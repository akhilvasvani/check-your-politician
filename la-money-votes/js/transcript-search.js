/*!
 * transcript-search.js — Per-official transcript search module.
 *
 * Renders and wires the transcript-search section on official.html: users
 * type a natural-language query, we call /api/search-transcripts, and
 * results are shown as time-stamped snippets that deep-link back to the
 * source YouTube video.
 *
 * On submit this calls the same-origin serverless function at
 * /api/search-transcripts (source: api/search-transcripts.js), which holds
 * PERPLEXITY_API_KEY + SUPABASE credentials server-side. This file never
 * talks to Perplexity or Supabase directly.
 *
 * The module is scoped to one official per page (mirrors the "Ask about
 * [Official]" pattern). If the current official doesn't have a matching
 * roster.json entry (resolved_official_id), we hide the panel rather than
 * showing empty results.
 *
 * Depends on the DOM elements defined in official.html
 * (#transcript-search-section, #transcript-search-form, #transcript-search-input,
 * #transcript-search-submit, #transcript-search-status,
 * #transcript-search-results, #transcript-search-empty) and, optionally,
 * escapeHtml() from app.js (falls back to a local copy).
 *
 * js/app.js calls window.initTranscriptSearch(id, official) once it has
 * fetched the current official's funding.json (same wire-up as ask-ai).
 */
(function (global) {
  "use strict";

  var MAX_QUERY_LENGTH = 200;
  var RESUBMIT_COOLDOWN_MS = 3000;

  var currentContext = null;
  var lastRequestAt = 0;
  var wired = false;

  function escapeHtml(value) {
    if (typeof global.escapeHtml === "function") return global.escapeHtml(value);
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function formatTime(seconds) {
    var s = Math.max(0, Math.round(Number(seconds) || 0));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    var pad = function (n) { return n < 10 ? "0" + n : String(n); };
    return (h > 0 ? h + ":" + pad(m) : String(m)) + ":" + pad(sec);
  }

  function formatDate(iso) {
    // Meeting date is ISO "YYYY-MM-DD"; render as "Aug 4, 2026" without
    // yanking in an i18n library.
    if (typeof iso !== "string" || iso.length < 10) return String(iso || "");
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var y = iso.slice(0, 4);
    var m = parseInt(iso.slice(5, 7), 10);
    var d = parseInt(iso.slice(8, 10), 10);
    if (!m || !d) return iso;
    return months[m - 1] + " " + d + ", " + y;
  }

  function youtubeUrl(videoId, startSec) {
    var t = Math.max(0, Math.floor(Number(startSec) || 0));
    return "https://www.youtube.com/watch?v=" + encodeURIComponent(videoId) + "&t=" + t + "s";
  }

  async function initTranscriptSearch(id, official) {
    var section = document.getElementById("transcript-search-section");
    if (!section || !official) return;

    // Roster lives in data/transcripts/roster.json. Only councilmembers
    // (and the mayor/city-attorney) that map to an official.id in
    // roster.json can be searched -- the API endpoint filters strictly on
    // resolved_official_id. If this official isn't in the roster, hide the
    // whole module so users don't see a "This official isn't linked yet"
    // error on every submit.
    var rosterEntry = null;
    try {
      var res = await fetch("data/transcripts/roster.json");
      if (res.ok) {
        var roster = await res.json();
        var members = (roster && roster.members) || [];
        rosterEntry = members.find(function (r) {
          return r && r.official_id === id;
        });
      }
    } catch (err) {
      console.warn("[transcript-search] Could not load roster.json:", err);
    }

    if (!rosterEntry || !rosterEntry.official_id) {
      section.hidden = true;
      return;
    }

    currentContext = {
      id: id,
      resolved_official_id: rosterEntry.official_id,
      name: official.name || rosterEntry.display_name || "this official",
    };

    section.hidden = false;
    var nameSpan = document.getElementById("transcript-search-official-name");
    if (nameSpan) nameSpan.textContent = currentContext.name;

    wireForm();
  }

  function wireForm() {
    if (wired) return;
    var form = document.getElementById("transcript-search-form");
    if (!form) return;
    wired = true;
    form.addEventListener("submit", handleSubmit);
  }

  async function handleSubmit(evt) {
    evt.preventDefault();
    if (!currentContext) return;

    var input = document.getElementById("transcript-search-input");
    var submitBtn = document.getElementById("transcript-search-submit");
    var resultsEl = document.getElementById("transcript-search-results");
    var emptyEl = document.getElementById("transcript-search-empty");
    if (!input || !submitBtn || !resultsEl) return;

    var query = String(input.value || "").trim();
    if (!query) {
      showStatus("Please enter a search phrase.", true);
      return;
    }
    if (query.length > MAX_QUERY_LENGTH) {
      showStatus("Query too long — " + MAX_QUERY_LENGTH + " characters max.", true);
      return;
    }

    var now = Date.now();
    if (now - lastRequestAt < RESUBMIT_COOLDOWN_MS) {
      showStatus("Please wait a moment before searching again.", true);
      return;
    }
    lastRequestAt = now;

    resultsEl.innerHTML = "";
    if (emptyEl) emptyEl.hidden = true;
    setLoading(true);
    showStatus("Searching\u2026", false);

    try {
      var response = await fetch("/api/search-transcripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          official: {
            id: currentContext.id,
            resolved_official_id: currentContext.resolved_official_id,
            name: currentContext.name,
          },
          limit: 8,
        }),
      });

      var data = null;
      try { data = await response.json(); } catch (e) { data = null; }

      if (!response.ok) {
        var message =
          (data && data.error) ||
          "Search is temporarily unavailable. Please try again in a moment.";
        showStatus(message, true);
        return;
      }

      var results = (data && Array.isArray(data.results)) ? data.results : [];
      if (!results.length) {
        if (emptyEl) {
          emptyEl.hidden = false;
          emptyEl.textContent =
            "No transcript matches for \u201C" + query + "\u201D. Try a broader phrase, or a topic like \u201Chomelessness\u201D or \u201Cbudget\u201D.";
        }
        hideStatus();
        return;
      }

      renderResults(resultsEl, results);
      hideStatus();
    } catch (err) {
      console.warn("[transcript-search] request failed:", err);
      showStatus(
        "Couldn't reach the search service. Please check your connection and try again.",
        true
      );
    } finally {
      setLoading(false);
      startCooldown(submitBtn);
    }
  }

  function renderResults(container, results) {
    container.innerHTML = "";
    var heading = document.createElement("p");
    heading.className = "transcript-search-results-heading";
    heading.textContent = results.length + " matching passage" + (results.length === 1 ? "" : "s");
    container.appendChild(heading);

    var list = document.createElement("ol");
    list.className = "transcript-search-results-list";

    results.forEach(function (r) {
      var li = document.createElement("li");
      li.className = "transcript-search-result";

      var meta = document.createElement("p");
      meta.className = "transcript-search-result-meta";
      var link = document.createElement("a");
      link.href = youtubeUrl(r.video_id, r.start_sec);
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = formatDate(r.meeting_date) + " · " + formatTime(r.start_sec);
      meta.appendChild(link);

      if (r.resolved_name) {
        var speaker = document.createElement("span");
        speaker.className = "transcript-search-result-speaker";
        speaker.textContent = " · " + r.resolved_name;
        meta.appendChild(speaker);
      }

      if (typeof r.similarity === "number") {
        var score = document.createElement("span");
        score.className = "transcript-search-result-score";
        score.textContent = " · match " + (r.similarity * 100).toFixed(0) + "%";
        meta.appendChild(score);
      }

      li.appendChild(meta);

      var body = document.createElement("p");
      body.className = "transcript-search-result-text";
      // The text/snippet fields are untrusted CART output; escape before insertion.
      var hasSnippet = typeof r.snippet === "string" && r.snippet.length > 0 &&
        r.snippet.length < String(r.text || "").length;
      body.innerHTML = escapeHtml(hasSnippet ? r.snippet : r.text);
      li.appendChild(body);

      if (hasSnippet) {
        var toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "transcript-search-result-toggle";
        toggle.textContent = "Show full passage";
        toggle.setAttribute("aria-expanded", "false");
        toggle.addEventListener("click", function () {
          var expanded = toggle.getAttribute("aria-expanded") === "true";
          body.innerHTML = escapeHtml(expanded ? r.snippet : r.text);
          toggle.textContent = expanded ? "Show full passage" : "Show snippet";
          toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
        });
        li.appendChild(toggle);
      }

      list.appendChild(li);
    });

    container.appendChild(list);
  }

  function setLoading(isLoading) {
    var submitBtn = document.getElementById("transcript-search-submit");
    var input = document.getElementById("transcript-search-input");
    if (submitBtn) submitBtn.textContent = isLoading ? "Searching\u2026" : "Search";
    if (input) input.disabled = isLoading;
    if (submitBtn) submitBtn.disabled = isLoading;
  }

  function startCooldown(submitBtn) {
    if (!submitBtn) return;
    submitBtn.disabled = true;
    setTimeout(function () { submitBtn.disabled = false; }, RESUBMIT_COOLDOWN_MS);
  }

  function showStatus(message, isError) {
    var statusEl = document.getElementById("transcript-search-status");
    if (!statusEl) return;
    statusEl.hidden = false;
    statusEl.textContent = message;
    statusEl.classList.toggle("transcript-search-status-error", !!isError);
  }

  function hideStatus() {
    var statusEl = document.getElementById("transcript-search-status");
    if (statusEl) statusEl.hidden = true;
  }

  global.initTranscriptSearch = initTranscriptSearch;
})(window);
