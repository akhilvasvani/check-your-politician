const { getClientIp, fetchJson, rateCounter, aggregatePaidLimit } = require("./request-safety");
// api/_lib/transcript-search-lib.js
//
// Shared building blocks for the transcript-search family of serverless
// endpoints:
//   - api/search-transcripts.js      (per-official search)
//   - api/search-public-comment.js   (public-comment-only search, M2.1)
//   - api/transcript-coverage.js      (per-official coverage aggregate, M3.2)
//
// Both endpoints share:
//   * query length / IP extraction / JSON parsing conventions
//   * snippet extraction from CART chunks
//   * durable per-IP rate limiting, failing closed on outages
//   * Perplexity embedding call for the query
//   * generic Supabase RPC invocation
//
// The differences are handled in each endpoint's own handler:
//   * request-shape validation (search-transcripts requires an official id,
//     search-public-comment does not)
//   * which RPC name to invoke + which parameters to pass
//
// Design notes:
//   - No hidden globals: rate-limit config is read from env at import time
//     but exported so callers can inspect it.
//   - Backwards-compatible with the previous single-file search-transcripts.js:
//     same MAX_QUERY_LENGTH, same MIN_SIMILARITY, same snippet output.

const MAX_QUERY_LENGTH = 200;
const DEFAULT_LIMIT = 8;
const MAX_LIMIT = 20;

// Must match scripts/transcripts/build_transcripts.py's EMBED_MODEL. If you
// change one, change both AND re-embed the corpus.
const EMBED_MODEL_NAME = "pplx-embed-v1-0.6b";
const EMBED_DIM = 1024;

// Cosine-similarity floor for returned chunks. Validated in M1.4 against a
// 20-query gold set on the full 5,003-chunk / 9-meeting corpus (see
// data/transcripts/eval_results_m1.4.json): parent@1 = 90%, parent@3 = 100%.
const MIN_SIMILARITY = 0.25;

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

// --- Structured metrics logging (M2.3) -------------------------------------
// Emits a single line per request so we can watch endpoint health in Vercel
// logs without shipping OpenTelemetry. Format is deliberately grep-friendly:
//   [metrics endpoint=<name> outcome=<ok|empty|error|rate_limited>
//     q_len=<int> count=<int|-> top1_sim=<float|-> min_sim=<float>
//     duration_ms=<int> official=<id|-> date_from=<iso|-> date_to=<iso|->]
// Never log raw query text: legal + civic-data caution. Query length only.
function logSearchMetrics(fields) {
  const parts = ["[metrics]"];
  for (const key of [
    "endpoint",
    "outcome",
    "q_len",
    "count",
    "top1_sim",
    "min_sim",
    "duration_ms",
    "official",
    "date_from",
    "date_to",
  ]) {
    let v = fields[key];
    if (v === undefined || v === null || v === "") v = "-";
    if (typeof v === "number" && Number.isFinite(v) && !Number.isInteger(v)) {
      v = v.toFixed(3);
    }
    parts.push(`${key}=${v}`);
  }
  console.log(parts.join(" "));
}

// --- Snippet extraction ----------------------------------------------------
// See history in search-transcripts.js — kept verbatim so both endpoints
// present the same snippet UX.

const SNIPPET_STOPWORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
  "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
  "to", "was", "were", "what", "when", "where", "which", "who", "will",
  "with", "about", "does", "do", "did", "how", "why", "their", "they",
]);

const SNIPPET_CONTEXT_SENTENCES = 1;
const SNIPPET_MAX_CHARS = 420;
const SNIPPET_FALLBACK_CHARS = 280;

function splitSentences(text) {
  const parts = String(text)
    .split(/(?<=[.?!])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  return parts.length > 0 ? parts : [String(text).trim()];
}

function queryTerms(query) {
  return String(query)
    .toLowerCase()
    .split(/[^a-z0-9']+/)
    .filter((t) => t.length > 2 && !SNIPPET_STOPWORDS.has(t));
}

function extractSnippet(text, query) {
  const sentences = splitSentences(text);
  if (sentences.length <= 2) return null;

  const terms = queryTerms(query);
  let bestIdx = -1;
  let bestScore = 0;
  for (let i = 0; i < sentences.length; i++) {
    const lower = sentences[i].toLowerCase();
    let score = 0;
    for (const t of terms) {
      if (lower.includes(t)) score += 1;
    }
    if (score > bestScore) {
      bestScore = score;
      bestIdx = i;
    }
  }

  if (bestIdx === -1) {
    const head = sentences.slice(0, 2).join(" ");
    return head.length > SNIPPET_FALLBACK_CHARS
      ? head.slice(0, SNIPPET_FALLBACK_CHARS).replace(/\s+\S*$/, "") + "\u2026"
      : head + (sentences.length > 2 ? " \u2026" : "");
  }

  const start = Math.max(0, bestIdx - SNIPPET_CONTEXT_SENTENCES);
  const end = Math.min(sentences.length, bestIdx + SNIPPET_CONTEXT_SENTENCES + 1);
  let snippet = sentences.slice(start, end).join(" ");
  if (snippet.length > SNIPPET_MAX_CHARS) {
    snippet = sentences[bestIdx];
    if (snippet.length > SNIPPET_MAX_CHARS) {
      snippet = snippet.slice(0, SNIPPET_MAX_CHARS).replace(/\s+\S*$/, "") + "\u2026";
    }
  }
  const prefix = start > 0 ? "\u2026 " : "";
  const suffix = end < sentences.length ? " \u2026" : "";
  return prefix + snippet + suffix;
}

// --- Request helpers -------------------------------------------------------
function isIsoDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  if (value.startsWith("0000-")) return false;
  const date = new Date(value + "T00:00:00Z");
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

// --- Rate limiting ---------------------------------------------------------
async function checkRateLimit(ip) {
  const minuteBucket = Math.floor(Date.now() / 60000);
  const hourBucket = Math.floor(Date.now() / 3600000);
  const aggregate = await aggregatePaidLimit(ip);
  if (aggregate.limited) return aggregate;
  const minResult = await rateCounter(`tsx:1m:${ip}:${minuteBucket}`, 90, RATE_LIMIT_PER_MIN);
  if (minResult.limited) return minResult;
  const hourResult = await rateCounter(`tsx:1h:${ip}:${hourBucket}`, 3700, RATE_LIMIT_PER_HOUR);
  return { limited: hourResult.limited };
}

// --- Embedding -------------------------------------------------------------
async function embedQuery(queryText) {
  const apiKey = process.env.PERPLEXITY_API_KEY;
  if (!apiKey) throw new Error("PERPLEXITY_API_KEY is not set in this environment.");

  const data = await fetchJson("https://api.perplexity.ai/v1/embeddings", {
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
  }, "embedding");

  const item = (data && Array.isArray(data.data)) ? data.data[0] : null;
  if (!item || typeof item.embedding !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(item.embedding)) {
    throw new Error("Unexpected Perplexity embedding response shape.");
  }

  const raw = Buffer.from(item.embedding, "base64");
  const vec = new Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    vec[i] = raw[i] > 127 ? raw[i] - 256 : raw[i];
  }
  if (vec.length !== EMBED_DIM) {
    throw new Error(`Expected ${EMBED_DIM}-dim embedding, got ${vec.length}.`);
  }
  if (!vec.some((value) => value !== 0)) throw new Error("Embedding vector has zero magnitude.");
  return vec;
}

// --- Supabase RPC ----------------------------------------------------------
function readRpcConfig() {
  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseKey = process.env.SUPABASE_ANON_KEY;
  if (!supabaseUrl || !supabaseKey) {
    throw new Error("SUPABASE_URL and SUPABASE_ANON_KEY must both be set.");
  }
  if (supabaseKey === process.env.SUPABASE_SERVICE_ROLE_KEY || supabaseKey.startsWith("sb_secret_")) throw new Error("Read credentials must be anonymous.");
  const publishable = /^sb_publishable_[A-Za-z0-9_-]+$/.test(supabaseKey);
  if (!publishable) {
    if (!/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(supabaseKey)) {
      throw new Error("Expected a publishable key or legacy anonymous JWT.");
    }
    const claims = JSON.parse(Buffer.from(supabaseKey.split(".")[1], "base64url").toString("utf8"));
    if (claims.role !== "anon") throw new Error("Read credentials must be anonymous.");
  }
  const baseUrl = new URL(supabaseUrl);
  if (baseUrl.protocol !== "https:" || baseUrl.username || baseUrl.password) throw new Error("Invalid read endpoint configuration.");
  return { supabaseUrl, supabaseKey, publishable };
}

async function callRpc(rpcName, params) {
  const { supabaseUrl, supabaseKey, publishable } = readRpcConfig();
  const rpcUrl = `${supabaseUrl}/rest/v1/rpc/${rpcName}`;
  return fetchJson(rpcUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: supabaseKey,
      // Publishable keys are API keys, not JWT bearer tokens.
      ...(publishable ? {} : { Authorization: `Bearer ${supabaseKey}` }),
    },
    body: JSON.stringify(params),
  }, "rpc");
}

async function searchTranscriptsRpc({ embedding, officialId, dateFrom, dateTo, limit, minSimilarity }) {
  return callRpc("search_transcripts", {
    p_query_embedding: embedding,
    p_official_id: officialId,
    p_date_from: dateFrom || null,
    p_date_to: dateTo || null,
    p_embedding_model: EMBED_MODEL_NAME,
    p_match_count: limit,
    p_min_similarity: minSimilarity,
  });
}

async function searchPublicCommentRpc({ embedding, dateFrom, dateTo, limit, minSimilarity }) {
  return callRpc("search_public_comment", {
    p_query_embedding: embedding,
    p_date_from: dateFrom || null,
    p_date_to: dateTo || null,
    p_embedding_model: EMBED_MODEL_NAME,
    p_match_count: limit,
    p_min_similarity: minSimilarity,
  });
}

async function transcriptCoverageRpc({ officialId }) {
  return callRpc("get_transcript_coverage", {
    p_official_id: officialId,
    p_embedding_model: EMBED_MODEL_NAME,
  });
}

// --- Body parsing ----------------------------------------------------------
function parseBody(req) {
  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (err) {
      return { error: "Invalid JSON body." };
    }
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { error: "Invalid request body." };
  }
  return { body };
}

module.exports = {
  // constants
  MAX_QUERY_LENGTH,
  DEFAULT_LIMIT,
  MAX_LIMIT,
  EMBED_MODEL_NAME,
  EMBED_DIM,
  MIN_SIMILARITY,
  RATE_LIMIT_PER_MIN,
  RATE_LIMIT_PER_HOUR,
  RATE_LIMIT_EXCEEDED_MESSAGE,

  // helpers
  extractSnippet,
  getClientIp,
  isIsoDate,
  parseBody,
  readRpcConfig,
  checkRateLimit,
  embedQuery,
  searchTranscriptsRpc,
  searchPublicCommentRpc,
  transcriptCoverageRpc,
  logSearchMetrics,
};
