"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

process.env.SUPABASE_URL = "https://example.supabase.co";
process.env.SUPABASE_ANON_KEY = "anon-test-key";

const lib = require("../api/_lib/transcript-search-lib");
const handler = require("../api/transcript-coverage");

function responseRecorder() {
  return {
    headers: {},
    statusCode: null,
    body: null,
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
    },
  };
}

test("coverage RPC pins official and embedding model", async () => {
  const originalFetch = global.fetch;
  let request = null;
  global.fetch = async (url, options) => {
    request = { url, options };
    return {
      ok: true,
      json: async () => [{
        speaking_turns: 45,
        meeting_count: 8,
        first_meeting_date: "2026-06-24",
        last_meeting_date: "2026-08-14",
      }],
    };
  };

  try {
    const rows = await lib.transcriptCoverageRpc({
      officialId: "cd14-official",
    });
    assert.equal(rows[0].speaking_turns, 45);
    assert.match(request.url, /\/rpc\/get_transcript_coverage$/);
    assert.deepEqual(JSON.parse(request.options.body), {
      p_official_id: "cd14-official",
      p_embedding_model: lib.EMBED_MODEL_NAME,
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test("coverage endpoint marks the lower-tail baseline as thin", async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => [{
      speaking_turns: "11",
      meeting_count: "4",
      first_meeting_date: "2026-06-24",
      last_meeting_date: "2026-08-14",
    }],
  });

  try {
    const res = responseRecorder();
    await handler(
      { method: "GET", query: { official_id: "cd9-official" } },
      res
    );
    assert.equal(res.statusCode, 200);
    assert.equal(res.body.speaking_turns, 11);
    assert.equal(res.body.meeting_count, 4);
    assert.equal(res.body.thin, true);
    assert.match(res.headers["Cache-Control"], /s-maxage=300/);
  } finally {
    global.fetch = originalFetch;
  }
});

test("coverage endpoint treats threshold values as non-thin", async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => [{
      speaking_turns: handler.MIN_TURNS_FOR_NON_THIN,
      meeting_count: handler.MIN_MEETINGS_FOR_NON_THIN,
      first_meeting_date: null,
      last_meeting_date: null,
    }],
  });

  try {
    const res = responseRecorder();
    await handler(
      { method: "GET", query: { official_id: "cd6-official" } },
      res
    );
    assert.equal(res.statusCode, 200);
    assert.equal(res.body.thin, false);
  } finally {
    global.fetch = originalFetch;
  }
});

test("coverage endpoint rejects invalid ids and non-GET methods", async () => {
  const invalid = responseRecorder();
  await handler(
    { method: "GET", query: { official_id: "../not-an-official" } },
    invalid
  );
  assert.equal(invalid.statusCode, 400);

  const wrongMethod = responseRecorder();
  await handler({ method: "POST", query: {} }, wrongMethod);
  assert.equal(wrongMethod.statusCode, 405);
  assert.equal(wrongMethod.headers.Allow, "GET");
});
