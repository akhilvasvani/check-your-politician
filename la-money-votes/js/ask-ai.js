/*!
 * ask-ai.js — "Ask about [Official Name]" Q&A module (official.html only)
 *
 * Renders and wires the search module that sits between the Funding
 * section's donor table and the "Voting & Proposal Record" section, plus a
 * small persistent floating "Ask AI" button on mobile that scrolls to it.
 *
 * On submit, this calls the same-origin serverless function at
 * /api/ask-official (source: api/ask-official.js), which holds the
 * PERPLEXITY_API_KEY server-side and never exposes it to the client. This
 * file never talks to the Perplexity API directly.
 *
 * Depends on nothing except the DOM elements defined in official.html
 * (#ask-ai-section, #ask-ai-form, #ask-ai-input, #ask-ai-submit,
 * #ask-ai-status, #ask-ai-result, #ask-ai-answer, #ask-ai-citations,
 * #ask-ai-float-btn) and, optionally, escapeHtml() from app.js (falls back
 * to a local copy if app.js hasn't defined it yet, so load order doesn't
 * matter). js/app.js calls window.initAskAI(id, official) once it has
 * fetched the current official's funding.json.
 */
(function (global) {
  "use strict";

  var MAX_QUESTION_LENGTH = 300;
  // Client-side debounce: how long the submit button stays disabled after a
  // request finishes (success or failure), to keep API cost predictable.
  // This is a UX-level cost control, not a security control — see
  // api/ask-official.js for the accompanying (best-effort) server-side
  // rate limit.
  var RESUBMIT_COOLDOWN_MS = 8000;

  var currentOfficialContext = null;
  var lastRequestAt = 0;
  var wired = false;

  function escapeHtml(value) {
    if (typeof global.escapeHtml === "function") return global.escapeHtml(value);
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function districtFromTitle(title) {
    var match = /District\s+(\d+)/i.exec(title || "");
    return match ? match[1] : null;
  }

  async function initAskAI(id, official) {
    var section = document.getElementById("ask-ai-section");
    if (!section || !official) return;

    var party = "Not publicly listed";
    try {
      var res = await fetch("data/officials.json");
      if (res.ok) {
        var officials = await res.json();
        var entry = (officials || []).find(function (o) { return o.id === id; });
        if (entry && entry.party && entry.party.affiliation) {
          party = entry.party.affiliation;
        }
      }
    } catch (err) {
      // Non-fatal — party context is a nice-to-have for the AI prompt, not
      // required for the module to work.
      console.warn("[ask-ai.js] Could not load party context:", err);
    }

    currentOfficialContext = {
      id: id || null,
      name: official.name || "this official",
      title: official.office || "",
      district: districtFromTitle(official.office),
      party: party,
    };

    var nameSpan = document.getElementById("ask-ai-official-name");
    if (nameSpan) nameSpan.textContent = currentOfficialContext.name;

    wireForm();
    wireFloatingButton();
  }

  function wireForm() {
    if (wired) return;
    var form = document.getElementById("ask-ai-form");
    if (!form) return;
    wired = true;
    form.addEventListener("submit", handleSubmit);
  }

  async function handleSubmit(evt) {
    evt.preventDefault();

    var input = document.getElementById("ask-ai-input");
    var submitBtn = document.getElementById("ask-ai-submit");
    var resultEl = document.getElementById("ask-ai-result");
    var answerEl = document.getElementById("ask-ai-answer");
    var citationsEl = document.getElementById("ask-ai-citations");
    if (!input || !submitBtn) return;

    var question = input.value.trim();
    if (!question) {
      showStatus("Please type a question first.", true);
      return;
    }
    if (question.length > MAX_QUESTION_LENGTH) {
      showStatus("Question must be " + MAX_QUESTION_LENGTH + " characters or fewer.", true);
      return;
    }

    var now = Date.now();
    if (now - lastRequestAt < RESUBMIT_COOLDOWN_MS) {
      showStatus("Please wait a few seconds before asking another question.", true);
      return;
    }
    lastRequestAt = now;

    resultEl.hidden = true;
    setLoading(true);
    showStatus("Thinking\u2026", false);

    try {
      var response = await fetch("/api/ask-official", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question,
          official: currentOfficialContext,
        }),
      });

      var data = null;
      try {
        data = await response.json();
      } catch (parseErr) {
        data = null;
      }

      if (!response.ok) {
        var message =
          (data && data.error) ||
          "We couldn't get an answer right now. Please try again in a moment.";
        showStatus(message, true);
        return;
      }

      if (!data || !data.answer) {
        showStatus("No answer was returned. Please try rephrasing your question.", true);
        return;
      }

      renderAnswer(answerEl, data.answer);
      renderCitations(citationsEl, data.citations || []);
      resultEl.hidden = false;
      hideStatus();
    } catch (err) {
      console.warn("[ask-ai.js] Ask-AI request failed:", err);
      showStatus(
        "We couldn't reach the search service. Please check your connection and try again, or use the funding/record data above directly.",
        true
      );
    } finally {
      setLoading(false);
      startCooldown(submitBtn);
    }
  }

  // Renders the AI answer as sanitized HTML so Markdown (bold, italics,
  // lists, links) displays properly instead of showing raw "**...**"
  // syntax. Uses the vendored `marked` (Markdown -> HTML) and `DOMPurify`
  // (HTML sanitizer) libraries loaded via <script> tags in official.html --
  // see js/vendor/. The API response is external/untrusted content, so it
  // is always run through DOMPurify before being inserted into the DOM,
  // even though it also passes through marked's own escaping.
  function renderAnswer(container, rawAnswer) {
    if (!container) return;
    var text = rawAnswer == null ? "" : String(rawAnswer);

    if (typeof global.marked === "undefined" || typeof global.DOMPurify === "undefined") {
      // Vendored libraries failed to load for some reason -- fail safe to
      // plain text rather than showing broken markup or, worse, raw HTML.
      console.warn("[ask-ai.js] marked/DOMPurify not available; falling back to plain text.");
      container.textContent = text;
      return;
    }

    try {
      var rawHtml = global.marked.parse(text, { breaks: true });
      var safeHtml = global.DOMPurify.sanitize(rawHtml, {
        ALLOWED_TAGS: [
          "p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "a",
          "blockquote", "code", "pre", "h1", "h2", "h3", "h4",
        ],
        ALLOWED_ATTR: ["href", "target", "rel"],
      });
      container.innerHTML = safeHtml;
      // Harden any links the model's markdown produced (marked doesn't add
      // target/rel by default) so they behave like the citations list.
      var links = container.querySelectorAll("a[href]");
      for (var i = 0; i < links.length; i++) {
        links[i].setAttribute("target", "_blank");
        links[i].setAttribute("rel", "noopener noreferrer");
      }
    } catch (err) {
      console.warn("[ask-ai.js] Markdown rendering failed; falling back to plain text:", err);
      container.textContent = text;
    }
  }

  function renderCitations(container, citations) {
    if (!container) return;
    container.innerHTML = "";
    if (!citations.length) return;

    var heading = document.createElement("p");
    heading.className = "ask-ai-citations-heading";
    heading.textContent = "Sources";
    container.appendChild(heading);

    var list = document.createElement("ol");
    list.className = "ask-ai-citations-list";
    citations.forEach(function (c) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = (c && c.url) || "#";
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = (c && (c.title || c.url)) || "Source";
      li.appendChild(a);
      list.appendChild(li);
    });
    container.appendChild(list);
  }

  function setLoading(isLoading) {
    var submitBtn = document.getElementById("ask-ai-submit");
    var input = document.getElementById("ask-ai-input");
    if (submitBtn) submitBtn.textContent = isLoading ? "Asking\u2026" : "Ask";
    if (input) input.disabled = isLoading;
    if (submitBtn) submitBtn.disabled = isLoading;
  }

  function startCooldown(submitBtn) {
    if (!submitBtn) return;
    submitBtn.disabled = true;
    setTimeout(function () {
      submitBtn.disabled = false;
    }, RESUBMIT_COOLDOWN_MS);
  }

  function showStatus(message, isError) {
    var statusEl = document.getElementById("ask-ai-status");
    if (!statusEl) return;
    statusEl.hidden = false;
    statusEl.textContent = message;
    statusEl.classList.toggle("ask-ai-status-error", !!isError);
  }

  function hideStatus() {
    var statusEl = document.getElementById("ask-ai-status");
    if (statusEl) statusEl.hidden = true;
  }

  function wireFloatingButton() {
    var btn = document.getElementById("ask-ai-float-btn");
    var section = document.getElementById("ask-ai-section");
    if (!btn || !section || btn.dataset.wired) return;
    btn.dataset.wired = "true";
    btn.addEventListener("click", function () {
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      var input = document.getElementById("ask-ai-input");
      if (input) {
        setTimeout(function () {
          input.focus();
        }, 350);
      }
    });
  }

  global.initAskAI = initAskAI;
})(window);
