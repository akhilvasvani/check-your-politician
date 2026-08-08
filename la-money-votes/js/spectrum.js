// la-money-votes — spectrum.js, powers spectrum.html only.
// Fetches officials + their endorsements.json (for lean_score, photo, label)
// and positions each as a circular, hoverable/clickable node on a left-right
// axis. Clicking a node navigates to profile.html?id=<official-id>.

async function loadSpectrum() {
  const loadingEl = document.getElementById("spectrum-loading");
  const rootEl = document.getElementById("spectrum-root");
  const errorEl = document.getElementById("spectrum-error");
  const nodesEl = document.getElementById("spectrum-nodes");

  try {
    const officials = await fetch("data/officials.json").then((r) => r.json());

    const withLean = await Promise.all(
      officials.map(async (official) => {
        try {
          const endorsements = await fetch(
            `data/officials/${official.id}/endorsements.json`
          ).then((r) => r.json());
          return { ...official, ...endorsements };
        } catch {
          return { ...official, lean_score: 0, lean_label: "Unknown", endorsements: [] };
        }
      })
    );

    nodesEl.innerHTML = withLean.map(renderNode).join("");

    loadingEl.hidden = true;
    rootEl.hidden = false;
  } catch (err) {
    loadingEl.hidden = true;
    errorEl.hidden = false;
    errorEl.textContent = "Couldn't load officials. Try refreshing.";
    console.error(err);
  }
}

function renderNode(official) {
  const score = Number.isFinite(official.lean_score) ? official.lean_score : 0;
  const clamped = Math.max(-100, Math.min(100, score));
  const leftPercent = ((clamped + 100) / 200) * 100;
  const topCount = Array.isArray(official.endorsements)
    ? official.endorsements.length
    : 0;

  return `
    <button
      type="button"
      class="spectrum-node"
      style="left:${leftPercent}%"
      onclick="window.location.href='profile.html?id=${encodeURIComponent(official.id)}'"
    >
      <span class="spectrum-node-avatar">
        <img src="${official.photo_url || ""}" alt="${escapeHtml(official.name)}" loading="lazy" />
      </span>
      <span class="spectrum-node-name">${escapeHtml(official.name)}</span>
      <span class="spectrum-node-tooltip">
        <strong>${escapeHtml(official.name)} — ${escapeHtml(official.office)}</strong>
        ${escapeHtml(official.lean_label || "")}<br />
        ${topCount} organizational endorsement${topCount === 1 ? "" : "s"} on file.
        <br />Click for full profile &rarr;
      </span>
    </button>
  `;
}

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

loadSpectrum();
