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

// The "YYYY-MM-DD" prefix of a date string, or null if it isn't one. Dates stay
// as strings all the way through: in that form they compare correctly with <
// and >, so nothing here has to touch Date() and risk a timezone shift.
function isoDay(value) {
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(String(value || ""));
  return m ? m[1] : null;
}

// Today in the reader's own timezone, in the same comparable form.
function todayIso() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
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

// Falls back to the office title instead of showing a raw placeholder token,
// in case an official's name isn't filled in yet (e.g. a newly added entry).
function displayName(official) {
  return isPlaceholderName(official.name) ? official.office : official.name;
}

// Renders "Source: <name>" into el, linked when the source carries a URL.
// `detail` is appended in parentheses — used to name the exact committees a
// donor list was drawn from.
function renderSourceNote(el, source, detail) {
  if (!el) return;
  if (!source || !source.name) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const label = escapeHtml(source.name);
  const linked = source.url
    ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${label}</a>`
    : label;
  el.innerHTML = `Source: ${linked}${detail ? ` (${escapeHtml(detail)})` : ""}`;
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

// ---------------------------------------------------------------------------
// Re-election banner
// ---------------------------------------------------------------------------

const ELECTION_RESULT_LABELS = {
  won: "Won re-election",
  lost: "Lost re-election",
  runoff: "Advanced to a runoff",
};

function renderReelectionBanner(reelection) {
  const el = document.getElementById("reelection-banner");
  if (!el) return;

  if (!reelection) {
    el.hidden = true;
    return;
  }

  // The election date decides the tense, not the stored `active` flag. `active`
  // is frozen when the data is built, so on the day after an election a page
  // built before it would still claim the official is "running for re-election"
  // until someone re-ran the pipeline. Comparing against today on every page
  // load means the banner can't go stale between builds.
  const electionDay = isoDay(reelection.election_date);
  const held = electionDay !== null && electionDay < todayIso();
  const upcoming = !!reelection.active && !held;

  el.hidden = false;
  el.classList.toggle("active", upcoming);
  el.classList.toggle("held", held);
  el.classList.toggle("inactive", !upcoming && !held);

  let status;
  if (upcoming) {
    status = "Running for re-election";
  } else if (held) {
    status = ELECTION_RESULT_LABELS[reelection.result] || "Election already held";
  } else {
    status = "Not currently in an active re-election campaign";
  }

  const parts = [`<span class="reelection-status">${escapeHtml(status)}</span>`];
  if (electionDay) {
    parts.push(
      `<span class="reelection-date">${held ? "Election held" : "Election date"}: ${escapeHtml(
        formatDate(electionDay)
      )}</span>`
    );
  }
  if (reelection.committee) {
    parts.push(`<span class="reelection-committee">${escapeHtml(reelection.committee)}</span>`);
  }
  el.innerHTML = parts.join("");
}

// ---------------------------------------------------------------------------
// Donor list — filter by type, sort by any column
// ---------------------------------------------------------------------------

const DONOR_TYPE_LABELS = { individual: "Individual", pac: "PAC", business: "Business" };

function donorTotal(donor) {
  return typeof donor.total === "number" ? donor.total : parseFloat(donor.total) || 0;
}

function donorContributions(donor) {
  return Array.isArray(donor.contributions) ? donor.contributions : [];
}

// build_funding.py writes contributions oldest-first, but scan rather than
// index so a hand-edited or differently-ordered file still sorts correctly.
function donorLatestDate(donor) {
  let latest = null;
  donorContributions(donor).forEach((c) => {
    const day = isoDay(c && c.date);
    if (day && (latest === null || day > latest)) latest = day;
  });
  return latest;
}

// Each sort key maps to the value rows are compared on; strings compare
// case-insensitively, everything else numerically or as an ISO date string.
const DONOR_SORT_VALUES = {
  name: (d) => String(d.name || "").toLowerCase(),
  type: (d) => String(d.type || ""),
  employer: (d) => String(d.employer || "").toLowerCase(),
  count: (d) => donorContributions(d).length,
  latest: (d) => donorLatestDate(d) || "",
  total: (d) => donorTotal(d),
};

// Clicking a column sorts it the way that column is usually read first: names
// A–Z, money and dates biggest/newest first.
const DONOR_SORT_DEFAULT_DIR = {
  name: "asc",
  type: "asc",
  employer: "asc",
  count: "desc",
  latest: "desc",
  total: "desc",
};

const donorState = { donors: [], type: "all", sortKey: "total", sortDir: "desc" };

function sortedDonors(donors, key, dir) {
  const valueOf = DONOR_SORT_VALUES[key] || DONOR_SORT_VALUES.total;
  const sign = dir === "asc" ? 1 : -1;
  return donors
    .map((donor, index) => ({ donor, index })) // index keeps equal rows in a stable order
    .sort((a, b) => {
      const av = valueOf(a.donor);
      const bv = valueOf(b.donor);
      if (av < bv) return -1 * sign;
      if (av > bv) return 1 * sign;
      return a.index - b.index;
    })
    .map((entry) => entry.donor);
}

// One <li> per contribution, with a "Source" link when build_funding.py
// resolved one (see CONTRACT.md's donors[].contributions[].source_url) —
// plain text otherwise, never a guessed link.
function contributionDetailHtml(c) {
  const dateLabel = escapeHtml(formatDate(c.date) || "Undated");
  const amountLabel = escapeHtml(formatMoney(c.amount));
  const sourceLink = c.source_url
    ? `<a href="${escapeHtml(c.source_url)}" target="_blank" rel="noopener noreferrer">Source</a>`
    : '<span class="muted">No filing link on file</span>';
  return `<li><span class="contribution-date">${dateLabel}</span><span class="contribution-amount">${amountLabel}</span><span class="contribution-source">${sourceLink}</span></li>`;
}

function donorRowHtml(donor, rowIndex) {
  const type = String(donor.type || "");
  const typeLabel = DONOR_TYPE_LABELS[type] || type || "Unknown";
  const contributions = donorContributions(donor);
  const latest = donorLatestDate(donor);
  const detailsId = `donor-details-${rowIndex}`;

  return `
    <tr>
      <td class="donor-name">${escapeHtml(donor.name)}</td>
      <td><span class="type-badge type-${escapeHtml(type || "unknown")}">${escapeHtml(typeLabel)}</span></td>
      <td class="donor-employer">${donor.employer ? escapeHtml(donor.employer) : '<span class="muted">—</span>'}</td>
      <td class="num">${
        contributions.length
          ? `<button type="button" class="donor-details-toggle" aria-expanded="false" aria-controls="${detailsId}">${contributions.length}</button>`
          : contributions.length
      }</td>
      <td class="donor-date">${latest ? escapeHtml(formatDate(latest)) : '<span class="muted">—</span>'}</td>
      <td class="num donor-total">${escapeHtml(formatMoney(donorTotal(donor)))}</td>
    </tr>
    ${
      contributions.length
        ? `<tr class="donor-details-row" id="${detailsId}" hidden>
            <td colspan="6">
              <ul class="donor-details-list">${contributions.map(contributionDetailHtml).join("")}</ul>
            </td>
          </tr>`
        : ""
    }
  `;
}

function renderDonors() {
  const table = document.getElementById("donor-table");
  const emptyEl = document.getElementById("donor-empty");
  const summaryEl = document.getElementById("donor-summary");
  if (!table || !emptyEl) return;

  const { donors, type, sortKey, sortDir } = donorState;
  const filtered = type === "all" ? donors.slice() : donors.filter((d) => d.type === type);
  const rows = sortedDonors(filtered, sortKey, sortDir);

  table.querySelector("tbody").innerHTML = rows.map((donor, i) => donorRowHtml(donor, i)).join("");
  table.hidden = rows.length === 0;
  emptyEl.hidden = rows.length !== 0;
  wireDonorDetailToggles();

  if (summaryEl) {
    const shownTotal = rows.reduce((sum, d) => sum + donorTotal(d), 0);
    const scope = type === "all" ? "" : ` ${DONOR_TYPE_LABELS[type] || type}`;
    summaryEl.textContent = `Showing ${rows.length} of ${donors.length}${scope} donor${
      donors.length === 1 ? "" : "s"
    } · ${formatMoney(shownTotal)}`;
  }

  // Screen readers get the sort state from aria-sort; sighted readers get the
  // arrow. Both come off the same source of truth.
  table.querySelectorAll("th[data-sort]").forEach((th) => {
    const isActive = th.dataset.sort === sortKey;
    th.setAttribute("aria-sort", isActive ? (sortDir === "asc" ? "ascending" : "descending") : "none");
    th.classList.toggle("sorted", isActive);
    const indicator = th.querySelector(".sort-indicator");
    if (indicator) indicator.textContent = isActive ? (sortDir === "asc" ? "▲" : "▼") : "";
  });
}

// Every render rebuilds the tbody from scratch, so toggles are re-wired each
// time rather than persisted — a re-sort or re-filter always starts collapsed.
function wireDonorDetailToggles() {
  document.querySelectorAll(".donor-details-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = document.getElementById(btn.getAttribute("aria-controls"));
      if (!row) return;
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!expanded));
      row.hidden = expanded;
    });
  });
}

function wireDonorSorting() {
  document.querySelectorAll("#donor-table th[data-sort] .sort-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.closest("th").dataset.sort;
      if (donorState.sortKey === key) {
        donorState.sortDir = donorState.sortDir === "asc" ? "desc" : "asc";
      } else {
        donorState.sortKey = key;
        donorState.sortDir = DONOR_SORT_DEFAULT_DIR[key] || "desc";
      }
      renderDonors();
    });
  });
}

// Buttons are built from the data rather than hardcoded, so a type that nobody
// in this donor list belongs to shows a 0 and can't be selected into an empty
// table — and a type we haven't seen before still gets a button.
function wireDonorFilters(donors) {
  const container = document.querySelector(".donor-filters");
  if (!container) return;

  const counts = donors.reduce((acc, d) => {
    const key = String(d.type || "unknown");
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const types = Object.keys(DONOR_TYPE_LABELS)
    .concat(Object.keys(counts).filter((t) => !(t in DONOR_TYPE_LABELS)))
    .filter((t, i, all) => all.indexOf(t) === i);

  container.innerHTML = [{ key: "all", label: "All", count: donors.length }]
    .concat(types.map((t) => ({ key: t, label: DONOR_TYPE_LABELS[t] || t, count: counts[t] || 0 })))
    .map(
      ({ key, label, count }) => `
        <button type="button" class="filter-btn${key === donorState.type ? " active" : ""}"
                data-donor-type="${escapeHtml(key)}"${count === 0 ? " disabled" : ""}>
          ${escapeHtml(label)} <span class="filter-count">${count}</span>
        </button>`
    )
    .join("");

  container.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      donorState.type = btn.dataset.donorType;
      renderDonors();
    });
  });
}

function renderFundingStats(donors) {
  const el = document.getElementById("funding-stats");
  if (!el) return;
  const total = donors.reduce((sum, d) => sum + donorTotal(d), 0);
  el.textContent = `${formatMoney(total)} raised from ${donors.length} donor${donors.length === 1 ? "" : "s"}`;
}

function renderFunding(funding) {
  const donors = funding.donors || [];
  renderFundingStats(donors);
  donorState.donors = donors;
  wireDonorFilters(donors);
  wireDonorSorting();
  renderDonors();
  renderSourceNote(
    document.getElementById("funding-source"),
    funding.source,
    (funding.source && (funding.source.committees || []).join(", ")) || ""
  );
}

// ---------------------------------------------------------------------------
// Voting / proposal record
// ---------------------------------------------------------------------------

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
  const file = escapeHtml(item.council_file);
  // Items with no verified primary source (mayoral directives, for now) stay
  // plain text rather than getting a link that goes somewhere approximate.
  const fileCell = item.source_url
    ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer">${file}</a>`
    : file;
  return `
    <tr>
      <td class="record-date">${escapeHtml(formatDate(item.date))}</td>
      <td class="record-file">${fileCell}</td>
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
  const inTerm = items.filter((item) => item.term === term);
  const filtered = inTerm
    .filter(filterFn)
    .slice()
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)); // newest first

  table.querySelector("tbody").innerHTML = filtered.map(recordRowHtml).join("");
  table.hidden = filtered.length === 0;
  emptyEl.hidden = filtered.length !== 0;
  // An empty term and an empty filter result look identical but mean very
  // different things — a councilmember who just started a new term has nothing
  // on file yet, which shouldn't read as "your filter matched nothing".
  emptyEl.textContent = inTerm.length
    ? "No matching items."
    : "Nothing on file for this term yet.";
}

function renderRecord(items, filterKey) {
  renderRecordTerm(items, "current", filterKey);
  renderRecordTerm(items, "previous", filterKey);
}

function wireRecordFilters(items) {
  // Scoped to this group: the donor list uses .filter-btn for the same pill
  // styling, and an unscoped query would wire those into the record filters.
  const buttons = document.querySelectorAll(".record-filters .filter-btn");
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
  renderFunding(funding);
  wireRecordFilters(record.items || []);
  renderRecord(record.items || [], "all");
  renderSourceNote(document.getElementById("record-source"), record.source);

  if (typeof renderFundingGraph === "function") {
    renderFundingGraph("graph", funding);
  }
}

loadOfficialsIndex();
loadOfficialPage();
