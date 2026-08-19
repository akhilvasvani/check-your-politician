// api/search-transcripts.js
//
// Vercel serverless function backing the "Transcript search" module on
// each official profile page (see official.html + js/transcript-search.js).
//
// Contract with the frontend:
//   POST /api/search-transcripts
//   body: {
//     query: string,                // the user's search query (max 200 chars)
//     official: {
//       id: string,                  // e.g. "cd14-official"
//       resolved_official_id: string // MUST match roster.json values
//                                     // (e.g. "cd14-official"). Required.
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
//       text, token_count, similarity
//     }]
//   }
//   4xx/5xx -> { error }
//
// Backing store:
//   Supabase Postgres with pgvector, table transcript_chunks (see
//   la-money-votes/data/transcripts/schema.sql). Query is embedded via
//   Perplexity /v1/embeddings using the same model as the ingestion
//   pipeline (build_transcripts.py) -- if the two ever drift the RPC's
//   embedding_model filter will match zero rows, which is safer than
//   returning silently-bad results.
//
// Security / cost controls (mirroring ask-official.js):
//   - PERPLEXITY_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY (or SERVICE_ROLE)
//     read from process.env only. Never sent to the client.
//   - Only POST is accepted.
//   - Query length capped at 200 chars server-side.
//   - Two rate-limit windows per IP (BOTH must be under limit):
//       * TRANSCRIPT_RATE_LIMIT_PER_MIN     (default 10)
//       * TRANSCRIPT_RATE_LIMIT_PER_HOUR    (default 60)
//     Backed by Upstash Redis if configured, in-memory fallback otherwise.

const MAX_QUERY_LENGTH = 200;
const DEFAULT_LIMIT = 8;
const MAX_LIMIT = 20;

// MUST match scripts/transcripts/build_transcripts.py's EMBED_MODEL.
// If you change one, change both AND re-embed the corpus.
const EMBED_MODEL_NAME = "pplx-embed-v1-0.6b";
const EMBED_DIM = 1024;

// Cosine-similarity floor for returned chunks. Any hit below this is treated
// as "no chunk in this corpus is actually about the query" and dropped.
// Rationale: M0.2 v2 re-eval (spike-m0/embed_bakeoff_v2_pplx.json, 2026-08-19)
// showed off-topic chunks scoring ~0.25-0.32 and on-topic chunks ~0.37+.
// The SQL RPC applies the same default; this constant just lets the API
// override it if we ever want to tune per-request.
const MIN_SIMILARITY = 0.35;

const DEFAULT_PER_MIN = 10;
const DEFAULT_PER_HOUR = 60;

const RATE_LIMIT_PER_MIN =
  Number.parseInt(process.env.TRANSCRIPT_RATE_LIMIT_PER_MIN, 10) > 0
    ? Number.parseInt(process.env.TRANSCRIPT_RATE_LIMIT_PER_MIN, 10)
    : DEFAULT_PER_MIN;

const RATE_LIMIT_PER_HOUR =
  Number.parseInt(process.env.TRANSCRIPT_RATE_LIMIT_PER_HOUR, 10) > 0
    ? Number.parseInt(process.env.TRANSCRIPT_RATE_LIMIT_PER_HOUR, 10)
    : DEFAULT_PER_HOUR;

const RATE_LIMIT_EXCEEDED_MESSAGE =
  "You've searched a lot recently. Please wait a minute before searching again.";

const memoryHits = new Map(); // key -> { count, windowStart }

function getClientIp(req) {
  const forwarded = req.headers["x-forwarded-for"];
  if (typeof forwarded === "string" && forwarded.length > 0) {
    return forwarded.split(",")[0].trim();
  }
  return (req.socket && req.socket.remoteAddress) || "unknown";
}

function sanitizeString(value, maxLen) {
  if (typeof value === "string") return value.slice(0, maxLen);
  return "";
}

function isIsoDate(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

// -------- Rate limiting --------
async function rateLimitViaUpstash(key, windowSeconds, limit) {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;

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
    await fetch(`${url}/expire/${encodedKey}/${windowSeconds}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).catch((err) => {
      console.warn("[search-transcripts] Upstash EXPIRE failed (non-fatal):", err);
    });
  }
  return { count, limited: count > limit };
}

function rateLimitViaMemory(key, windowSeconds, limit) {
  const now = Date.now();
  const windowMs = windowSeconds * 1000;
  const entry = memoryHits.get(key);
  if (!entry || now - entry.windowStart > windowMs) {
    memoryHits.set(key, { count: 1, windowStart: now });
    return { count: 1, limited: false };
  }
  entry.count += 1;
  return { count: entry.count, limited: entry.count > limit };
}

async function checkRateLimit(ip) {
  const now = Date.now();
  const minuteBucket = Math.floor(now / 60_000);
  const hourBucket = Math.floor(now / 3_600_000);
  const minuteKey = `tsx:1m:${ip}:${minuteBucket}`;
  const hourKey = `tsx:1h:${ip}:${hourBucket}`;

  let minResult;
  let hourResult;
  try {
    minResult = await rateLimitViaUpstash(minuteKey, 90, RATE_LIMIT_PER_MIN);
    hourResult = await rateLimitViaUpstash(hourKey, 3700, RATE_LIMIT_PER_HOUR);
  } catch (err) {
    console.warn("[search-transcripts] Upstash rate-limit failed, falling back to memory:", err);
    minResult = null;
    hourResult = null;
  }
  if (!minResult) minResult = rateLimitViaMemory(minuteKey, 60, RATE_LIMIT_PER_MIN);
  if (!hourResult) hourResult = rateLimitViaMemory(hourKey, 3600, RATE_LIMIT_PER_HOUR);
  return { minResult, hourResult, limited: minResult.limited || hourResult.limited };
}

// -------- Embedding --------
// Perplexity /v1/embeddings returns base64-encoded int8 values by default.
// We decode to a plain number array (values in [-128, 127]). Cosine
// similarity is scale-invariant so the magnitude is fine to keep; we do
// NOT L2-normalize. See Perplexity's best-practices doc:
// https://docs.perplexity.ai/docs/embeddings/best-practices
async function embedQuery(queryText) {
  const apiKey = process.env.PERPLEXITY_API_KEY;
  if (!apiKey) throw new Error("PERPLEXITY_API_KEY is not set in this environment.");

  const resp = await fetch("https://api.perplexity.ai/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      input: queryText,
      model: EMBED_MODEL_NAME,
      encoding_format: "base64_int8",
    }),
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`Perplexity embed failed status=${resp.status} body=${body.slice(0, 200)}`);
  }

  const data = await resp.json();
  const item = (data && Array.isArray(data.data)) ? data.data[0] : null;
  if (!item || typeof item.embedding !== "string") {
    throw new Error("Unexpected Perplexity embedding response shape.");
  }

  // Decode base64 -> Uint8Array -> signed int8 -> number[].
  const raw = Buffer.from(item.embedding, "base64");
  const vec = new Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    // Convert unsigned byte to signed int8 (-128..127).
    vec[i] = raw[i] > 127 ? raw[i] - 256 : raw[i];
  }
  if (vec.length !== EMBED_DIM) {
    throw new Error(`Expected ${EMBED_DIM}-dim embedding, got ${vec.length}.`);
  }
  return vec;
}

// -------- Supabase RPC --------
async function searchTranscriptsRpc({ embedding, officialId, dateFrom, dateTo, limit, minSimilarity }) {
  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseKey =
    process.env.SUPABASE_ANON_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !supabaseKey) {
    throw new Error("SUPABASE_URL and a Supabase key must both be set.");
  }
  const rpcUrl = `${supabaseUrl}/rest/v1/rpc/search_transcripts`;
  const resp = await fetch(rpcUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: supabaseKey,
      Authorization: `Bearer ${supabaseKey}`,
    },
    body: JSON.stringify({
      p_query_embedding: embedding,
      p_official_id: officialId,
      p_date_from: dateFrom || null,
      p_date_to: dateTo || null,
      p_embedding_model: EMBED_MODEL_NAME,
      p_match_count: limit,
      p_min_similarity: minSimilarity,
    }),
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`Supabase RPC failed status=${resp.status} body=${body.slice(0, 300)}`);
  }
  return resp.json();
}

// -------- Handler --------
module.exports = async function handler(req, res) {
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
  if (!body || typeof body !== "object") {
    res.status(400).json({ error: "Invalid request body." });
    return;
  }

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

  try {
    const rl = await checkRateLimit(ip);
    if (rl.limited) {
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

    const resultArray = Array.isArray(results) ? results : [];
    if (resultArray.length === 0) {
      // Useful signal for tuning the floor: this fires when the model had
      // an opinion but every hit was below MIN_SIMILARITY, vs. "the
      // official has no chunks in the index at all."
      console.log(
        `[search-transcripts] no results above similarity=${MIN_SIMILARITY} ` +
          `for official=${officialId} query=${query.slice(0, 80)}`
      );
    }

    res.status(200).json({
      query,
      count: resultArray.length,
      results: resultArray,
    });
  } catch (err) {
    console.error("[search-transcripts] search failed:", err);
    res.status(502).json({
      error:
        "Transcript search is temporarily unavailable. Please try again in a moment.",
    });
  }
};
