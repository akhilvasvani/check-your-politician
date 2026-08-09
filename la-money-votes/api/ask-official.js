// api/ask-official.js
//
// Vercel serverless function (Node.js runtime) backing the "Ask about
// [Official Name]" search module on each official profile page
// (see official.html + js/ask-ai.js).
//
// Contract with the frontend:
//   POST /api/ask-official
//   body: {
//     question: string,                       // the user's typed question
//     official: {                              // context, not secret
//       id: string,           // e.g. "cd5-official" or "mayor" — used to key
//                              // the per-official rate limit
//       name: string,
//       title: string,        // e.g. "LA City Council District 5" or "Mayor"
//       district: string|number|null,
//       party: string
//     }
//   }
//   200 -> { answer: string, citations: [{ title: string, url: string }] }
//   4xx/5xx -> { error: string }   (always a human-readable message the
//                                    frontend can show as a fallback)
//
// Security / cost controls:
//   - PERPLEXITY_API_KEY is read from process.env ONLY. It is never sent to
//     the client, never logged in full, and must be set in Vercel's
//     Project Settings -> Environment Variables (see DEPLOYMENT.md) --
//     never committed to this repo.
//   - Only POST is accepted.
//   - Question length is capped server-side (defense in depth -- the
//     frontend also caps it via a maxlength attribute).
//   - Server-side rate limiting, keyed by IP + official page, backed by
//     Upstash Redis (REST API, no SDK dependency needed -- see
//     rateLimitViaUpstash below) when the Redis REST URL/token env vars
//     are set (see UPSTASH_URL_ENV_VARS / UPSTASH_TOKEN_ENV_VARS below --
//     Vercel's "Upstash for Redis" marketplace integration names these
//     KV_REST_API_URL / KV_REST_API_TOKEN, a holdover from Vercel's
//     original KV product, rather than the UPSTASH_-prefixed names Upstash
//     itself uses when connected directly; both are supported). Limits
//     are configurable via
//     RATE_LIMIT_MAX_REQUESTS / RATE_LIMIT_WINDOW_SECONDS env vars so they
//     can be tuned without a code change.
//   - If Upstash isn't configured yet, falls back to a best-effort
//     in-memory limiter (same config, same key shape) so the feature still
//     degrades safely rather than failing open -- but note this fallback is
//     NOT durable across cold starts / multiple instances / regions. Set up
//     Upstash (see DEPLOYMENT.md) before relying on this for real abuse
//     prevention.

const MAX_QUESTION_LENGTH = 300;

const DEFAULT_RATE_LIMIT_MAX_REQUESTS = 5;
const DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 600; // 10 minutes

const RATE_LIMIT_MAX_REQUESTS =
  Number.parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10) > 0
    ? Number.parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10)
    : DEFAULT_RATE_LIMIT_MAX_REQUESTS;

const RATE_LIMIT_WINDOW_SECONDS =
  Number.parseInt(process.env.RATE_LIMIT_WINDOW_SECONDS, 10) > 0
    ? Number.parseInt(process.env.RATE_LIMIT_WINDOW_SECONDS, 10)
    : DEFAULT_RATE_LIMIT_WINDOW_SECONDS;

const RATE_LIMIT_EXCEEDED_MESSAGE =
  "You've asked a lot of questions! Please wait a few minutes before asking again.";

// In-memory fallback store -- persists across invocations only while this
// function instance stays warm; resets on cold start. See note above: this
// is a soft backstop only, used when Upstash isn't configured.
const memoryHits = new Map(); // key -> { count, windowStart }

function getClientIp(req) {
  const forwarded = req.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.length > 0) {
    return forwarded.split(",")[0].trim();
  }
  return (req.socket && req.socket.remoteAddress) || "unknown";
}

function sanitizeContextField(value, maxLen) {
  if (typeof value === "string") return value.slice(0, maxLen);
  if (typeof value === "number") return String(value).slice(0, maxLen);
  return "";
}

function hostnameFor(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (err) {
    return "Source";
  }
}

// Rate limit via Upstash Redis's REST API using a fixed-window counter:
//   INCR key ; if new key, set EXPIRE to the window length.
// Uses plain fetch (no @upstash/redis SDK) so no npm dependency / build
// step is required for this static-site + serverless-function project.
async function rateLimitViaUpstash(key) {
  // Support both naming conventions so this works whether Redis was
  // connected via Vercel's "Upstash for Redis" marketplace integration
  // (which sets KV_REST_API_URL / KV_REST_API_TOKEN) or a direct Upstash
  // integration (which sets UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN).
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null; // not configured -- caller falls back

  const encodedKey = encodeURIComponent(key);
  const incrResp = await fetch(`${url}/incr/${encodedKey}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!incrResp.ok) {
    throw new Error(`Upstash INCR failed with status ${incrResp.status}`);
  }
  const incrData = await incrResp.json();
  const count = Number(incrData && incrData.result);

  if (count === 1) {
    // First hit in this window -- set the window's expiry.
    await fetch(`${url}/expire/${encodedKey}/${RATE_LIMIT_WINDOW_SECONDS}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).catch((err) => {
      console.warn("[ask-official] Upstash EXPIRE failed (non-fatal):", err);
    });
  }

  return { count, limited: count > RATE_LIMIT_MAX_REQUESTS };
}

function rateLimitViaMemory(key) {
  const now = Date.now();
  const windowMs = RATE_LIMIT_WINDOW_SECONDS * 1000;
  const entry = memoryHits.get(key);

  if (!entry || now - entry.windowStart > windowMs) {
    memoryHits.set(key, { count: 1, windowStart: now });
    return { count: 1, limited: false };
  }

  entry.count += 1;
  return { count: entry.count, limited: entry.count > RATE_LIMIT_MAX_REQUESTS };
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    res.status(405).json({ error: "Method not allowed. Use POST." });
    return;
  }

  const apiKey = process.env.PERPLEXITY_API_KEY;
  if (!apiKey) {
    console.error("[ask-official] PERPLEXITY_API_KEY is not set in this environment");
    res.status(500).json({ error: "Ask-AI is not configured on the server yet." });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (err) {
      res.status(400).json({ error: "Invalid JSON body." });
      return;
    }
  }
  if (!body || typeof body !== "object") {
    res.status(400).json({ error: "Invalid request body." });
    return;
  }

  const question = typeof body.question === "string" ? body.question.trim() : "";
  if (!question) {
    res.status(400).json({ error: "A question is required." });
    return;
  }
  if (question.length > MAX_QUESTION_LENGTH) {
    res.status(400).json({ error: `Question must be ${MAX_QUESTION_LENGTH} characters or fewer.` });
    return;
  }

  const official = (body.official && typeof body.official === "object") ? body.official : {};
  const officialId = sanitizeContextField(official.id, 80) || "unknown-official";
  const officialName = sanitizeContextField(official.name, 120) || "this official";
  const officialTitle = sanitizeContextField(official.title, 120);
  const officialParty = sanitizeContextField(official.party, 60);

  // --- Server-side rate limit: max N requests per IP per official page per
  // window. Tries Upstash Redis first (durable, shared across instances);
  // falls back to the in-memory limiter if Upstash isn't configured. ---
  const ip = getClientIp(req);
  const rateLimitKey = `ask-official:${ip}:${officialId}`;
  try {
    let rateLimitResult = null;
    try {
      rateLimitResult = await rateLimitViaUpstash(rateLimitKey);
    } catch (err) {
      console.warn("[ask-official] Upstash rate limit check failed, falling back to in-memory:", err);
      rateLimitResult = null;
    }
    if (!rateLimitResult) {
      rateLimitResult = rateLimitViaMemory(rateLimitKey);
    }
    if (rateLimitResult.limited) {
      res.status(429).json({ error: RATE_LIMIT_EXCEEDED_MESSAGE });
      return;
    }
  } catch (err) {
    // Rate limiting itself must never be the reason a legitimate request
    // fails outright -- log and continue if the check errors unexpectedly.
    console.error("[ask-official] Rate limit check threw unexpectedly:", err);
  }

  const districtOrCity = /mayor/i.test(officialTitle)
    ? "the City of Los Angeles"
    : (officialTitle || "Los Angeles");

  const DECLINE_MESSAGE =
    `I can only answer questions about ${officialName}\u2019s political record, ` +
    "policy positions, voting history, public statements, and biography, " +
    "or LA city/county politics more broadly. Try asking something on " +
    "one of those topics instead.";

  const systemPrompt =
    `You are answering questions about ${officialName}, the ${officialTitle || "official"}` +
    (officialParty ? ` (${officialParty})` : "") +
    ` representing ${districtOrCity}. Only answer based on verifiable public ` +
    "information about their political record, policy positions, voting " +
    "history, public statements, and biography.\n\n" +
    "You MUST respond with ONLY a single valid JSON object (no markdown " +
    "code fences, no text before or after it) matching exactly this " +
    'shape: {"in_scope": true or false, "answer": "..."}.\n\n' +
    "First, decide whether the user's question is actually about " +
    officialName + "'s political record, policy positions, voting " +
    "history, public statements, biography, or LA city/county government " +
    "and politics more broadly.\n" +
    "- If it is NOT in scope -- including general knowledge, trivia, " +
    "recipes, coding help, other public figures, or any other unrelated " +
    'topic, even if you know the answer -- set "in_scope" to false and ' +
    '"answer" to an empty string. Do not answer the off-topic question ' +
    "in the JSON at all, not even partially.\n" +
    '- If it IS in scope, set "in_scope" to true and put your answer in ' +
    '"answer": base it on verifiable public information, always cite ' +
    "sources, and keep it concise (3-5 sentences unless the question " +
    "clearly requires more detail). Be factual and neutral: do not " +
    "editorialize, endorse, or attack, and clearly note when something " +
    "is disputed or unconfirmed rather than guessing.";

  try {
    const upstream = await fetch("https://api.perplexity.ai/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "sonar",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: question },
        ],
        return_citations: true,
        // Force structured JSON output so the model must explicitly
        // decide in_scope before answering, rather than relying purely on
        // it following a plain-text instruction to decline off-topic
        // questions -- this is enforced server-side below regardless of
        // what the model puts in "answer".
        response_format: {
          type: "json_schema",
          json_schema: {
            schema: {
              type: "object",
              properties: {
                in_scope: { type: "boolean" },
                answer: { type: "string" },
              },
              required: ["in_scope", "answer"],
            },
          },
        },
      }),
    });

    if (!upstream.ok) {
      const errText = await upstream.text().catch(() => "");
      console.error("[ask-official] Perplexity API responded with", upstream.status, errText);
      res.status(502).json({ error: "The search service couldn't answer that question right now. Please try again shortly." });
      return;
    }

    const data = await upstream.json();
    const rawContent = data && data.choices && data.choices[0] && data.choices[0].message
      ? String(data.choices[0].message.content || "").trim()
      : "";

    if (!rawContent) {
      res.status(502).json({ error: "No answer was returned. Please try rephrasing your question." });
      return;
    }

    let parsed = null;
    try {
      // Defensive: strip accidental markdown code fences even though the
      // prompt and response_format both ask for raw JSON.
      const cleaned = rawContent.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/i, "").trim();
      parsed = JSON.parse(cleaned);
    } catch (err) {
      console.error("[ask-official] Failed to parse model JSON output:", rawContent);
      res.status(502).json({ error: "No answer was returned. Please try rephrasing your question." });
      return;
    }

    // Server-side enforcement of the scope decision: if the model marked
    // the question out of scope, ALWAYS use our own fixed decline message
    // and never surface whatever text it put in "answer", no matter what.
    if (parsed.in_scope !== true) {
      res.status(200).json({ answer: DECLINE_MESSAGE, citations: [] });
      return;
    }

    const answer = typeof parsed.answer === "string" ? parsed.answer.trim() : "";
    if (!answer) {
      res.status(502).json({ error: "No answer was returned. Please try rephrasing your question." });
      return;
    }

    const rawCitations = Array.isArray(data.citations) ? data.citations : [];
    const citations = rawCitations.slice(0, 8).map((url) => ({
      title: hostnameFor(url),
      url: String(url),
    }));

    res.status(200).json({ answer, citations });
  } catch (err) {
    console.error("[ask-official] Unexpected error calling the Perplexity API:", err);
    res.status(500).json({ error: "Unexpected server error. Please try again in a moment." });
  }
};
