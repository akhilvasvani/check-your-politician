"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const officialHandler = require("../../api/search-transcripts");
const publicHandler = require("../../api/search-public-comment");
const askHandler = require("../../api/ask-official");
const lib = require("../../api/_lib/transcript-search-lib");
function response() {
  return {
    headers: {},
    setHeader(name, value) {
      this.headers[name] = value;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(body) {
      this.body = body;
      return this;
    }
  };
}
function req(body) {
  return {
    method: "POST", headers: {}, socket: { remoteAddress: "127.0.0.1" }, body
  };
}
const context = {
  id: "cd14-official", resolved_official_id: "cd14-official"
};
for (const [name, handler] of [["official", officialHandler], ["public", publicHandler]]) {
  test(`${name} rejects oversized original query before external calls`, async () => {
    const original = global.fetch;
    let calls = 0;
    global.fetch = async () => {
      calls++;
      throw new Error("Unexpected external call");
    };
    try {
      const res = response();
      await handler(req({ query: " x".repeat(201), official: context }), res);
      assert.equal(res.statusCode, 400);
      assert.equal(calls, 0);
    } finally {
      global.fetch = original;
    }
  });
  test(`${name} rejects malformed, impossible and reversed supplied bounds`, async () => {
    const original = global.fetch;
    let calls = 0;
    global.fetch = async () => {
      calls++;
      throw new Error("Unexpected external call");
    };
    try {
      const invalidBounds = [
        { date_from: "tomorrow" },
        { date_from: "2026-02-30" },
        { date_to: 12 },
        { date_from: "2026-11-07", date_to: "2026-11-01" },
      ];
      for (const dates of invalidBounds) {
        const res = response();
        await handler(req({ query: "housing", official: context, ...dates }), res);
        assert.equal(res.statusCode, 400, JSON.stringify(dates));
      }
      assert.equal(calls, 0);
    } finally {
      global.fetch = original;
    }
  });
}
test("official search rejects canonical identity mismatch", async () => {
  const res = response();
  await officialHandler(req({
    query: "housing", official: { id: "cd14-official", resolved_official_id: "cd11-official" }
  }), res);
  assert.equal(res.statusCode, 400);
});

test("read RPC cannot fall back to service role", async () => {
  const oldAnon = process.env.SUPABASE_ANON_KEY;
  const oldUrl = process.env.SUPABASE_URL;
  const oldService = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const original = global.fetch;
  delete process.env.SUPABASE_ANON_KEY;
  process.env.SUPABASE_URL = "https://example.supabase.co";
  process.env.SUPABASE_SERVICE_ROLE_KEY = "secret-write-token";
  let calls = 0;
  global.fetch = async () => {
    calls++;
    return { ok: true, json: async () => [] };
  };
  try {
    await assert.rejects(lib.transcriptCoverageRpc({ officialId: "cd14-official" }));
    assert.equal(calls, 0);
  } finally {
    global.fetch = original;
    for (const [k, v] of Object.entries({
      SUPABASE_ANON_KEY: oldAnon, SUPABASE_URL: oldUrl, SUPABASE_SERVICE_ROLE_KEY: oldService
    })) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
});

test("calendar validation handles leap years", () => {
  assert.equal(lib.isIsoDate("2024-02-29"), true);
  assert.equal(lib.isIsoDate("2026-02-29"), false);
  assert.equal(lib.isIsoDate("2026-04-31"), false);
});
const safety = require("../../api/_lib/request-safety");
const coverageHandler = require("../../api/transcript-coverage");
function withEnv(values, run) {
  const before = Object.fromEntries(Object.keys(values).map(k => [k, process.env[k]]));
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  return Promise.resolve().then(run).finally(() => {
    for (const [key, value] of Object.entries(before)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });
}
const unconfiguredLimiter = {
  KV_REST_API_URL: undefined,
  KV_REST_API_TOKEN: undefined,
  UPSTASH_REDIS_REST_URL: undefined,
  UPSTASH_REDIS_REST_TOKEN: undefined,
  ALLOW_IN_MEMORY_LIMITER: undefined,
};
const providerEnv = {
  PERPLEXITY_API_KEY: "fixture-key",
  SUPABASE_URL: "https://fixture.supabase.co",
  SUPABASE_ANON_KEY: "sb_publishable_test_fixture",
  KV_REST_API_URL: "https://limiter.test",
  KV_REST_API_TOKEN: "fixture-token",
};

function mockProvider(calls) {
  return async (url, options) => {
    calls.push({ url, options });
    if (url.startsWith("https://limiter.test")) return {
      ok: true, json: async () => ({ result: [1, 60] })
    };
    if (url.endsWith("/embeddings")) return {
      ok: true, json: async () => ({
        data: [{ embedding: Buffer.alloc(1024, 1).toString("base64") } ]
      })
    };
    if (url.includes("/rpc/")) return { ok: true, json: async () => [] };
    return {
      ok: true, json: async () => ({
        choices: [{
          message: {
            content: JSON.stringify({ in_scope: true, answer: "A sourced response." })
          }
        }], citations: ["javascript:alert(1)", "https://clerk.lacity.gov/records", "data:text/html,test"]
      })
    };
  };
}
test("canonical Ask-AI ignores forged context and filters citation schemes", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  const calls = [];
  global.fetch = mockProvider(calls);
  try {
    const res = response();
    await askHandler(req({
      question: "Housing policy?", official: {
        id: "cd14-official", name: "Forged Identity", title: "INJECTED INSTRUCTION", party: "FORGED"
      }
    }), res);
    assert.equal(res.statusCode, 200);
    const call = calls.find(c => c.url.endsWith("chat/completions"));
    const prompt = JSON.parse(call.options.body).messages[0].content;
    assert.match(prompt, /Ysabel Jurado/);
    assert.doesNotMatch(prompt, /Forged|INJECTED|FORGED/);
    assert.equal(res.body.citations.length, 1);
    assert.match(res.headers["X-Request-ID"], /^[a-f0-9-]{36}$/);
  } finally {
    global.fetch = original;
  }
}));

test("Ask-AI rejects unsupported IDs before paid calls", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls++;
    throw new Error("unexpected");
  };
  try {
    for (const id of ["unknown", "cd99-official", "cd14-official-extra", null]) {
      const res = response();
      await askHandler(req({
        question: "housing", official: { id }
      }), res);
      assert.equal(res.statusCode, 400);
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = original;
  }
}));

test("both kill switches stop provider and limiter calls", () => withEnv({
  ...providerEnv, ASK_AI_DISABLED: "true", TRANSCRIPT_SEARCH_DISABLED: "true"
}, async () => {
  const original = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls++;
    throw new Error("unexpected");
  };
  try {
    for (const handler of [askHandler, officialHandler, publicHandler]) {
      const res = response();
      await handler(req({ question: "housing", query: "housing", official: context }), res);
      assert.equal(res.statusCode, 503);
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = original;
  }
}));

test("missing durable limiter fails closed for every paid handler", () => withEnv({
  ...providerEnv, ...unconfiguredLimiter
}, async () => {
  const original = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls++;
    throw new Error("unexpected");
  };
  try {
    for (const handler of [askHandler, officialHandler, publicHandler]) {
      const res = response();
      await handler(req({ question: "housing", query: "housing", official: context }), res);
      assert.equal(res.statusCode, 503);
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = original;
  }
}));

test("production rejects explicit memory fallback", () => withEnv({
  ...unconfiguredLimiter, ALLOW_IN_MEMORY_LIMITER: "true", VERCEL: "1"
}, async () => {
  await assert.rejects(safety.rateCounter("test", 60, 5));
}));

test("limiter verifies count and expiry and uses a single atomic EVAL", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  let request;
  try {
    for (const result of [[NaN, 60], [1, -1], [1, 0], [1, 61], ["1", 60], null]) {
      global.fetch = async () => ({
        ok: true, json: async () => ({ result })
      });
      await assert.rejects(safety.rateCounter("test", 60, 5));
    }
    global.fetch = async (url, options) => {
      request = { url, options };
      return {
        ok: true, json: async () => ({ result: [6, 60] })
      };
    };
    assert.equal((await safety.rateCounter("test", 60, 5)).limited, true);
    const command = JSON.parse(request.options.body);
    assert.equal(command[0], "EVAL");
    assert.match(command[1], /INCR/);
    assert.match(command[1], /EXPIRE/);
    assert.match(command[1], /TTL/);
    assert.equal(command[3], "test");
  } finally {
    global.fetch = original;
  }
}));

test("all paid endpoints share a client ceiling across official IDs", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true, json: async () => ({ result: [61, 100] })
    };
  };
  try {
    const requests = [
      [askHandler, "cd14-official"],
      [askHandler, "cd11-official"],
      [officialHandler, "cd14-official"],
      [publicHandler, "cd14-official"],
    ];
    for (const [handler, id] of requests) {
      const res = response();
      await handler(req({
        question: "housing", query: "housing", official: { id, resolved_official_id: id }
      }), res);
      assert.equal(res.statusCode, 429);
    }
    assert.equal(calls.length, 4);
    const keys = calls.map(c => JSON.parse(c.options.body)[3]);
    assert.equal(new Set(keys).size, 1);
    assert.match(keys[0], /^paid:1h:/);
  } finally {
    global.fetch = original;
  }
}));

test("limiter outage consumes no paid call and has no retry", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls++;
    throw new Error("outage");
  };
  try {
    const res = response();
    await officialHandler(req({ query: "housing", official: context }), res);
    assert.equal(res.statusCode, 503);
    assert.equal(calls, 1);
  } finally {
    global.fetch = original;
  }
}));

test("provider JSON body deadline aborts without retry", async () => {
  const original = global.fetch;
  let calls = 0;
  global.fetch = async (_url, options) => {
    calls++;
    return {
      ok: true, json: () => new Promise((resolve, reject) => options.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true }))
    };
  };
  try {
    await assert.rejects(safety.fetchJson("https://provider.test", {}, "embedding", 10), /aborted/);
    assert.equal(calls, 1);
  } finally {
    global.fetch = original;
  }
});

test("proxy header is trusted only on Vercel", () => withEnv({
  VERCEL: undefined
}, async () => {
  const request = {
    headers: { "x-forwarded-for": "1.2.3.4", "x-vercel-forwarded-for": "5.6.7.8" }, socket: { remoteAddress: "127.0.0.1" }
  };
  assert.equal(safety.getClientIp(request), "127.0.0.1");
  process.env.VERCEL = "1";
  assert.equal(safety.getClientIp(request), "5.6.7.8");
  request.headers["x-vercel-forwarded-for"] = "5.6.7.8, 9.1.2.3";
  assert.equal(safety.getClientIp(request), "unknown");
}));

test("missing or malformed coverage aggregate never becomes zero", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  try {
    for (const rows of [[], null, [{}], [{ speaking_turns: null, meeting_count: null }], [{ speaking_turns: -1, meeting_count: 2 }]]) {
      global.fetch = async () => ({ ok: true, json: async () => rows });
      const res = response();
      await coverageHandler({
        method: "GET", query: { official_id: "cd14-official" }
      }, res);
      assert.equal(res.statusCode, 502);
      assert.equal(res.body.speaking_turns, undefined);
    }
  } finally {
    global.fetch = original;
  }
}));

test("valid zero coverage stays distinct from unavailable", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  global.fetch = async () => ({
    ok: true, json: async () => [{ speaking_turns: 0, meeting_count: 0 }]
  });
  try {
    const res = response();
    await coverageHandler({
      method: "GET", query: { official_id: "cd14-official" }
    }, res);
    assert.equal(res.statusCode, 200);
    assert.equal(res.body.speaking_turns, 0);
    assert.equal(res.body.thin, true);
  } finally {
    global.fetch = original;
  }
}));

test("read credential role rejects a service JWT in the anon field", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls++;
  };
  process.env.SUPABASE_ANON_KEY = "header." + Buffer.from(JSON.stringify({ role: "service_role" })).toString("base64url") + ".signature";
  try {
    await assert.rejects(lib.transcriptCoverageRpc({ officialId: "cd14-official" }));
    assert.equal(calls, 0);
  } finally {
    global.fetch = original;
  }
}));

test("invalid embedding dimension fails before database read", () => withEnv(providerEnv, async () => {
  const original = global.fetch;
  const calls = [];
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith("/embeddings")) return {
      ok: true, json: async () => ({
        data: [{ embedding: Buffer.alloc(2).toString("base64") } ]
      })
    };
    return {
      ok: true, json: async () => ({ result: [1, 60] })
    };
  };
  try {
    const res = response();
    await officialHandler(req({ query: "housing", official: context }), res);
    assert.equal(res.statusCode, 502);
    assert.equal(calls.some(c => c.url.includes("/rpc/")), false);
  } finally {
    global.fetch = original;
  }
}));

test("blank and boolean coverage counts are unavailable", () => withEnv(providerEnv, async () => {
  const originalFetch = global.fetch;
  try {
    for (const value of ["", " ", false, true]) {
      global.fetch = async () => ({
        ok: true, json: async () => [{ speaking_turns: value, meeting_count: 1 }]
      });
      const res = response();
      await coverageHandler({
        method: "GET", query: { official_id: "cd14-official" }
      }, res);
      assert.equal(res.statusCode, 502);
    }
  } finally {
    global.fetch = originalFetch;
  }
}));

test("year zero is rejected before reaching PostgreSQL", () => {
  assert.equal(lib.isIsoDate("0000-01-01"), false);
});

test("zero magnitude or malformed base64 embeddings cannot reach database", () => withEnv(providerEnv, async () => {
  const originalFetch = global.fetch;
  try {
    for (const embedding of [Buffer.alloc(1024).toString("base64"), "invalid !".repeat(200)]) {
      global.fetch = async () => ({
        ok: true, json: async () => ({
          data: [{ embedding }]
        })
      });
      await assert.rejects(lib.embedQuery("housing"));
    }
  } finally {
    global.fetch = originalFetch;
  }
}));

test("wrong speaker or public-comment attribution is never returned as official evidence", () => withEnv(providerEnv, async () => {
  const originalFetch = global.fetch;
  try {
    for (const handler of [officialHandler, publicHandler]) {
      const mock = mockProvider([]);
      global.fetch = async (url, options) => {
        if (url.includes("/rpc/")) return {
          ok: true, json: async () => [{
            text: "Statement", resolved_official_id: "cd11-official", resolved_role: "councilmember"
          }]
        };
        return mock(url, options);
      };
      const res = response();
      await handler(req({ query: "housing", official: context }), res);
      assert.equal(res.statusCode, 502);
      assert.equal(res.body.results, undefined);
    }
  } finally {
    global.fetch = originalFetch;
  }
}));

test("invalid read configuration consumes no limiter, embedding or database request", () => withEnv(providerEnv, async () => {
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    throw new Error("Unexpected external request");
  };
  try {
    const serviceJwt = "header." + Buffer.from(JSON.stringify({ role: "service_role" })).toString("base64url") + ".signature";
    for (const credential of [undefined, "opaque-malformed-key", "sb_publishable_", "sb_secret_example", serviceJwt]) {
      if (credential === undefined) delete process.env.SUPABASE_ANON_KEY;
      else process.env.SUPABASE_ANON_KEY = credential;
      for (const handler of [officialHandler, publicHandler]) {
        const res = response();
        await handler(req({ query: "housing", official: context }), res);
        assert.equal(res.statusCode, 503);
      }
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = originalFetch;
  }
}));

test("publishable read keys use apikey while legacy anonymous JWTs retain bearer authentication", () => withEnv(providerEnv, async () => {
  const originalFetch = global.fetch;
  const requests = [];
  global.fetch = async (url, options) => {
    requests.push({ url, options });
    return { ok: true, json: async () => [] };
  };
  try {
    await lib.transcriptCoverageRpc({ officialId: "cd14-official" });
    assert.equal(requests[0].options.headers.apikey, "sb_publishable_test_fixture");
    assert.equal(requests[0].options.headers.Authorization, undefined);
    const header = Buffer.from(JSON.stringify({ typ: "JWT", alg: "HS256" })).toString("base64url");
    const claims = Buffer.from(JSON.stringify({ role: "anon" })).toString("base64url");
    process.env.SUPABASE_ANON_KEY = `${header}.${claims}.fixture_signature`;
    await lib.transcriptCoverageRpc({ officialId: "cd14-official" });
    assert.equal(requests[1].options.headers.Authorization, `Bearer ${process.env.SUPABASE_ANON_KEY}`);
  } finally {
    global.fetch = originalFetch;
  }
}));
