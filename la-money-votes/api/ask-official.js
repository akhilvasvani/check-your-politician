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
//   - A best-effort per-IP in-memory rate limit adds a second layer behind
//     the frontend's own debounce. NOTE: this is a soft backstop only --
//     serverless function instances are not guaranteed to be warm/shared
//     across requests, regions, or deployments, so a determined caller can
//     bypass it. Do not rely on this alone if real abuse-prevention is
//     ever needed; add a durable store (e.g. Vercel KV / Upstash) instead.

const MAX_QUESTION_LENGTH = 300;
const RATE_LIMIT_WINDOW_MS = 5000;

// Module-level Map -> persists across invocations only while this function
// instance stays warm. Reset to empty on cold start. See note above.
const lastRequestByIp = new Map();

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

  const ip = getClientIp(req);
  const now = Date.now();
  const lastRequest = lastRequestByIp.get(ip) || 0;
  if (now - lastRequest < RATE_LIMIT_WINDOW_MS) {
    res.status(429).json({ error: "Please wait a few seconds before asking another question." });
    return;
  }
  lastRequestByIp.set(ip, now);

  const official = (body.official && typeof body.official === "object") ? body.official : {};
  const officialName = sanitizeContextField(official.name, 120) || "this official";
  const officialTitle = sanitizeContextField(official.title, 120);
  const officialDistrict = sanitizeContextField(official.district, 10);
  const officialParty = sanitizeContextField(official.party, 60);

  const contextLine = [
    `Name: ${officialName}`,
    officialTitle ? `Title/Office: ${officialTitle}` : null,
    officialDistrict ? `District: ${officialDistrict}` : null,
    officialParty ? `Party: ${officialParty}` : null,
  ]
    .filter(Boolean)
    .join(" | ");

  const systemPrompt =
    "You are a nonpartisan civic-information assistant embedded on a public " +
    "accountability website about Los Angeles city officials. Answer the " +
    "user's question about the specific official identified below using " +
    "current, verifiable public information. Be factual, concise (roughly " +
    "3-6 sentences), and neutral in tone: do not editorialize, endorse, or " +
    "attack, and clearly note when something is disputed or unconfirmed " +
    "rather than guessing. Ground your answer in real, checkable sources.\n\n" +
    `Official being asked about -- ${contextLine}`;

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
      }),
    });

    if (!upstream.ok) {
      const errText = await upstream.text().catch(() => "");
      console.error("[ask-official] Perplexity API responded with", upstream.status, errText);
      res.status(502).json({ error: "The search service couldn't answer that question right now. Please try again shortly." });
      return;
    }

    const data = await upstream.json();
    const answer = data && data.choices && data.choices[0] && data.choices[0].message
      ? String(data.choices[0].message.content || "").trim()
      : "";

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
