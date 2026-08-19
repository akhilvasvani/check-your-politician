/*!
 * transcript-search.js — Per-official transcript search module.
 *
 * Renders and wires the transcript-search section on official.html: users
 * type a natural-language query, we call /api/search-transcripts, and
 * results are shown as time-stamped snippets that deep-link back to the
 * source YouTube video.
 *
 * M2 additions (2026-08-19):
 *   * "part N of M" badge when the RPC returns a chunk from a long turn
 *     that was split by the M1 chunker (sub_chunk_of > 1). Helps readers
 *     know they're only seeing one slice of a longer statement.
 *   * "Include public comment" checkbox that fires a second request to
 *     /api/search-public-comment and renders those hits below the
 *     per-official results in their own labeled section. Intentionally
 *     separate — mixing dilutes both stories (see M2_PLAN.md D5).
 *
 * On submit this calls /api/search-transcripts (and optionally
 * /api/search-public-comment) — the serverless functions hold the
 * PERPLEXITY_API_KEY + SUPABASE credentials server-side. This file never
 * talks to Perplexity or Supabase directly.
 *
 * If the current official doesn't have a matching roster.json entry
 * (resolved_official_id), the whole panel stays hidden. The public-comment
 * corpus is org-wide (not tied to one official), but we still gate it on
 * the transcript panel showing up at all — so a page for someone not in
 * the roster never surfaces public-comment results either.
 *
 * DOM contract (see official.html):
 *   #transcript-search-section, #transcript-search-form,
 *   #transcript-search-input, #transcript-search-submit,
 *   #transcript-search-status, #transcript-search-results,
 *   #transcript-search-public-results (M2), #transcript-search-empty,
 *   #transcript-search-include-public (M2 checkbox).
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

  // M2: sub-chunk badge. sub_chunk_of=1 (default) means the chunk is a
  // whole turn — no badge. Anything higher means a splitter kicked in.
  // sub_chunk_idx is 0-based; display as 1-based part number.
  function subChunkBadgeText(row) {
    var total = Number(row && row.sub_chunk_of) || 1;
    if (total <= 1) return null;
    var idx = Number(row && row.sub_chunk_idx) || 0;
    return "part " + (idx + 1) + " of " + total;
  }

  // Public-comment rows don't have a canonical resolved_official_id. Pick
  // the best display label available. Priority: source_label (CART cue,
  // e.g. "Palisades Larry"), then turn_speaker_raw, then a neutral fallback.
  function publicSpeakerLabel(row) {
    if (row && typeof row.source_label === "string" && row.source_label.trim()) {
      return row.source_label.trim();
    }
    if (row && typeof row.turn_speaker_raw === "string" && row.turn_speaker_raw.trim()) {
      return row.turn_speaker_raw.trim();
    }
    if (row && typeof row.resolved_name === "string" && row.resolved_name.trim()) {
      return row.resolved_name.trim();
    }
    return "Public speaker";
  }

  async function initTranscriptSearch(id, official) {
    var section = document.getElementById("transcript-search-section");
    if (!section || !official) return;

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
    var publicResultsEl = document.getElementById("transcript-search-public-results");
    var includePublicEl = document.getElementById("transcript-search-include-public");
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
    if (publicResultsEl) {
      publicResultsEl.innerHTML = "";
      publicResultsEl.hidden = true;
    }
    if (emptyEl) emptyEl.hidden = true;
    setLoading(true);
    showStatus("Searching\u2026", false);

    var includePublic = !!(includePublicEl && includePublicEl.checked);

    try {
      // Fire the per-official search and (if requested) the public-comment
      // search in parallel. They're independent RPCs and the two endpoints
      // don't share state client-side.
      var officialPromise = fetch("/api/search-transcripts", {
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

      var publicPromise = includePublic
        ? fetch("/api/search-public-comment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: query, limit: 8 }),
          })
        : null;

      var officialResp = await officialPromise;
      var officialData = null;
      try { officialData = await officialResp.json(); } catch (e) { officialData = null; }

      if (!officialResp.ok) {
        var message =
          (officialData && officialData.error) ||
          "Search is temporarily unavailable. Please try again in a moment.";
        showStatus(message, true);
        return;
      }

      var results = (officialData && Array.isArray(officialData.results)) ? officialData.results : [];

      var publicResults = [];
      var publicError = null;
      if (publicPromise) {
        try {
          var publicResp = await publicPromise;
          var publicData = null;
          try { publicData = await publicResp.json(); } catch (e) { publicData = null; }
          if (publicResp.ok && publicData && Array.isArray(publicData.results)) {
            publicResults = publicData.results;
          } else if (publicData && publicData.error) {
            publicError = publicData.error;
          } else {
            publicError = "Public comment search was unavailable for this query.";
          }
        } catch (err) {
          console.warn("[transcript-search] public-comment request failed:", err);
          publicError = "Public comment search was unavailable for this query.";
        }
      }

      if (!results.length && !publicResults.length) {
        if (emptyEl) {
          emptyEl.hidden = false;
          emptyEl.textContent =
            "No transcript matches for \u201C" + query + "\u201D. Try a broader phrase, or a topic like \u201Chomelessness\u201D or \u201Cbudget\u201D.";
        }
        hideStatus();
        return;
      }

      if (results.length) {
        renderResults(resultsEl, results, {
          headingSingular: "matching passage from " + currentContext.name,
          headingPlural: "matching passages from " + currentContext.name,
          showSpeaker: true,
        });
      } else {
        // Official had no hits but public-comment did — surface a subhead.
        var noOfficial = document.createElement("p");
        noOfficial.className = "transcript-search-results-heading";
        noOfficial.textContent = "No matches from " + currentContext.name + ".";
        resultsEl.appendChild(noOfficial);
      }

      if (publicResultsEl && includePublic) {
        publicResultsEl.hidden = false;
        if (publicResults.length) {
          renderResults(publicResultsEl, publicResults, {
            headingSingular: "matching passage from public comment",
            headingPlural: "matching passages from public comment",
            showSpeaker: true,
            isPublicComment: true,
          });
        } else {
          var noPublic = document.createElement("p");
          noPublic.className = "transcript-search-results-heading";
          noPublic.textContent = publicError
            ? publicError
            : "No public comment matches for \u201C" + query + "\u201D.";
          publicResultsEl.appendChild(noPublic);
        }
      }

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

  function renderResults(container, results, opts) {
    opts = opts || {};
    container.innerHTML = "";

    var heading = document.createElement("p");
    heading.className = "transcript-search-results-heading";
    heading.textContent =
      results.length +
      " " +
      (results.length === 1
        ? (opts.headingSingular || "matching passage")
        : (opts.headingPlural || "matching passages"));
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

      if (opts.showSpeaker) {
        var speakerText = opts.isPublicComment
          ? publicSpeakerLabel(r)
          : (r.resolved_name || "");
        if (speakerText) {
          var speaker = document.createElement("span");
          speaker.className = "transcript-search-result-speaker";
          speaker.textContent = " · " + speakerText;
          meta.appendChild(speaker);
        }
      }

      // M2.2 sub-chunk badge. Only shown when the chunk is one slice of a
      // longer turn (sub_chunk_of > 1). Positioned between speaker and
      // score so it reads left-to-right as: date · time · speaker · part …
      // · match %.
      var badgeText = subChunkBadgeText(r);
      if (badgeText) {
        var badge = document.createElement("span");
        badge.className = "transcript-search-result-badge";
        badge.textContent = " · " + badgeText;
        badge.setAttribute(
          "title",
          "This turn was long enough that the chunker split it into " +
            r.sub_chunk_of +
            " parts."
        );
        meta.appendChild(badge);
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
