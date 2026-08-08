// la-money-votes — starter app.js, Person 4 owns this file
// Loads data/officials.json on index.html, and one official's
// funding.json + record.json on official.html (via ?id=<official-id>).

async function loadOfficialsIndex() {
  const list = document.getElementById("official-list");
  if (!list) return;

  const res = await fetch("data/officials.json");
  const officials = await res.json();

  list.innerHTML = officials
    .map(
      (o) =>
        `<li><a href="official.html?id=${o.id}">${o.name}</a> — ${o.office}</li>`
    )
    .join("");
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

  const [funding, record] = await Promise.all([
    fetch(`data/officials/${id}/funding.json`).then((r) => r.json()),
    fetch(`data/officials/${id}/record.json`).then((r) => r.json()),
  ]);

  nameEl.textContent = funding.official.name;
  document.getElementById("official-office").textContent =
    funding.official.office;

  const donorList = document.getElementById("donor-list");
  donorList.innerHTML = funding.donors
    .map((d) => `<li>${d.name} (${d.type}) — $${d.total.toLocaleString()}</li>`)
    .join("");

  const recordList = document.getElementById("record-list");
  recordList.innerHTML = record.items
    .map(
      (i) =>
        `<li>${i.date} — ${i.title} (${i.role}, ${i.outcome})</li>`
    )
    .join("");

  if (typeof renderFundingGraph === "function") {
    renderFundingGraph(funding.donors, "funding-graph");
  }
}

loadOfficialsIndex();
loadOfficialPage();
