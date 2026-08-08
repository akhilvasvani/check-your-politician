// la-money-votes — js/graph.js, Person 3 owns this file.
// Exposes exactly one global: renderFundingGraph(containerId, fundingData).
// Requires Cytoscape.js to already be loaded on the page, e.g.:
//   <script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>

const DONOR_COLORS = {
  individual: "#2b6cb0",
  pac: "#dd6b20",
  business: "#2f855a",
};
const DEFAULT_DONOR_COLOR = "#4a5568";
const OFFICIAL_COLOR = "#1a1a1a";

const OFFICIAL_NODE_SIZE = 110;
const DONOR_NODE_MIN = 24;
const DONOR_NODE_MAX = 90;
const EDGE_WIDTH_MIN = 2;
const EDGE_WIDTH_MAX = 14;

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

function sqrtScale(value, maxValue, minOut, maxOut) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0 || !maxValue || maxValue <= 0) return minOut;
  const ratio = Math.sqrt(Math.min(n, maxValue) / maxValue);
  return minOut + ratio * (maxOut - minOut);
}

function buildElements(official, donors) {
  const officialId = `official:${official.id || "official"}`;
  const elements = [
    {
      data: {
        id: officialId,
        label: official.name || "Official",
        kind: "official",
      },
    },
  ];

  const totals = donors.map((d) => Number(d && d.total) || 0);
  const maxTotal = totals.length ? Math.max(...totals) : 0;

  donors.forEach((donor, idx) => {
    const donorId = `donor:${idx}`;
    const total = Number(donor && donor.total) || 0;
    const rawType = donor && donor.type;
    const type = DONOR_COLORS[rawType] ? rawType : "individual";
    const contributions = Array.isArray(donor && donor.contributions)
      ? donor.contributions
      : [];

    elements.push({
      data: {
        id: donorId,
        label: (donor && donor.name) || "Unknown donor",
        kind: "donor",
        donorType: type,
        total,
        employer: (donor && donor.employer) ?? null,
        contributions,
        nodeSize: sqrtScale(total, maxTotal, DONOR_NODE_MIN, DONOR_NODE_MAX),
      },
    });

    elements.push({
      data: {
        id: `edge:${donorId}`,
        source: officialId,
        target: donorId,
        edgeWidth: sqrtScale(total, maxTotal, EDGE_WIDTH_MIN, EDGE_WIDTH_MAX),
      },
    });
  });

  return elements;
}

function buildStylesheet() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        color: "#1a1a1a",
        "font-size": 10,
        "text-valign": "bottom",
        "text-margin-y": 4,
        "text-wrap": "ellipsis",
        "text-max-width": "80px",
      },
    },
    {
      selector: 'node[kind = "official"]',
      style: {
        "background-color": OFFICIAL_COLOR,
        color: "#ffffff",
        "font-weight": "bold",
        "font-size": 13,
        "text-valign": "center",
        width: OFFICIAL_NODE_SIZE,
        height: OFFICIAL_NODE_SIZE,
        "z-index": 10,
      },
    },
    {
      selector: 'node[kind = "donor"]',
      style: {
        width: "data(nodeSize)",
        height: "data(nodeSize)",
        "background-color": DEFAULT_DONOR_COLOR,
        "border-width": 2,
        "border-color": "#ffffff",
      },
    },
    ...Object.keys(DONOR_COLORS).map((type) => ({
      selector: `node[donorType = "${type}"]`,
      style: { "background-color": DONOR_COLORS[type] },
    })),
    {
      selector: 'node[kind = "donor"]:selected',
      style: { "border-color": "#000000", "border-width": 3 },
    },
    {
      selector: "edge",
      style: {
        width: "data(edgeWidth)",
        "line-color": "#cbd5e0",
        "curve-style": "bezier",
      },
    },
  ];
}

function buildLayout() {
  return {
    name: "concentric",
    concentric: (node) => (node.data("kind") === "official" ? 10 : 1),
    levelWidth: () => 1,
    minNodeSpacing: 40,
    animate: false,
  };
}

function renderTooltipContent(tooltipEl, donorData) {
  const contributions = Array.isArray(donorData.contributions)
    ? donorData.contributions
    : [];

  const rows = contributions.length
    ? contributions
        .map((c) => {
          const date = c && c.date ? escapeHtml(c.date) : "Unknown date";
          const amount = formatCurrency(c && c.amount);
          return `<li style="display:flex;justify-content:space-between;gap:12px;padding:2px 0;">
            <span>${date}</span><span>${amount}</span>
          </li>`;
        })
        .join("")
    : '<li style="opacity:0.7;">No contribution history</li>';

  tooltipEl.innerHTML = `
    <button type="button" data-graph-tooltip-close
      style="position:absolute;top:4px;right:6px;border:none;background:none;
      font-size:14px;line-height:1;cursor:pointer;color:#666;">&times;</button>
    <div style="font-weight:600;margin-bottom:4px;padding-right:16px;">${escapeHtml(
      donorData.label
    )}</div>
    <div style="font-size:12px;opacity:0.8;margin-bottom:6px;">
      ${donorData.employer ? escapeHtml(donorData.employer) : "Employer unknown"}
    </div>
    <div style="font-weight:600;margin-bottom:6px;">Total: ${formatCurrency(
      donorData.total
    )}</div>
    <ul style="list-style:none;margin:0;padding:0;font-size:12px;max-height:160px;overflow-y:auto;">
      ${rows}
    </ul>
  `;
}

function positionTooltip(tooltipEl, node, cy, containerEl) {
  const pos = node.renderedPosition();
  const containerRect = containerEl.getBoundingClientRect();
  const tooltipWidth = 220;

  let left = pos.x + 16;
  if (left + tooltipWidth > containerRect.width) {
    left = Math.max(8, pos.x - tooltipWidth - 16);
  }
  const top = Math.max(8, pos.y - 20);

  tooltipEl.style.left = `${left}px`;
  tooltipEl.style.top = `${top}px`;
}

function hideTooltip(tooltipEl) {
  tooltipEl.style.display = "none";
}

/**
 * Renders an interactive funding graph (official + donors) into containerId.
 * @param {string} containerId - id of the element to render into.
 * @param {object} fundingData - parsed funding.json: { official, donors }.
 */
function renderFundingGraph(containerId, fundingData) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (typeof cytoscape === "undefined") {
    container.innerHTML =
      '<p style="color:#a00;">renderFundingGraph: cytoscape.js is not loaded. ' +
      'Add &lt;script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"&gt;&lt;/script&gt; ' +
      "before js/graph.js.</p>";
    return;
  }

  if (container.__cyInstance) {
    container.__cyInstance.destroy();
    container.__cyInstance = null;
  }
  container.innerHTML = "";

  const official = (fundingData && fundingData.official) || {};
  const donors = Array.isArray(fundingData && fundingData.donors)
    ? fundingData.donors
    : [];

  if (!donors.length) {
    container.innerHTML =
      '<p style="opacity:0.7;">No donor data available for this official.</p>';
    return;
  }

  container.style.position = "relative";

  const canvasEl = document.createElement("div");
  canvasEl.style.width = "100%";
  canvasEl.style.height = "480px";
  container.appendChild(canvasEl);

  const tooltipEl = document.createElement("div");
  tooltipEl.style.position = "absolute";
  tooltipEl.style.display = "none";
  tooltipEl.style.width = "220px";
  tooltipEl.style.background = "#ffffff";
  tooltipEl.style.border = "1px solid #d0d0d0";
  tooltipEl.style.borderRadius = "8px";
  tooltipEl.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
  tooltipEl.style.padding = "10px 12px";
  tooltipEl.style.fontSize = "12px";
  tooltipEl.style.zIndex = "20";
  container.appendChild(tooltipEl);

  const cy = cytoscape({
    container: canvasEl,
    elements: buildElements(official, donors),
    style: buildStylesheet(),
    layout: buildLayout(),
    minZoom: 0.3,
    maxZoom: 3,
  });

  container.__cyInstance = cy;

  cy.on("tap", "node[kind = \"donor\"]", (evt) => {
    const node = evt.target;
    renderTooltipContent(tooltipEl, node.data());
    positionTooltip(tooltipEl, node, cy, canvasEl);
    tooltipEl.style.display = "block";
  });

  cy.on("tap", (evt) => {
    if (evt.target === cy || evt.target.data("kind") !== "donor") {
      hideTooltip(tooltipEl);
    }
  });

  cy.on("drag", () => hideTooltip(tooltipEl));
  cy.on("zoom pan", () => hideTooltip(tooltipEl));

  tooltipEl.addEventListener("click", (evt) => {
    if (evt.target && evt.target.hasAttribute("data-graph-tooltip-close")) {
      hideTooltip(tooltipEl);
    }
  });

  const handleResize = () => {
    cy.resize();
    cy.fit(undefined, 20);
  };
  window.addEventListener("resize", handleResize);
  cy.on("destroy", () => window.removeEventListener("resize", handleResize));
}
