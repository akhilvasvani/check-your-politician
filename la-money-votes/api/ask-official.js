// Web-grounded Ask-AI. Canonical identity and all provider credentials stay server-side.
const { canonicalOfficial, getClientIp, withRequest, fetchJson, rateCounter, aggregatePaidLimit, safeUrl } = require("./_lib/request-safety");

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

function hostnameFor(url) {
  return new URL(url).hostname.replace(/^www\./, "");
}

module.exports = withRequest("ask-official", async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    res.status(405).json({ error: "Method not allowed. Use POST." });
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
  if (!body || typeof body !== "object" || Array.isArray(body)) {
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

  const official = canonicalOfficial(body.official && body.official.id);
  if (!official) {
    res.status(400).json({ error: "A supported official ID is required." });
    return;
  }
  const officialName = official.name;
  const officialTitle = official.office;
  const officialParty = official.party && official.party.affiliation;
  if (process.env.ASK_AI_DISABLED === "true") {
    res.status(503).json({ error: "Ask-AI is temporarily unavailable. You can still inspect the profile's source records." });
    return;
  }
  const apiKey = process.env.PERPLEXITY_API_KEY;
  if (!apiKey) {
    res.status(503).json({ error: "Ask-AI is temporarily unavailable." });
    return;
  }
  const ip = getClientIp(req);
  try {
    const aggregate = await aggregatePaidLimit(ip);
    const bucket = Math.floor(Date.now() / (RATE_LIMIT_WINDOW_SECONDS * 1000));
    const result = aggregate.limited ? aggregate : await rateCounter(`ask-official:${ip}:${bucket}`, RATE_LIMIT_WINDOW_SECONDS, RATE_LIMIT_MAX_REQUESTS);
    if (result.limited) {
      res.status(429).json({ error: RATE_LIMIT_EXCEEDED_MESSAGE });
      return;
    }
  } catch {
    console.warn("[ask-official] limiter unavailable");
    res.status(503).json({ error: "Ask-AI is temporarily unavailable. Please try again later." });
    return;
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
    const data = await fetchJson("https://api.perplexity.ai/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: "sonar",
        max_tokens: 600,
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
    }, "generation");

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
      console.warn("[ask-official] invalid provider output");
      res.status(502).json({ error: "No answer was returned. Please try rephrasing your question." });
      return;
    }

    // Server-side enforcement of the scope decision: if the model marked
    // the question out of scope, ALWAYS use our own fixed decline message
    // and never surface whatever text it put in "answer", no matter what.
    if (!parsed || typeof parsed.in_scope !== "boolean" || typeof parsed.answer !== "string") {
      res.status(502).json({ error: "No usable answer was returned. Please try again." });
      return;
    }
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
    const citations = rawCitations.map(safeUrl).filter(Boolean).slice(0, 8).map((url) => ({
      title: hostnameFor(url),
      url: String(url),
    }));

    res.status(200).json({ answer, citations });
  } catch (err) {
    console.warn("[ask-official] provider request failed");
    res.status(502).json({ error: "The answer service is temporarily unavailable. Please try again in a moment." });
  }
});
