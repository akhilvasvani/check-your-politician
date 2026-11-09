"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() {
    this.children = [];
    this._text = "";
    this.hidden = false;
    this.events = {};
    this.attrs = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }

  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }

  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }

  set innerHTML(value) {
    this._text = value;
    this.children = [];
  }

  get innerHTML() {
    return this._text;
  }

  appendChild(element) {
    this.children.push(element);
    return element;
  }

  addEventListener(name, callback) {
    this.events[name] = callback;
  }

  setAttribute(name, value) {
    this.attrs[name] = value;
  }

  getAttribute(name) {
    return this.attrs[name];
  }
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function setup(official, publicComment, coverage) {
  const elements = {};
  const document = {
    getElementById(id) {
      return elements[id] ||= new Element();
    },
    createElement() {
      return new Element();
    },
  };
  const context = {
    document,
    window: { escapeHtml: String },
    console: { warn() {} },
    Date,
    AbortController,
    URL,
    Number,
    Promise,
    clearTimeout,
    setTimeout(callback, milliseconds) {
      // Skip the UI cooldown, while keeping actual request deadlines available.
      if (milliseconds > 1000 && milliseconds < 10000) return 0;
      const timer = setTimeout(callback, milliseconds);
      timer.unref?.();
      return timer;
    },
    fetch: async (url) => {
      if (url === "data/transcripts/roster.json") {
        return {
          ok: true,
          json: async () => ({ members: [{ official_id: "cd14-official" }] }),
        };
      }
      if (url.startsWith("/api/transcript-coverage")) {
        if (coverage instanceof Error) throw coverage;
        return { ok: !!coverage, json: async () => coverage };
      }
      return url === "/api/search-transcripts" ? official.promise : publicComment.promise;
    },
  };
  const script = fs.readFileSync(path.resolve(__dirname, "../../js/transcript-search.js"), "utf8");
  vm.runInNewContext(script, context);
  return { elements, document, context };
}

const row = {
  video_id: "MBjio010l60",
  meeting_date: "2026-07-01",
  start_sec: 12,
  text: "Housing testimony.",
  similarity: 0.7,
  resolved_name: "Test speaker",
};
const success = { ok: true, json: async () => ({ results: [row] }) };
const empty = { ok: true, json: async () => ({ results: [] }) };

async function ready(harness) {
  await harness.context.window.initTranscriptSearch("cd14-official", { name: "Ysabel Jurado" });
  await Promise.resolve();
  harness.document.getElementById("transcript-search-input").value = "housing";
  harness.document.getElementById("transcript-search-include-public").checked = true;
}

function submit(harness) {
  return harness.elements["transcript-search-form"].events.submit({ preventDefault() {} });
}

for (const failed of ["official", "public"]) {
  test(`preserves the successful source after ${failed} HTTP failure`, async () => {
    const official = deferred();
    const publicComment = deferred();
    const harness = setup(official, publicComment);
    await ready(harness);
    const done = submit(harness);
    const failedRequest = failed === "official" ? official : publicComment;
    const successfulRequest = failed === "official" ? publicComment : official;
    failedRequest.resolve({ ok: false, json: async () => ({ error: "Source unavailable." }) });
    successfulRequest.resolve(success);
    await done;

    const officialResults = harness.elements["transcript-search-results"];
    const publicResults = harness.elements["transcript-search-public-results"];
    const successfulResults = failed === "official" ? publicResults : officialResults;
    const failedResults = failed === "official" ? officialResults : publicResults;
    assert.match(successfulResults.textContent, /Housing testimony/);
    assert.match(failedResults.textContent, /unavailable/);
  });
}

test("coverage failure keeps incompleteness disclosure and unavailable count", async () => {
  const harness = setup(deferred(), deferred(), new Error("outage"));
  await ready(harness);
  await Promise.resolve();
  const element = harness.elements["transcript-search-coverage"];
  assert.equal(element.hidden, false);
  assert.match(element.textContent, /not a complete public record/);
  assert.match(element.textContent, /unavailable/);
  assert.doesNotMatch(element.textContent, /0 speaking/);
});

test("empty plus failed source never reports both sources had no matches", async () => {
  const official = deferred();
  const publicComment = deferred();
  const harness = setup(official, publicComment);
  await ready(harness);
  const done = submit(harness);
  official.resolve(empty);
  publicComment.resolve({ ok: false, json: async () => ({ error: "Public comment unavailable." }) });
  await done;
  assert.match(harness.elements["transcript-search-public-results"].textContent, /unavailable/);
  assert.equal(harness.elements["transcript-search-empty"].hidden, true);
});

for (const first of ["official", "public"]) {
  for (const failed of ["official", "public", "both"]) {
    test(`settles ${failed} network rejection with ${first} completing first`, async () => {
      const official = deferred();
      const publicComment = deferred();
      const harness = setup(official, publicComment);
      await ready(harness);
      const unhandled = [];
      const listener = (reason) => unhandled.push(reason);
      process.on("unhandledRejection", listener);
      try {
        const done = submit(harness);
        function settle(source) {
          const request = source === "official" ? official : publicComment;
          if (failed === source || failed === "both") request.reject(new Error("offline"));
          else request.resolve(success);
        }
        settle(first);
        await new Promise((resolve) => setImmediate(resolve));
        settle(first === "official" ? "public" : "official");
        await done;
        await new Promise((resolve) => setImmediate(resolve));
        assert.equal(unhandled.length, 0);
        for (const source of ["official", "public"]) {
          const id = source === "official" ? "transcript-search-results" : "transcript-search-public-results";
          const expected = failed === source || failed === "both" ? /unavailable/ : /Housing testimony/;
          assert.match(harness.elements[id].textContent, expected);
        }
      } finally {
        process.removeListener("unhandledRejection", listener);
      }
    });
  }
}

test("malformed source payload is unavailable, never a no-match", async () => {
  const official = deferred();
  const publicComment = deferred();
  const harness = setup(official, publicComment);
  await ready(harness);
  const done = submit(harness);
  official.resolve({ ok: true, json: async () => ({}) });
  publicComment.resolve(success);
  await done;
  assert.match(harness.elements["transcript-search-results"].textContent, /unavailable/);
});

test("similarity is a raw score with explanatory label, never a percentage", async () => {
  const official = deferred();
  const publicComment = deferred();
  const harness = setup(official, publicComment);
  await ready(harness);
  const done = submit(harness);
  official.resolve(success);
  publicComment.resolve(empty);
  await done;
  const element = harness.elements["transcript-search-results"];
  assert.match(element.textContent, /similarity 0.70/);
  assert.doesNotMatch(element.textContent, /%/);
});

test("partial failures and completion are announced through the live status", async () => {
  const official = deferred();
  const publicComment = deferred();
  const harness = setup(official, publicComment);
  await ready(harness);
  const done = submit(harness);
  official.resolve(success);
  publicComment.reject(new Error("unavailable"));
  await done;
  const status = harness.elements["transcript-search-status"];
  assert.equal(status.hidden, false);
  assert.match(status.textContent, /Official transcript search returned 1/);
  assert.match(status.textContent, /Public comment search is unavailable/);
});
