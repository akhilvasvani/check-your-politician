// Tests for js/freshness.js. Node built-ins only (node:test, node:assert);
// run from la-money-votes/ with:  node --test tests/js/
// Local-only: not part of CI until a workflow change adds it.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..", "..");
const MODULE = path.join(ROOT, "js", "freshness.js");
const F = require(MODULE);

const GENERATED = "2026-10-18T12:00:00+00:00";

function funding(overrides) {
  return Object.assign(
    {
      source_type: "automated_api",
      status: "ok",
      attempted_at: "2026-10-18T12:00:00+00:00",
      last_success_at: "2026-10-18",
      source_retrieved_at: "2026-10-18T11:59:00+00:00",
      latest_reporting_period_end: "2026-09-30",
      displayed_donor_count: 30,
      matched_row_count: 412,
      donor_count: 30,
      warning_codes: ["EMPLOYER_OCCUPATION_UNAVAILABLE"],
    },
    overrides || {}
  );
}

function record(overrides) {
  return Object.assign(
    {
      source_type: "manual_curated",
      status: "ok",
      attempted_at: "2026-10-18T12:00:00+00:00",
      last_success_at: "2026-10-18",
      reviewed_through: "2026-10-01",
      item_count: 12,
      warning_codes: [],
    },
    overrides || {}
  );
}

function doc(entry, extra) {
  return Object.assign(
    { schema_version: "2.0", generated_at: GENERATED, officials: { "cd1-official": entry } },
    extra || {}
  );
}

function describe(fundingEntry, recordEntry, extra) {
  return F.describeFreshness(doc({ funding: fundingEntry, record: recordEntry }, extra), "cd1-official");
}

// Fixed fixture: a v1-migrated entry with unknown funding provenance.
const MIGRATED_FIXTURE = {
  funding: {
    source_type: "unknown",
    status: "ok",
    attempted_at: "2026-10-05T21:59:15+00:00",
    last_success_at: "2026-10-05",
    source_retrieved_at: null,
    latest_reporting_period_end: null,
    displayed_donor_count: 30,
    matched_row_count: null,
    donor_count: 30,
    warning_codes: ["LATEST_REPORTING_PERIOD_UNKNOWN", "SOURCE_RETRIEVED_AT_UNKNOWN", "SOURCE_TYPE_UNKNOWN"],
  },
  record: {
    source_type: "manual_curated",
    status: "ok",
    attempted_at: "2026-10-05T21:59:15+00:00",
    last_success_at: "2026-10-05",
    reviewed_through: null,
    item_count: 12,
    warning_codes: ["REVIEW_DATE_MISSING"],
  },
};

// --- Minimal fake DOM: records children, forbids innerHTML -----------------

class FakeElement {
  constructor(ownerDocument, tag) {
    this.ownerDocument = ownerDocument;
    this.tagName = tag;
    this.children = [];
    this.hidden = true;
    this._text = "";
  }
  get firstChild() {
    return this.children[0] || null;
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
  removeChild(child) {
    const i = this.children.indexOf(child);
    if (i < 0) throw new Error("not a child");
    this.children.splice(i, 1);
    return child;
  }
  set textContent(value) {
    this._text = String(value);
  }
  get textContent() {
    return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text;
  }
  set innerHTML(_value) {
    throw new Error("innerHTML must not be used");
  }
  get innerHTML() {
    throw new Error("innerHTML must not be used");
  }
}

class FakeDocument {
  constructor(ids) {
    this.elements = {};
    (ids || ["funding-freshness", "record-freshness"]).forEach((id) => {
      this.elements[id] = new FakeElement(this, "div");
    });
  }
  createElement(tag) {
    return new FakeElement(this, tag);
  }
  getElementById(id) {
    return this.elements[id] || null;
  }
}

function lines(el) {
  return el.children.map((c) => c.textContent);
}

function jsonResponse(data) {
  return { ok: true, json: () => Promise.resolve(data) };
}

function quietly(fn) {
  const original = console.warn;
  const warnings = [];
  console.warn = (...args) => warnings.push(args);
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      console.warn = original;
    })
    .then((value) => ({ value, warnings }));
}

// --- Dates ------------------------------------------------------------------

test("date-only and UTC timestamp formatting", () => {
  assert.equal(F.freshDay("2026-10-01"), "Oct 1, 2026");
  assert.equal(F.freshDay("2024-02-29"), "Feb 29, 2024");
  assert.equal(F.freshDay("2000-02-29"), "Feb 29, 2000");
  assert.equal(F.freshTimestamp("2026-10-05T23:30:00+00:00"), "Oct 5, 2026, 23:30 UTC");
  assert.equal(F.freshTimestamp("2026-10-05T00:00:00Z"), "Oct 5, 2026, 00:00 UTC");
});

test("impossible dates and malformed timestamps are rejected", () => {
  for (const bad of ["2026-02-30", "2025-02-29", "1900-02-29", "2026-13-01", "2026-00-10", "2026-04-31",
    "10/05/2026", "2026-10-5", "2026-10-05T00:00:00+00:00", "", " 2026-10-05", 20261005, null, undefined, {}, []]) {
    assert.equal(F.freshDay(bad), null, `freshDay(${JSON.stringify(bad)})`);
  }
  for (const bad of ["2026-10-05T24:00:00+00:00", "2026-10-05T23:60:00+00:00", "2026-10-05T23:59:60+00:00",
    "2026-10-05T12:00:00-07:00", "2026-10-05T12:00:00+01:00", "2026-10-05T12:00:00", "2026-10-05T12:00+00:00",
    "2026-10-05T12:00:00.123+00:00", "2026-02-30T12:00:00+00:00", "2026-10-05", "", null, 1760000000]) {
    assert.equal(F.freshTimestamp(bad), null, `freshTimestamp(${JSON.stringify(bad)})`);
  }
});

test("dates do not shift across reader timezones", () => {
  const script =
    `const F=require(${JSON.stringify(MODULE)});` +
    `process.stdout.write(JSON.stringify([F.freshDay("2026-10-01"),F.freshTimestamp("2026-10-05T23:30:00+00:00"),` +
    `F.freshDay("2026-01-01"),F.freshTimestamp("2026-12-31T23:59:59Z")]))`;
  for (const tz of ["UTC", "America/Los_Angeles", "Pacific/Kiritimati", "Pacific/Pago_Pago"]) {
    const r = spawnSync(process.execPath, ["-e", script], { env: Object.assign({}, process.env, { TZ: tz }), encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
    assert.deepEqual(JSON.parse(r.stdout), ["Oct 1, 2026", "Oct 5, 2026, 23:30 UTC", "Jan 1, 2026", "Dec 31, 2026, 23:59 UTC"], tz);
  }
});

// --- Funding ----------------------------------------------------------------

test("funding ok with every field", () => {
  assert.deepEqual(describe(funding(), record()).funding, [
    "Last successful build: Oct 18, 2026.",
    "Contribution data retrieved from the source: Oct 18, 2026, 11:59 UTC.",
    "Latest reporting period represented ends Sep 30, 2026.",
  ]);
});

test("funding failed and skipped, with and without a previous success", () => {
  const failed = describe(
    funding({ status: "failed", last_success_at: "2026-09-01", warning_codes: ["BUILD_FAILED_PREVIOUS_DATA_SERVED"] }),
    record()
  ).funding;
  assert.equal(failed[0], "The latest build attempt (Oct 18, 2026, 12:00 UTC) failed.");
  assert.equal(failed[1], "Showing data from the last successful build on Sep 1, 2026.");

  const skipped = describe(funding({ status: "skipped", last_success_at: null, warning_codes: ["SOURCE_UNAVAILABLE"] }), record()).funding;
  assert.equal(skipped[0], "The latest build attempt (Oct 18, 2026, 12:00 UTC) was skipped. The source was unavailable for that attempt.");
  assert.equal(skipped[1], "No successful build is recorded.");
});

test("skipped without SOURCE_UNAVAILABLE does not claim the source was unavailable", () => {
  const skipped = describe(funding({ status: "skipped", warning_codes: ["NO_COMMITTEE_CONFIGURED"] }), record()).funding;
  assert.equal(skipped[0], "The latest build attempt (Oct 18, 2026, 12:00 UTC) was skipped.");
  assert.ok(skipped.every((l) => !/unavailable/i.test(l)), skipped.join(" | "));
});

test("no build timestamp is described as an 'update'", () => {
  const all = [
    ...describe(funding(), record()).funding,
    ...describe(funding({ status: "failed" }), record({ status: "skipped" })).funding,
    ...describe(funding(), record({ status: "skipped" })).record,
  ];
  assert.ok(all.every((l) => !/\bupdate/i.test(l)), all.join(" | "));
});

test("retrieval time unknown for api, downloaded-file and unknown sources", () => {
  const api = describe(funding({ source_retrieved_at: null, warning_codes: ["SOURCE_RETRIEVED_AT_UNKNOWN"] }), record()).funding;
  assert.equal(api[1], "Contribution data retrieval time: unknown.");
  const csv = describe(funding({ source_type: "automated_csv", source_retrieved_at: null }), record()).funding;
  assert.equal(csv[1], "Contribution data came from a downloaded file; retrieval time not recorded.");
  const unknown = describe(
    funding({ source_type: "unknown", source_retrieved_at: null, latest_reporting_period_end: null, matched_row_count: null }),
    record()
  ).funding;
  assert.equal(unknown[1], "Contribution data retrieval time: unknown.");
});

test("retrieval time and reporting period stay on separate lines", () => {
  const out = describe(funding(), record()).funding;
  const retrieval = out.filter((l) => l.startsWith("Contribution data"));
  const period = out.filter((l) => l.startsWith("Latest reporting period"));
  assert.equal(retrieval.length, 1);
  assert.equal(period.length, 1);
  assert.ok(!retrieval[0].includes("reporting period") && !period[0].includes("retrieved"));
});

test("reporting period present or unknown, never a completeness claim", () => {
  assert.equal(describe(funding(), record()).funding.at(-1), "Latest reporting period represented ends Sep 30, 2026.");
  const unknown = describe(funding({ latest_reporting_period_end: null }), record()).funding;
  assert.equal(unknown.at(-1), "Latest reporting period represented: unknown.");
  for (const l of [...describe(funding(), record()).funding, ...unknown]) {
    assert.ok(!/complete|coverage|through/i.test(l), l);
  }
});

test("donor-cache and supporting-statements cache fallbacks are distinct", () => {
  const donor = describe(funding({ warning_codes: ["SOURCE_CACHE_FALLBACK"] }), record()).funding;
  assert.ok(donor.includes("These donors came from a saved copy of the source and may be older than the build date."));
  assert.ok(!donor.some((l) => l.startsWith("Filed-statement links")));

  const supporting = describe(funding({ warning_codes: ["SUPPORTING_SOURCE_CACHE_FALLBACK"] }), record()).funding;
  assert.ok(supporting.includes("Filed-statement links came from a saved copy of a supporting source; donor data is not affected."));
  assert.ok(!supporting.some((l) => l.startsWith("These donors came from a saved copy")), supporting.join(" | "));
});

test("unknown and malformed warning lists are ignored safely", () => {
  const base = describe(funding(), record()).funding;
  for (const codes of [["SOMETHING_NEW"], "SOURCE_CACHE_FALLBACK", null, undefined, 7, {}, [["SOURCE_CACHE_FALLBACK"]],
    [{ code: "SOURCE_UNAVAILABLE" }], [null, 3, ["SOURCE_UNAVAILABLE"]]]) {
    assert.deepEqual(describe(funding({ warning_codes: codes }), record()).funding, base, JSON.stringify(codes));
  }
  const skipped = describe(funding({ status: "skipped", warning_codes: [["SOURCE_UNAVAILABLE"], { SOURCE_UNAVAILABLE: true }] }), record()).funding;
  assert.equal(skipped[0], "The latest build attempt (Oct 18, 2026, 12:00 UTC) was skipped.");
});

test("fixed fixture: unknown funding provenance wording", () => {
  const out = F.describeFreshness(
    { schema_version: "2.0", generated_at: "2026-10-05T21:59:15+00:00", officials: { "mayor-bass": MIGRATED_FIXTURE } },
    "mayor-bass"
  );
  assert.deepEqual(out.funding, [
    "Last successful build: Oct 5, 2026.",
    "Contribution data retrieval time: unknown.",
    "Latest reporting period represented: unknown.",
  ]);
  assert.deepEqual(out.record, [
    "Last successful build: Oct 5, 2026.",
    "No human review date is recorded.",
    F.CURATED_SAMPLE,
  ]);
});

// --- Record -----------------------------------------------------------------

test("record with a human review date", () => {
  assert.deepEqual(describe(funding(), record()).record, [
    "Last successful build: Oct 18, 2026.",
    "Human-reviewed through Oct 1, 2026: a maintainer checked this project's official sources for actions through that date.",
    "These public actions are a curated sample, not a complete voting history.",
  ]);
});

test("curated-sample disclaimer appears with a null review date and in the fallback", () => {
  const out = describe(funding(), record({ reviewed_through: null, warning_codes: ["REVIEW_DATE_MISSING"] })).record;
  assert.equal(out[1], "No human review date is recorded.");
  assert.equal(out.at(-1), "These public actions are a curated sample, not a complete voting history.");
  assert.deepEqual(F.recordLinesOrFallback(null), [F.FALLBACK, F.CURATED_SAMPLE]);
  assert.deepEqual(F.fundingLinesOrFallback(null), [F.FALLBACK]);
});

test("funding and record are independent", () => {
  const a = describe(funding({ status: "failed" }), record());
  assert.match(a.funding[0], /failed/);
  assert.equal(a.record[0], "Last successful build: Oct 18, 2026.");
  const b = describe(funding(), record({ status: "failed", last_success_at: "2026-09-02" }));
  assert.equal(b.funding[0], "Last successful build: Oct 18, 2026.");
  assert.match(b.record[0], /failed/);
});

test("one bad dataset alongside one good dataset", () => {
  const badFunding = describe(funding({ status: "exploded" }), record());
  assert.equal(badFunding.funding, null);
  assert.ok(Array.isArray(badFunding.record));
  const badRecord = describe(funding(), record({ reviewed_through: "2026-02-30" }));
  assert.ok(Array.isArray(badRecord.funding));
  assert.equal(badRecord.record, null);
  const missing = F.describeFreshness(doc({ funding: funding() }), "cd1-official");
  assert.ok(Array.isArray(missing.funding));
  assert.equal(missing.record, null);
});

test("status must be an exact own string, not an inherited name or array", () => {
  for (const bad of ["toString", "constructor", "__proto__", "hasOwnProperty", ["ok"], ["failed"], "OK", " ok", 1, null, undefined, {}]) {
    const label = JSON.stringify(bad) === undefined ? "undefined" : JSON.stringify(bad);
    const f = describe(funding({ status: bad }), record());
    assert.equal(f.funding, null, `funding status ${label}`);
    assert.ok(Array.isArray(f.record), `record kept for funding status ${label}`);
    const r = describe(funding(), record({ status: bad }));
    assert.equal(r.record, null, `record status ${label}`);
    assert.ok(Array.isArray(r.funding), `funding kept for record status ${label}`);
  }
  // JSON-parsed "__proto__" is an own data property, as in a real fetch.
  const parsed = JSON.parse(JSON.stringify(doc({ funding: funding(), record: record() })).replace(/"status":"ok"/, '"status":"__proto__"'));
  const out = F.describeFreshness(parsed, "cd1-official");
  assert.equal(out.funding, null);
  assert.ok(Array.isArray(out.record));
});

test("source_type must match the dataset exactly", () => {
  for (const bad of ["manual_curated", "Automated_API", "toString", "__proto__", ["automated_api"], null, undefined, 1]) {
    const label = JSON.stringify(bad) === undefined ? "undefined" : JSON.stringify(bad);
    const f = describe(funding({ source_type: bad }), record());
    assert.equal(f.funding, null, `funding source_type ${label}`);
    assert.ok(Array.isArray(f.record));
  }
  for (const bad of ["automated_api", "automated_csv", "unknown", "toString", ["manual_curated"], null, undefined]) {
    const label = JSON.stringify(bad) === undefined ? "undefined" : JSON.stringify(bad);
    const r = describe(funding(), record({ source_type: bad }));
    assert.equal(r.record, null, `record source_type ${label}`);
    assert.ok(Array.isArray(r.funding));
  }
  for (const ok of ["automated_api", "automated_csv", "unknown"]) {
    const nulls = ok === "automated_api" ? {} : { source_retrieved_at: null };
    const extra = ok === "unknown" ? { latest_reporting_period_end: null, matched_row_count: null } : {};
    assert.ok(Array.isArray(describe(funding(Object.assign({ source_type: ok }, nulls, extra)), record()).funding), ok);
  }
});

test("funding provenance combinations the contract prohibits fall back without repair", () => {
  const ts = "2026-10-18T11:59:00+00:00";
  const unknownBase = { source_type: "unknown", source_retrieved_at: null, latest_reporting_period_end: null, matched_row_count: null };
  const cases = [
    { source_type: "automated_csv", source_retrieved_at: ts },
    Object.assign({}, unknownBase, { source_retrieved_at: ts }),
    Object.assign({}, unknownBase, { latest_reporting_period_end: "2026-09-30" }),
    Object.assign({}, unknownBase, { matched_row_count: 412 }),
    Object.assign({}, unknownBase, { matched_row_count: 0 }),
  ];
  for (const overrides of cases) {
    for (const status of ["ok", "failed", "skipped"]) {
      const out = describe(funding(Object.assign({ status, last_success_at: "2026-10-05" }, overrides)), record());
      assert.equal(out.funding, null, JSON.stringify(Object.assign({ status }, overrides)));
      assert.ok(Array.isArray(out.record), "record stays visible");
    }
  }
  // The valid unknown combination still describes, with no inferred provenance.
  const valid = describe(funding(unknownBase), record()).funding;
  assert.deepEqual(valid, [
    "Last successful build: Oct 18, 2026.",
    "Contribution data retrieval time: unknown.",
    "Latest reporting period represented: unknown.",
  ]);
});

test("year 0000 is rejected; year bounds keep leap-year handling", () => {
  for (const bad of ["0000-01-01", "0000-02-29", "0000-12-31"]) {
    assert.equal(F.freshDay(bad), null, bad);
    assert.equal(F.freshTimestamp(bad + "T00:00:00+00:00"), null, bad + " timestamp");
    assert.equal(F.freshTimestamp(bad + "T12:00:00Z"), null, bad + " Z timestamp");
  }
  assert.equal(F.freshDay("0001-01-01"), "Jan 1, 1");
  assert.equal(F.freshDay("0004-02-29"), "Feb 29, 4");
  assert.equal(F.freshDay("0001-02-29"), null);
  assert.equal(F.freshTimestamp("0001-01-01T00:00:00Z"), "Jan 1, 1, 00:00 UTC");
  const out = describe(funding({ last_success_at: "0000-01-01" }), record({ reviewed_through: "0000-06-01" }));
  assert.equal(out.funding, null);
  assert.equal(out.record, null);
});

test("missing or malformed fields give that dataset's fallback, never raw values", () => {
  const cases = [
    ["funding", { attempted_at: "yesterday" }],
    ["funding", { last_success_at: "2026-10-18T00:00:00+00:00" }],
    ["funding", { source_retrieved_at: "2026-10-18 11:59" }],
    ["funding", { latest_reporting_period_end: "Q3 2026" }],
    ["funding", { last_success_at: undefined }],
    ["record", { reviewed_through: 20261001 }],
    ["record", { status: undefined }],
  ];
  for (const [dataset, overrides] of cases) {
    const out = dataset === "funding" ? describe(funding(overrides), record()) : describe(funding(), record(overrides));
    assert.equal(out[dataset], null, JSON.stringify(overrides));
  }
  assert.equal(describe("not an object", record()).funding, null);
  assert.equal(describe(funding(), [record()]).record, null);
});

test("contradictory chronology gives the fallback rather than misleading text", () => {
  const cases = [
    ["funding", { last_success_at: "2026-10-19" }],
    ["funding", { source_retrieved_at: "2026-10-18T12:00:01+00:00" }],
    ["funding", { latest_reporting_period_end: "2026-10-19" }],
    ["funding", { status: "ok", last_success_at: null }],
    ["funding", { attempted_at: "2026-10-18T12:00:01+00:00" }],
    ["record", { reviewed_through: "2026-10-19" }],
    ["record", { status: "failed", last_success_at: "2026-10-19" }],
  ];
  for (const [dataset, overrides] of cases) {
    const out = dataset === "funding" ? describe(funding(overrides), record()) : describe(funding(), record(overrides));
    assert.equal(out[dataset], null, JSON.stringify(overrides));
    const other = dataset === "funding" ? "record" : "funding";
    assert.ok(Array.isArray(out[other]), `other dataset still shown for ${JSON.stringify(overrides)}`);
  }
});

// --- Document level ---------------------------------------------------------

test("unsupported or unusable documents give both fallbacks", () => {
  const good = { funding: funding(), record: record() };
  const docs = [
    null,
    undefined,
    "freshness",
    [],
    { schema_version: "1.0", generated_at: GENERATED, officials: { "cd1-official": good } },
    { schema_version: "3.0", generated_at: GENERATED, officials: { "cd1-official": good } },
    { schema_version: 2, generated_at: GENERATED, officials: { "cd1-official": good } },
    { schema_version: "2.0", generated_at: "bad", officials: { "cd1-official": good } },
    { schema_version: "2.0", generated_at: GENERATED },
    { schema_version: "2.0", generated_at: GENERATED, officials: [] },
    { schema_version: "2.0", generated_at: GENERATED, officials: { "other-official": good } },
    { schema_version: "2.0", generated_at: GENERATED, officials: { "cd1-official": null } },
  ];
  for (const d of docs) {
    assert.deepEqual(F.describeFreshness(d, "cd1-official"), { funding: null, record: null }, JSON.stringify(d));
  }
  assert.deepEqual(F.describeFreshness(doc(good), "__proto__"), { funding: null, record: null });
});

test("committed data/freshness.json: every current official describes safely", () => {
  const data = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "freshness.json"), "utf8"));
  const officials = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "officials.json"), "utf8"));
  const ids = (Array.isArray(officials) ? officials : officials.officials || []).map((o) => o.id);
  assert.ok(ids.length > 0);
  for (const id of ids) {
    const out = F.describeFreshness(data, id);
    for (const dataset of ["funding", "record"]) {
      assert.ok(Array.isArray(out[dataset]), `${id}.${dataset} should describe from valid committed data`);
      assert.ok(out[dataset].every((l) => typeof l === "string" && l.length > 0));
    }
    assert.equal(out.record.at(-1), F.CURATED_SAMPLE);
  }
});

// --- DOM rendering ----------------------------------------------------------

test("safe text insertion: markup in values is never interpreted", () => {
  const d = new FakeDocument();
  const el = d.getElementById("funding-freshness");
  F.renderFreshnessLines(el, ['<img src=x onerror="alert(1)">', "plain"]);
  assert.deepEqual(lines(el), ['<img src=x onerror="alert(1)">', "plain"]);
  assert.ok(el.children.every((c) => c.tagName === "p"));
});

test("rendering twice replaces content instead of duplicating it", () => {
  const d = new FakeDocument();
  const el = d.getElementById("record-freshness");
  F.renderFreshnessLines(el, ["one", "two", "three"]);
  F.renderFreshnessLines(el, ["four"]);
  assert.deepEqual(lines(el), ["four"]);
});

test("loadFreshness success reveals both placeholders with described text", async () => {
  const d = new FakeDocument();
  const fetch = () => Promise.resolve(jsonResponse(doc({ funding: funding(), record: record() })));
  await F.loadFreshness("cd1-official", { document: d, fetch });
  const f = d.getElementById("funding-freshness");
  const r = d.getElementById("record-freshness");
  assert.equal(f.hidden, false);
  assert.equal(r.hidden, false);
  assert.equal(lines(f)[0], "Last successful build: Oct 18, 2026.");
  assert.equal(lines(r).at(-1), F.CURATED_SAMPLE);
  await F.loadFreshness("cd1-official", { document: d, fetch });
  assert.equal(lines(f).length, 3, "second load replaces, not appends");
});

test("fetch failures resolve, reveal fallbacks and never throw", async () => {
  const failures = {
    rejects: () => Promise.reject(new TypeError("network down")),
    throwsSync: () => {
      throw new Error("boom");
    },
    notOk: () => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) }),
    badJson: () => Promise.resolve({ ok: true, json: () => Promise.reject(new SyntaxError("Unexpected token")) }),
    nullResponse: () => Promise.resolve(null),
    v1: () => Promise.resolve(jsonResponse({ schema_version: "1.0", officials: {} })),
  };
  for (const [name, fetch] of Object.entries(failures)) {
    const d = new FakeDocument();
    const { warnings } = await quietly(() => F.loadFreshness("cd1-official", { document: d, fetch }));
    const f = d.getElementById("funding-freshness");
    const r = d.getElementById("record-freshness");
    assert.equal(f.hidden, false, name);
    assert.equal(r.hidden, false, name);
    assert.deepEqual(lines(f), [F.FALLBACK], name);
    assert.deepEqual(lines(r), [F.FALLBACK, F.CURATED_SAMPLE], name);
    if (name !== "v1") assert.ok(warnings.length >= 1, `${name} logs a warning`);
  }
});

test("missing fetch or missing DOM targets do not reject", async () => {
  const d = new FakeDocument([]);
  await quietly(() => F.loadFreshness("cd1-official", { document: d, fetch: () => Promise.resolve(jsonResponse(doc({}))) }));
  const onlyFunding = new FakeDocument(["funding-freshness"]);
  await F.loadFreshness("cd1-official", { document: onlyFunding, fetch: () => Promise.resolve(jsonResponse(doc({ funding: funding(), record: record() }))) });
  assert.equal(lines(onlyFunding.getElementById("funding-freshness"))[0], "Last successful build: Oct 18, 2026.");
  await quietly(() => F.loadFreshness("cd1-official", { document: {}, fetch: null }));
  assert.equal(F.renderFreshnessLines(null, ["x"]), false);
});

test("unhandled rejections: none across failure scenarios", async () => {
  const seen = [];
  const onRejection = (reason) => seen.push(reason);
  process.on("unhandledRejection", onRejection);
  try {
    await quietly(async () => {
      await F.loadFreshness("cd1-official", { document: new FakeDocument([]), fetch: () => Promise.reject(new Error("x")) });
      await F.loadFreshness("cd1-official", { document: null, fetch: () => Promise.reject(new Error("y")) });
      await F.loadFreshness("cd1-official", {
        document: { getElementById: () => { throw new Error("dom gone"); } },
        fetch: () => Promise.resolve(jsonResponse(doc({ funding: funding(), record: record() }))),
      });
    });
    await new Promise((resolve) => setImmediate(resolve));
  } finally {
    process.off("unhandledRejection", onRejection);
  }
  assert.deepEqual(seen, []);
});

test("importing the module touches neither document nor fetch", () => {
  const script = `
    let touched = [];
    Object.defineProperty(globalThis, "document", { configurable: true, get() { touched.push("document"); return undefined; } });
    Object.defineProperty(globalThis, "fetch", { configurable: true, get() { touched.push("fetch"); return () => { touched.push("fetch-call"); }; } });
    const F = require(${JSON.stringify(MODULE)});
    if (typeof F.loadFreshness !== "function" || typeof F.describeFreshness !== "function") throw new Error("exports missing");
    if ("CypFreshness" in globalThis) throw new Error("browser global leaked under Node");
    process.stdout.write(JSON.stringify(touched));`;
  const r = spawnSync(process.execPath, ["-e", script], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(JSON.parse(r.stdout), []);
});

test("browser-style load exposes window.CypFreshness without module", () => {
  const vm = require("node:vm");
  const sandbox = { console };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(MODULE, "utf8"), sandbox, { filename: "freshness.js" });
  assert.equal(typeof sandbox.CypFreshness.loadFreshness, "function");
});
