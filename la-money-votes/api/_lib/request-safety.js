"use strict";

const { AsyncLocalStorage } = require("node:async_hooks");
const { randomUUID } = require("node:crypto");
const { isIP } = require("node:net");
const officials = require("../../data/officials.json");
const roster = require("../../data/transcripts/roster.json");
const contexts = new AsyncLocalStorage();
const memoryCounters = new Map();
const DEADLINES = { limiter: 2000, embedding: 12000, rpc: 5000, generation: 22000 };

function canonicalOfficial(id, transcript = false) {
  const official = officials.find((entry) => entry.id === id);
  if (!official) return null;
  if (transcript && !roster.members.some((entry) => entry.official_id === id)) return null;
  return official;
}

function getClientIp(req) {
  // Vercel overwrites this header at its trusted ingress. Outside Vercel,
  // use the socket peer and ignore caller-supplied proxy headers.
  // https://vercel.com/docs/headers/request-headers#x-vercel-forwarded-for
  const candidate = process.env.VERCEL === "1"
    ? req.headers && req.headers["x-vercel-forwarded-for"]
    : req.socket && req.socket.remoteAddress;
  return typeof candidate === "string" && isIP(candidate.trim()) ? candidate.trim() : "unknown";
}

function withRequest(endpoint, handler) {
  return async function (req, res) {
    const request = {
      request_id: randomUUID(),
      endpoint,
      started: Date.now(),
      calls: { limiter: 0, embedding: 0, rpc: 0, generation: 0 },
      controller: new AbortController(),
    };
    res.setHeader("X-Request-ID", request.request_id);
    const abort = () => request.controller.abort();
    const deadline = setTimeout(abort, 28000);
    req.once?.("aborted", abort);
    const closed = () => {
      if (!res.writableEnded) abort();
    };
    res.once?.("close", closed);
    try {
      return await contexts.run(request, () => handler(req, res));
    } finally {
      clearTimeout(deadline);
      req.removeListener?.("aborted", abort);
      res.removeListener?.("close", closed);
      console.log(JSON.stringify({
        request_id: request.request_id,
        endpoint,
        status: res.statusCode,
        duration_ms: Date.now() - request.started,
        provider_calls: request.calls,
      }));
    }
  };
}

async function fetchJson(url, options, category, timeoutMs = DEADLINES[category]) {
  const request = contexts.getStore();
  if (request) request.calls[category] += 1;
  const controller = new AbortController();
  const cancel = () => controller.abort();
  const parent = request?.controller.signal;
  parent?.addEventListener("abort", cancel, { once: true });
  if (parent?.aborted) controller.abort();
  const timer = setTimeout(cancel, timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) throw new Error(`${category}_http_${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
    parent?.removeEventListener("abort", cancel);
  }
}

// Increment and expiry validation happen in one Redis script. A lost response
// consumes a slot. We never retry automatically and never fail open.
const COUNTER_SCRIPT = `
local count = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
`;

async function rateCounter(key, windowSeconds, limit) {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) {
    if (process.env.ALLOW_IN_MEMORY_LIMITER !== "true" ||
        process.env.VERCEL === "1" || process.env.NODE_ENV === "production") {
      throw new Error("limiter_unconfigured");
    }
    const now = Date.now();
    for (const [entryKey, value] of memoryCounters) {
      if (value.expires <= now) memoryCounters.delete(entryKey);
    }
    const entry = memoryCounters.get(key) || { count: 0, expires: now + windowSeconds * 1000 };
    entry.count += 1;
    memoryCounters.set(key, entry);
    return { count: entry.count, limited: entry.count > limit };
  }
  const target = new URL(url);
  if (target.protocol !== "https:" || target.username || target.password) {
    throw new Error("limiter_configuration_invalid");
  }
  const data = await fetchJson(target.href, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(["EVAL", COUNTER_SCRIPT, "1", key, String(windowSeconds)]),
  }, "limiter");
  const [count, ttl] = Array.isArray(data?.result) ? data.result : [];
  if (!Number.isSafeInteger(count) || count < 1 ||
      !Number.isSafeInteger(ttl) || ttl < 1 || ttl > windowSeconds) {
    throw new Error("limiter_result_invalid");
  }
  return { count, limited: count > limit };
}

async function aggregatePaidLimit(ip) {
  const bucket = Math.floor(Date.now() / 3600000);
  return rateCounter(`paid:1h:${ip}:${bucket}`, 3700, 60);
}

function safeUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

module.exports = {
  canonicalOfficial,
  getClientIp,
  withRequest,
  fetchJson,
  rateCounter,
  aggregatePaidLimit,
  safeUrl,
  DEADLINES,
};
