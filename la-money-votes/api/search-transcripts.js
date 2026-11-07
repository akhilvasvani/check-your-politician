const { canonicalOfficial, withRequest } = require("./_lib/request-safety");
// api/search-transcripts.js
//
// Vercel serverless function backing the "Transcript search" module on
// each official profile page (see official.html + js/transcript-search.js).
//
// M2 refactor (2026-08-19): shared logic (snippet extraction, rate limiting,
// embedding, RPC invocation) moved to api/_lib/transcript-search-lib.js so
// api/search-public-comment.js can reuse it. Behavior for this endpoint is
// unchanged from M1.
//
// Contract with the frontend:
//   POST /api/search-transcripts
//   body: {
//     query: string,                // the user's search query (max 200 chars)
//     official: {
//       id: string,                  // e.g. "cd14-official"
//       resolved_official_id: string // MUST match roster.json values.
//                                     // Required.
//       name: string,                // display only
//     },
//     limit: number,                 // optional, default 8, cap 20
//     date_from: string,             // optional ISO date, e.g. "2026-01-01"
//     date_to: string                // optional ISO date
//   }
//   200 -> {
//     query, count,
//     results: [{
//       video_id, meeting_date, chunk_idx, start_sec, end_sec,
//       resolved_role, resolved_name, resolved_official_id,
//       text, token_count, similarity, sub_chunk_idx, sub_chunk_of, snippet?
//     }]
//   }
//   4xx/5xx -> { error }
//
// Backing store: Supabase Postgres with pgvector, table transcript_chunks
// (see la-money-votes/data/transcripts/schema.sql). RPC: search_transcripts.

const {
  MAX_QUERY_LENGTH,
  DEFAULT_LIMIT,
  MAX_LIMIT,
  MIN_SIMILARITY,
  RATE_LIMIT_EXCEEDED_MESSAGE,
  extractSnippet,
  getClientIp,
  isIsoDate,
  parseBody,
  readRpcConfig,
  checkRateLimit,
  embedQuery,
  searchTranscriptsRpc,
  logSearchMetrics,
} = require("./_lib/transcript-search-lib");

const ENDPOINT = "search-transcripts";

module.exports = withRequest("search-transcripts", async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    res.status(405).json({ error: "Method not allowed. Use POST." });
    return;
  }

  const parsed = parseBody(req);
  if (parsed.error) {
    res.status(400).json({ error: parsed.error });
    return;
  }
  const body = parsed.body;

  const query = typeof body.query === "string" ? body.query.trim() : "";
  if (!query) {
    res.status(400).json({ error: "A search query is required." });
    return;
  }
  if (query.length > MAX_QUERY_LENGTH) {
    res.status(400).json({ error: `Query must be ${MAX_QUERY_LENGTH} characters or fewer.` });
    return;
  }

  const official = body.official || {};
  const canonical = canonicalOfficial(official.id, true);
  const officialId = canonical && canonical.id;
  if (!officialId || (official.resolved_official_id !== undefined && official.resolved_official_id !== officialId)) {
    // Panel is shown per-councilmember. When a councilmember isn't linked
    // to a canonical official_id (roster.json), the frontend should hide
    // the module entirely -- this 400 is the safety net.
    res.status(400).json({
      error: "This official isn't linked to the transcript index yet.",
    });
    return;
  }

  const limit = Math.min(
    Math.max(Number.parseInt(body.limit, 10) || DEFAULT_LIMIT, 1),
    MAX_LIMIT
  );

  const dateFrom = body.date_from == null ? null : body.date_from;
  const dateTo = body.date_to == null ? null : body.date_to;
  if ((dateFrom !== null && !isIsoDate(dateFrom)) || (dateTo !== null && !isIsoDate(dateTo)) || (dateFrom && dateTo && dateFrom > dateTo)) {
    res.status(400).json({ error: "Supply valid calendar dates in YYYY-MM-DD order, with date_from on or before date_to." });
    return;
  }
  if (process.env.TRANSCRIPT_SEARCH_DISABLED === "true") {
    res.status(503).json({ error: "Transcript search is temporarily unavailable." });
    return;
  }

  try {
    readRpcConfig();
  } catch {
    res.status(503).json({ error: "Transcript search is temporarily unavailable." });
    return;
  }

  const ip = getClientIp(req);
  const startedAt = Date.now();

  try {
    const rl = await checkRateLimit(ip);
    if (rl.limited) {
      logSearchMetrics({
        endpoint: ENDPOINT,
        outcome: "rate_limited",
        q_len: query.length,
        min_sim: MIN_SIMILARITY,
        duration_ms: Date.now() - startedAt,
        official: officialId,
        date_from: dateFrom,
        date_to: dateTo,
      });
      res.status(429).json({ error: RATE_LIMIT_EXCEEDED_MESSAGE });
      return;
    }
  } catch (err) {
    console.warn("[search-transcripts] limiter unavailable");
    res.status(503).json({ error: "Search is temporarily unavailable. Please try again later." });
    return;
  }

  try {
    const embedding = await embedQuery(query);
    const results = await searchTranscriptsRpc({
      embedding,
      officialId,
      dateFrom,
      dateTo,
      limit,
      minSimilarity: MIN_SIMILARITY,
    });

    if (!Array.isArray(results)) throw new Error("Malformed search response");
    const resultArray = results.map((row) => {
      if (!row || typeof row.text !== "string" || row.resolved_official_id !== officialId) throw new Error("Unexpected transcript attribution");
      const snippet = extractSnippet(row.text, query);
      return snippet ? { ...row, snippet } : row;
    });
    const top1Sim = resultArray[0] && typeof resultArray[0].similarity === "number"
      ? resultArray[0].similarity
      : null;
    logSearchMetrics({
      endpoint: ENDPOINT,
      outcome: resultArray.length === 0 ? "empty" : "ok",
      q_len: query.length,
      count: resultArray.length,
      top1_sim: top1Sim,
      min_sim: MIN_SIMILARITY,
      duration_ms: Date.now() - startedAt,
      official: officialId,
      date_from: dateFrom,
      date_to: dateTo,
    });

    res.status(200).json({
      query,
      count: resultArray.length,
      results: resultArray,
    });
  } catch (err) {
    console.warn("[search-transcripts] provider request failed");
    logSearchMetrics({
      endpoint: ENDPOINT,
      outcome: "error",
      q_len: query.length,
      min_sim: MIN_SIMILARITY,
      duration_ms: Date.now() - startedAt,
      official: officialId,
      date_from: dateFrom,
      date_to: dateTo,
    });
    res.status(502).json({
      error:
        "Transcript search is temporarily unavailable. Please try again in a moment.",
    });
  }
});
