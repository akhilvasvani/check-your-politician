/*!
 * freshness.js — read-only display of data/freshness.json (schema 2.0) on a
 * profile page.
 *
 * Optional and additive: js/app.js starts it without waiting for it, and any
 * fetch, parse or rendering problem ends in the plain-text fallback
 * ("Update information unavailable.") instead of an error. Funding and the
 * public-action record are described independently, so one unusable entry
 * never hides the other.
 *
 * Dates are never passed through Date(): date-only values ("YYYY-MM-DD")
 * would parse as UTC midnight and can render as the previous day in US
 * timezones. Both dates and UTC timestamps are parsed by hand, impossible
 * values are rejected, and a rejected value is shown as "unknown", never raw.
 *
 * Text is inserted with createElement + textContent only. There are no
 * staleness thresholds here; the page states dates, not judgments.
 *
 * Loadable as a classic browser script (exposes window.CypFreshness) and from
 * Node via require() for tests. Loading it touches neither document nor fetch.
 */
(function (root) {
  "use strict";

  var SCHEMA_VERSION = "2.0";
  var FALLBACK = "Update information unavailable.";
  var CURATED_SAMPLE = "These public actions are a curated sample, not a complete voting history.";
  // Exact-match lists (indexOf), so inherited names such as "toString" or
  // "__proto__" and non-strings such as ["ok"] are never accepted.
  var STATUSES = ["ok", "failed", "skipped"];
  var FUNDING_SOURCE_TYPES = ["automated_api", "automated_csv", "unknown"];
  var RECORD_SOURCE_TYPES = ["manual_curated"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function daysInMonth(year, month) {
    if (month === 2) {
      var leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
      return leap ? 29 : 28;
    }
    return [4, 6, 9, 11].indexOf(month) >= 0 ? 30 : 31;
  }

  // "YYYY-MM-DD" -> {key, text} or null. `key` compares correctly as a string.
  function parseDay(value) {
    if (typeof value !== "string") return null;
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!m) return null;
    var year = parseInt(m[1], 10);
    var month = parseInt(m[2], 10);
    var day = parseInt(m[3], 10);
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) return null;
    return { key: value, text: MONTHS[month - 1] + " " + day + ", " + year };
  }

  // UTC "YYYY-MM-DDTHH:MM:SS+00:00" or "...Z" -> {key, day, text} or null.
  function parseTimestamp(value) {
    if (typeof value !== "string") return null;
    var m = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\+00:00|Z)$/.exec(value);
    if (!m) return null;
    var day = parseDay(m[1]);
    var hour = parseInt(m[2], 10);
    var minute = parseInt(m[3], 10);
    var second = parseInt(m[4], 10);
    if (!day || hour > 23 || minute > 59 || second > 59) return null;
    return {
      key: m[1] + "T" + m[2] + ":" + m[3] + ":" + m[4],
      day: m[1],
      text: day.text + ", " + m[2] + ":" + m[3] + " UTC",
    };
  }

  function freshDay(value) {
    var parsed = parseDay(value);
    return parsed ? parsed.text : null;
  }

  function freshTimestamp(value) {
    var parsed = parseTimestamp(value);
    return parsed ? parsed.text : null;
  }

  // Known codes only; anything that is not a list of strings is treated as
  // "no warnings" rather than guessed at.
  function warningSet(codes) {
    var set = {};
    if (!Array.isArray(codes)) return set;
    codes.forEach(function (code) {
      if (typeof code === "string") set[code] = true;
    });
    return set;
  }

  function oneOf(value, allowed) {
    return typeof value === "string" && allowed.indexOf(value) >= 0;
  }

  // Shared build/attempt lines. Returns null when the entry is unusable or
  // its dates contradict each other or the snapshot time.
  function buildLines(entry, generated, sourceTypes) {
    if (!isPlainObject(entry) || !oneOf(entry.status, STATUSES)) return null;
    if (!oneOf(entry.source_type, sourceTypes)) return null;
    var attempted = parseTimestamp(entry.attempted_at);
    if (!attempted || attempted.key > generated.key) return null;
    var lastSuccess = entry.last_success_at === null ? null : parseDay(entry.last_success_at);
    if (entry.last_success_at !== null && !lastSuccess) return null;
    if (lastSuccess && lastSuccess.key > attempted.day) return null;
    if (entry.status === "ok" && !lastSuccess) return null;

    var warnings = warningSet(entry.warning_codes);
    var lines = [];
    if (entry.status === "ok") {
      lines.push("Last successful build: " + lastSuccess.text + ".");
    } else {
      var outcome = entry.status === "failed" ? "failed" : "was skipped";
      var attempt = "The latest build attempt (" + attempted.text + ") " + outcome + ".";
      if (warnings.SOURCE_UNAVAILABLE) attempt += " The source was unavailable for that attempt.";
      lines.push(attempt);
      lines.push(
        lastSuccess
          ? "Showing data from the last successful build on " + lastSuccess.text + "."
          : "No successful build is recorded."
      );
    }
    return { lines: lines, attempted: attempted, warnings: warnings };
  }

  function describeFunding(entry, generated) {
    var base = buildLines(entry, generated, FUNDING_SOURCE_TYPES);
    if (!base) return null;
    var lines = base.lines;

    // Combinations the contract rules out are not shown or repaired: CSV and
    // unknown sources never have a retrieval time, and an unknown (v1-migrated)
    // entry has no reporting period or matched-row count.
    if (entry.source_type !== "automated_api" && entry.source_retrieved_at !== null) return null;
    if (
      entry.source_type === "unknown" &&
      (entry.latest_reporting_period_end !== null || entry.matched_row_count !== null)
    ) {
      return null;
    }

    // Contribution retrieval time and reporting period are separate facts.
    var retrieved = entry.source_retrieved_at === null ? null : parseTimestamp(entry.source_retrieved_at);
    if (entry.source_retrieved_at !== null && !retrieved) return null;
    if (retrieved && retrieved.key > base.attempted.key) return null;
    if (retrieved) {
      lines.push("Contribution data retrieved from the source: " + retrieved.text + ".");
    } else if (entry.source_type === "automated_csv") {
      lines.push("Contribution data came from a downloaded file; retrieval time not recorded.");
    } else {
      lines.push("Contribution data retrieval time: unknown.");
    }
    if (base.warnings.SOURCE_CACHE_FALLBACK) {
      lines.push("These donors came from a saved copy of the source and may be older than the build date.");
    }
    if (base.warnings.SUPPORTING_SOURCE_CACHE_FALLBACK) {
      lines.push("Filed-statement links came from a saved copy of a supporting source; donor data is not affected.");
    }

    var period = entry.latest_reporting_period_end === null ? null : parseDay(entry.latest_reporting_period_end);
    if (entry.latest_reporting_period_end !== null && !period) return null;
    if (period && period.key > base.attempted.day) return null;
    lines.push(
      period
        ? "Latest reporting period represented ends " + period.text + "."
        : "Latest reporting period represented: unknown."
    );
    return lines;
  }

  function describeRecord(entry, generated) {
    var base = buildLines(entry, generated, RECORD_SOURCE_TYPES);
    if (!base) return null;
    var lines = base.lines;
    var reviewed = entry.reviewed_through === null ? null : parseDay(entry.reviewed_through);
    if (entry.reviewed_through !== null && !reviewed) return null;
    if (reviewed && reviewed.key > base.attempted.day) return null;
    lines.push(
      reviewed
        ? "Human-reviewed through " +
            reviewed.text +
            ": a maintainer checked this project's official sources for actions through that date."
        : "No human review date is recorded."
    );
    lines.push(CURATED_SAMPLE);
    return lines;
  }

  // -> {funding: string[] | null, record: string[] | null}. null means "show
  // the fallback for that dataset". Never throws.
  function describeFreshness(doc, officialId) {
    var none = { funding: null, record: null };
    try {
      if (!isPlainObject(doc) || doc.schema_version !== SCHEMA_VERSION) return none;
      var generated = parseTimestamp(doc.generated_at);
      if (!generated || !isPlainObject(doc.officials)) return none;
      if (!Object.prototype.hasOwnProperty.call(doc.officials, officialId)) return none;
      var entry = doc.officials[officialId];
      if (!isPlainObject(entry)) return none;
      return {
        funding: describeFunding(entry.funding, generated),
        record: describeRecord(entry.record, generated),
      };
    } catch (err) {
      return none;
    }
  }

  function fundingLinesOrFallback(lines) {
    return lines || [FALLBACK];
  }

  // The curated-sample statement is shown even when the record entry is
  // unusable.
  function recordLinesOrFallback(lines) {
    return lines || [FALLBACK, CURATED_SAMPLE];
  }

  // Replaces el's content with one <p> per line and reveals it. Returns false
  // (and does nothing) when el is missing.
  function renderFreshnessLines(el, lines) {
    if (!el) return false;
    var doc = el.ownerDocument || root.document;
    while (el.firstChild) el.removeChild(el.firstChild);
    lines.forEach(function (line) {
      var p = doc.createElement("p");
      p.textContent = line;
      el.appendChild(p);
    });
    el.hidden = false;
    return true;
  }

  // Fetches data/freshness.json and fills #funding-freshness and
  // #record-freshness. Always resolves; never rejects.
  function loadFreshness(officialId, options) {
    var opts = options || {};
    var doc = opts.document || root.document;
    var fetchImpl = opts.fetch || root.fetch;
    var url = opts.url || "data/freshness.json";

    function render(described) {
      try {
        if (!doc || typeof doc.getElementById !== "function") return;
        renderFreshnessLines(doc.getElementById("funding-freshness"), fundingLinesOrFallback(described.funding));
        renderFreshnessLines(doc.getElementById("record-freshness"), recordLinesOrFallback(described.record));
      } catch (err) {
        warn("could not render freshness information", err);
      }
    }

    var request;
    try {
      if (typeof fetchImpl !== "function") throw new Error("fetch is unavailable");
      request = Promise.resolve(fetchImpl(url));
    } catch (err) {
      request = Promise.reject(err);
    }
    return request
      .then(function (res) {
        if (!res || !res.ok) throw new Error("freshness.json could not be loaded");
        return res.json();
      })
      .then(function (data) {
        render(describeFreshness(data, officialId));
      })
      .catch(function (err) {
        warn("freshness information unavailable", err);
        render({ funding: null, record: null });
      });
  }

  function warn(message, err) {
    if (root.console && typeof root.console.warn === "function") {
      root.console.warn("[freshness.js] " + message + ":", err);
    }
  }

  var api = {
    FALLBACK: FALLBACK,
    CURATED_SAMPLE: CURATED_SAMPLE,
    freshDay: freshDay,
    freshTimestamp: freshTimestamp,
    describeFreshness: describeFreshness,
    fundingLinesOrFallback: fundingLinesOrFallback,
    recordLinesOrFallback: recordLinesOrFallback,
    renderFreshnessLines: renderFreshnessLines,
    loadFreshness: loadFreshness,
  };

  if (typeof module === "object" && module && module.exports) {
    module.exports = api;
  } else {
    root.CypFreshness = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
