// la-money-votes — starter graph.js, Person 3 owns this file
// Renders a simple funding breakdown into the element with id=containerId.
// app.js calls renderFundingGraph(donors, containerId) once funding.json loads.

function renderFundingGraph(donors, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const total = donors.reduce((sum, d) => sum + d.total, 0);

  container.innerHTML = donors
    .map((d) => {
      const pct = total ? ((d.total / total) * 100).toFixed(1) : 0;
      return `
        <div class="graph-bar-row">
          <span class="graph-bar-label">${d.name}</span>
          <div class="graph-bar-track">
            <div class="graph-bar-fill" style="width:${pct}%"></div>
          </div>
          <span class="graph-bar-value">$${d.total.toLocaleString()}</span>
        </div>
      `;
    })
    .join("");
}
