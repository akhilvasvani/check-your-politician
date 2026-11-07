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
  sanitizeString,
  isIsoDate,
  parseBody,
  checkRateLimit,
  embedQuery,
  searchTranscriptsRpc,
  logSearchMetrics,
} = require("./_lib/transcript-search-lib");

const ENDPOINT = "search-transcripts";

module.exports = async function handler(req, res) {
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

  const query = sanitizeString(body.query, MAX_QUERY_LENGTH).trim();
  if (!query) {
    res.status(400).json({ error: "A search query is required." });
    return;
  }
  if (query.length > MAX_QUERY_LENGTH) {
    res.status(400).json({ error: `Query must be ${MAX_QUERY_LENGTH} characters or fewer.` });
    return;
  }

  const official = body.official || {};
  const officialId = sanitizeString(official.resolved_official_id, 64);
  if (!officialId) {
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

  const dateFrom = isIsoDate(body.date_from) ? body.date_from : null;
  const dateTo = isIsoDate(body.date_to) ? body.date_to : null;

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
    console.error("[search-transcripts] rate limit check errored:", err);
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

    const resultArray = (Array.isArray(results) ? results : []).map((row) => {
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
    console.error("[search-transcripts] search failed:", err);
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
};
