// la-money-votes — starter app.js, Person 4 owns this file
// Loads data/officials.json on index.html, and one official's
// funding.json + record.json on official.html (via ?id=<official-id>).

const PLACEHOLDER_NAME = "REPLACE_ME";

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Hand-parsed rather than new Date(): "YYYY-MM-DD" parses as UTC and can
// render as the previous day in US timezones.
function formatDate(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
  if (!m) return value || "";
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthIndex = parseInt(m[2], 10) - 1;
  if (monthIndex < 0 || monthIndex > 11) return value;
  return `${months[monthIndex]} ${parseInt(m[3], 10)}, ${m[1]}`;
}

function formatMoney(amount) {
  const n = typeof amount === "number" ? amount : parseFloat(amount) || 0;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function isPlaceholderName(name) {
  return !name || String(name).trim().toUpperCase() === PLACEHOLDER_NAME;
}

// funding.json still has "REPLACE_ME" for cd14/cd11's official.name — fall
// back to the office title rather than showing the raw placeholder token.
function displayName(official) {
  return isPlaceholderName(official.name) ? official.office : official.name;
}

async function loadOfficialsIndex() {
  const list = document.getElementById("official-list");
  if (!list) return;

  let officials;
  try {
    const res = await fetch("data/officials.json");
    officials = await res.json();
  } catch (err) {
    list.innerHTML = `<p class="load-error">Could not load officials list.</p>`;
    return;
  }

  list.innerHTML = officials
    .map((o) => {
      const pending = isPlaceholderName(o.name);
      return `
        <a class="official-card" href="official.html?id=${encodeURIComponent(o.id)}">
          <h2>${escapeHtml(displayName(o))}</h2>
          <p class="official-card-office">${escapeHtml(o.office)}</p>
          ${pending ? `<p class="official-card-pending">Name pending confirmation</p>` : ""}
        </a>
      `;
    })
    .join("");
}

function renderReelectionBanner(reelection) {
  const el = document.getElementById("reelection-banner");
  if (!el) return;

  if (!reelection) {
    el.hidden = true;
    return;
  }

  el.hidden = false;
  el.classList.toggle("active", !!reelection.active);
  el.classList.toggle("inactive", !reelection.active);

  const parts = [
    `<span class="reelection-status">${
      reelection.active ? "Running for re-election" : "Not currently in an active re-election campaign"
    }</span>`,
  ];
  if (reelection.election_date) {
    parts.push(`<span class="reelection-date">Election date: ${escapeHtml(formatDate(reelection.election_date))}</span>`);
  }
  if (reelection.committee) {
    parts.push(`<span class="reelection-committee">${escapeHtml(reelection.committee)}</span>`);
  }
  el.innerHTML = parts.join("");
}

function renderFundingStats(donors) {
  const el = document.getElementById("funding-stats");
  if (!el) return;
  const total = donors.reduce((sum, d) => sum + (typeof d.total === "number" ? d.total : parseFloat(d.total) || 0), 0);
  el.textContent = `${formatMoney(total)} raised from ${donors.length} donor${donors.length === 1 ? "" : "s"}`;
}

// role/outcome filters. "voted" covers any voted_* role (voted_yes, voted_no, ...);
// "passed" is outcome-based, not role-based, so it can overlap with "proposed".
const RECORD_FILTERS = {
  all: () => true,
  proposed: (item) => item.role === "proposed",
  passed: (item) => item.outcome === "passed",
  voted: (item) => /^voted_/.test(item.role || ""),
};

function recordRowHtml(item) {
  const role = String(item.role || "").replace(/_/g, " ");
  return `
    <tr>
      <td class="record-date">${escapeHtml(formatDate(item.date))}</td>
      <td class="record-file">${escapeHtml(item.council_file)}</td>
      <td>${escapeHtml(item.title)}</td>
      <td><span class="role-badge">${escapeHtml(role)}</span></td>
      <td><span class="outcome-badge outcome-${escapeHtml(item.outcome)}">${escapeHtml(item.outcome)}</span></td>
    </tr>
  `;
}

function renderRecordTerm(items, term, filterKey) {
  const table = document.getElementById(`record-table-${term}`);
  const emptyEl = document.getElementById(`record-empty-${term}`);
  if (!table || !emptyEl) return;

  const filterFn = RECORD_FILTERS[filterKey] || RECORD_FILTERS.all;
  const filtered = items
    .filter((item) => item.term === term)
    .filter(filterFn)
    .slice()
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)); // newest first

  table.querySelector("tbody").innerHTML = filtered.map(recordRowHtml).join("");
  table.hidden = filtered.length === 0;
  emptyEl.hidden = filtered.length !== 0;
}

function renderRecord(items, filterKey) {
  renderRecordTerm(items, "current", filterKey);
  renderRecordTerm(items, "previous", filterKey);
}

function wireRecordFilters(items) {
  const buttons = document.querySelectorAll(".filter-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderRecord(items, btn.dataset.filter);
    });
  });
}

async function loadOfficialPage() {
  const nameEl = document.getElementById("official-name");
  if (!nameEl) return;

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  if (!id) {
    nameEl.textContent = "No official specified";
    return;
  }

  let funding, record;
  try {
    [funding, record] = await Promise.all([
      fetch(`data/officials/${id}/funding.json`).then((r) => {
        if (!r.ok) throw new Error("funding.json not found");
        return r.json();
      }),
      fetch(`data/officials/${id}/record.json`).then((r) => {
        if (!r.ok) throw new Error("record.json not found");
        return r.json();
      }),
    ]);
  } catch (err) {
    nameEl.textContent = "Official not found";
    return;
  }

  const official = funding.official;
  nameEl.textContent = displayName(official);
  document.getElementById("official-office").textContent = official.office;

  renderReelectionBanner(official.reelection);
  renderFundingStats(funding.donors || []);
  wireRecordFilters(record.items || []);
  renderRecord(record.items || [], "all");

  if (typeof renderFundingGraph === "function") {
    renderFundingGraph("graph", funding);
  }
}

loadOfficialsIndex();
loadOfficialPage();
