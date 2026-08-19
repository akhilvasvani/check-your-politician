// api/search-public-comment.js
//
// Vercel serverless function backing the "Public comment" search surface
// (M2.1). Same look/feel as /api/search-transcripts, but the corpus is
// filtered server-side (in the SQL RPC) to public commenters only —
// resolved_role = 'public-speaker' — so councilmember/clerk/counsel/etc.
// chunks are never returned here even if they're semantically closer.
//
// Contract with the frontend:
//   POST /api/search-public-comment
//   body: {
//     query: string,                 // the user's search query (max 200 chars)
//     limit: number,                 // optional, default 8, cap 20
//     date_from: string,             // optional ISO date, e.g. "2026-01-01"
//     date_to: string                // optional ISO date
//   }
//   200 -> {
//     query, count,
//     results: [{
//       video_id, meeting_date, chunk_idx, start_sec, end_sec,
//       resolved_role, resolved_official_id, resolved_name,
//       source_label, turn_speaker_raw,
//       text, token_count, similarity, sub_chunk_idx, sub_chunk_of, snippet?
//     }]
//   }
//   4xx/5xx -> { error }
//
// Attribution note: public commenters don't have canonical IDs (resolved_
// official_id is NULL for these rows), so the frontend should display the
// CART cue verbatim — usually "PUBLIC SPEAKER" or "Speaker" — from
// resolved_name / source_label rather than the councilmember-style
// "Council President" label. M2 plan (scripts/transcripts/M2_PLAN.md, D5)
// intentionally keeps attribution at the cue level for the MVP.
//
// Rate limiting is shared with /api/search-transcripts (same `tsx:*` keys)
// so per-IP abuse ceilings apply across both endpoints.

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
  searchPublicCommentRpc,
} = require("./_lib/transcript-search-lib");

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

  const limit = Math.min(
    Math.max(Number.parseInt(body.limit, 10) || DEFAULT_LIMIT, 1),
    MAX_LIMIT
  );

  const dateFrom = isIsoDate(body.date_from) ? body.date_from : null;
  const dateTo = isIsoDate(body.date_to) ? body.date_to : null;

  const ip = getClientIp(req);

  try {
    const rl = await checkRateLimit(ip);
    if (rl.limited) {
      res.status(429).json({ error: RATE_LIMIT_EXCEEDED_MESSAGE });
      return;
    }
  } catch (err) {
    console.error("[search-public-comment] rate limit check errored:", err);
  }

  try {
    const embedding = await embedQuery(query);
    const results = await searchPublicCommentRpc({
      embedding,
      dateFrom,
      dateTo,
      limit,
      minSimilarity: MIN_SIMILARITY,
    });

    const resultArray = (Array.isArray(results) ? results : []).map((row) => {
      const snippet = extractSnippet(row.text, query);
      return snippet ? { ...row, snippet } : row;
    });
    if (resultArray.length === 0) {
      console.log(
        `[search-public-comment] no results above similarity=${MIN_SIMILARITY} ` +
          `for query=${query.slice(0, 80)}`
      );
    }

    res.status(200).json({
      query,
      count: resultArray.length,
      results: resultArray,
    });
  } catch (err) {
    console.error("[search-public-comment] search failed:", err);
    res.status(502).json({
      error:
        "Public comment search is temporarily unavailable. Please try again in a moment.",
    });
  }
};
