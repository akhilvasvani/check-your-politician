// la-money-votes — profile.js, powers profile.html only.
// Loads endorsements.json, funding.json, and record.json for ?id=<official-id>
// and renders them into three tabs: Endorsements, Contributions, Voting Record.

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => {
    switch (ch) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

function formatCurrency(amount) {
  const n = Number(amount);
  return Number.isFinite(n) ? `$${n.toLocaleString()}` : "$0";
}

function outcomeBadge(outcome) {
  const cls =
    outcome === "passed" ? "badge-passed" : outcome === "failed" ? "badge-failed" : "badge-pending";
  return `<span class="badge ${cls}">${escapeHtml(outcome || "unknown")}</span>`;
}

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-button");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.setAttribute("aria-selected", "false"));
      btn.setAttribute("aria-selected", "true");

      document.querySelectorAll(".tab-panel").forEach((panel) => {
        panel.hidden = true;
      });
      document.getElementById(`tab-${btn.dataset.tab}`).hidden = false;
    });
  });
}

function renderEndorsements(data) {
  const summary = document.getElementById("endorsements-summary");
  const body = document.getElementById("endorsements-body");
  const endorsements = Array.isArray(data.endorsements) ? data.endorsements : [];

  summary.textContent = `${endorsements.length} organizational endorsement${
    endorsements.length === 1 ? "" : "s"
  } on file — ${data.lean_label || "lean unclassified"}.`;

  body.innerHTML = endorsements
    .map(
      (e) => `
        <tr>
          <td>${escapeHtml(e.organization)}</td>
          <td><span class="badge">${escapeHtml((e.category || "").replace(/_/g, " "))}</span></td>
          <td>${escapeHtml(e.date || "—")}</td>
        </tr>
      `
    )
    .join("");
}

function renderContributions(funding) {
  const donors = Array.isArray(funding.donors) ? funding.donors : [];
  const rows = [];

  donors.forEach((donor) => {
    const contributions = Array.isArray(donor.contributions) ? donor.contributions : [];
    if (!contributions.length) {
      rows.push({ donor, date: null, amount: donor.total });
      return;
    }
    contributions.forEach((c) => {
      rows.push({ donor, date: c && c.date, amount: c && c.amount });
    });
  });

  rows.sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  const total = rows.reduce((sum, r) => sum + (Number(r.amount) || 0), 0);

  document.getElementById("contributions-total").textContent = formatCurrency(total);
  document.getElementById("contributions-count").textContent = rows.length;

  document.getElementById("contributions-body").innerHTML = rows
    .map(
      (r) => `
        <tr>
          <td>${escapeHtml(r.donor.name)}</td>
          <td><span class="badge">${escapeHtml(r.donor.type || "individual")}</span></td>
          <td>${escapeHtml(r.donor.employer || "—")}</td>
          <td>${escapeHtml(r.date || "—")}</td>
          <td>${formatCurrency(r.amount)}</td>
        </tr>
      `
    )
    .join("");
}

function renderRecord(record) {
  const items = Array.isArray(record.items) ? [...record.items] : [];
  items.sort((a, b) => (b.date || "").localeCompare(a.date || ""));

  document.getElementById("record-summary").textContent =
    `${items.length} legislative record item${items.length === 1 ? "" : "s"}.`;

  document.getElementById("record-body").innerHTML = items
    .map(
      (i) => `
        <tr>
          <td>${escapeHtml(i.council_file)}</td>
          <td>${escapeHtml(i.title)}</td>
          <td><span class="badge">${escapeHtml((i.role || "").replace(/_/g, " "))}</span></td>
          <td>${escapeHtml(i.date)}</td>
          <td>${outcomeBadge(i.outcome)}</td>
          <td>${escapeHtml(i.term)}</td>
        </tr>
      `
    )
    .join("");
}

async function loadProfile() {
  const loadingEl = document.getElementById("profile-loading");
  const rootEl = document.getElementById("profile-root");
  const errorEl = document.getElementById("profile-error");

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");

  if (!id) {
    loadingEl.hidden = true;
    errorEl.hidden = false;
    errorEl.textContent = "No official specified. Go back and pick one from the spectrum.";
    return;
  }

  try {
    const [officials, endorsements, funding, record] = await Promise.all([
      fetch("data/officials.json").then((r) => r.json()),
      fetch(`data/officials/${id}/endorsements.json`).then((r) => r.json()),
      fetch(`data/officials/${id}/funding.json`).then((r) => r.json()),
      fetch(`data/officials/${id}/record.json`).then((r) => r.json()),
    ]);

    const official = officials.find((o) => o.id === id) || funding.official || {};

    document.getElementById("profile-name").textContent =
      official.name || funding.official.name;
    document.getElementById("profile-office").textContent =
      official.office || funding.official.office;
    document.getElementById("profile-lean").textContent = endorsements.lean_label || "";
    document.getElementById("profile-avatar").innerHTML = endorsements.photo_url
      ? `<img src="${endorsements.photo_url}" alt="${escapeHtml(official.name)}" />`
      : "";

    renderEndorsements(endorsements);
    renderContributions(funding);
    renderRecord(record);

    setupTabs();

    loadingEl.hidden = true;
    rootEl.hidden = false;
  } catch (err) {
    loadingEl.hidden = true;
    errorEl.hidden = false;
    errorEl.textContent = "Couldn't load this official's profile. Try refreshing.";
    console.error(err);
  }
}

loadProfile();
