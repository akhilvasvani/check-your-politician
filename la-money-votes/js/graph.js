/*!
 * graph.js — LA official funding graph
 *
 * Exposes exactly one global:
 *   renderFundingGraph(containerId, fundingData) -> cytoscape instance | null
 *
 * Requires Cytoscape.js to already be on the page (see README / <script> tag).
 * No build step, no imports. Load with <script src="js/graph.js"></script>.
 */
/* global cytoscape */
(function (global) {
  'use strict';

  // ---------------------------------------------------------------------------
  // Tunables
  // ---------------------------------------------------------------------------

  // Muted rather than saturated: the type encoding the spec requires, but calm
  // enough to read as designed. Still distinct under projector washout.
  var TYPE_COLORS = {
    individual: '#4a6fa5', // dusty blue
    pac: '#c67b4a',        // terracotta
    business: '#5d8a6f'    // sage
  };
  var UNKNOWN_TYPE_COLOR = '#9aa0a6'; // anything not in the schema
  var OFFICIAL_COLOR = '#1a1a1a';

  // Color lives on the nodes only. Edges are neutral and carry meaning through
  // width alone, so the graph reads quietly until you engage with it.
  var EDGE_COLOR = '#d4d7db';

  var DONOR_SIZE_MIN = 26;
  var DONOR_SIZE_MAX = 78;
  var OFFICIAL_SIZE = 92;

  var EDGE_WIDTH_MIN = 1;
  var EDGE_WIDTH_MAX = 6;

  var FALLBACK_MIN_HEIGHT = 480; // only applied if the container has zero height

  // Tracks per-container state so a second render() tears down the first.
  var mounted = [];

  // ---------------------------------------------------------------------------
  // Small helpers
  // ---------------------------------------------------------------------------

  function toNumber(value) {
    var n = typeof value === 'number' ? value : parseFloat(value);
    return isFinite(n) ? n : 0;
  }

  function toText(value) {
    if (value === null || value === undefined) return '';
    return String(value).trim();
  }

  function escapeHtml(value) {
    return toText(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  var moneyFormatter = null;
  function formatMoney(amount) {
    var n = toNumber(amount);
    if (!moneyFormatter && global.Intl && Intl.NumberFormat) {
      moneyFormatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: n % 1 === 0 ? 0 : 2
      });
    }
    if (moneyFormatter) {
      try { return moneyFormatter.format(n); } catch (e) { /* fall through */ }
    }
    return '$' + n.toFixed(0);
  }

  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // Parsed by hand rather than with Date() — "2026-03-04" parses as UTC and can
  // render as the previous day in US timezones.
  function formatDate(value) {
    var raw = toText(value);
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
    if (!m) return raw || 'Undated';
    var monthIndex = parseInt(m[2], 10) - 1;
    if (monthIndex < 0 || monthIndex > 11) return raw;
    return MONTHS[monthIndex] + ' ' + parseInt(m[3], 10) + ', ' + m[1];
  }

  // Square-root scale: area reads as proportional to the value, so a $10k donor
  // doesn't visually swamp a $1k one the way a linear diameter scale would.
  function sqrtScale(value, minValue, maxValue, outMin, outMax) {
    var v = Math.max(0, toNumber(value));
    var lo = Math.max(0, toNumber(minValue));
    var hi = Math.max(0, toNumber(maxValue));
    if (hi <= lo) return (outMin + outMax) / 2; // every donor gave the same amount
    var t = (Math.sqrt(v) - Math.sqrt(lo)) / (Math.sqrt(hi) - Math.sqrt(lo));
    t = Math.min(1, Math.max(0, t));
    return outMin + t * (outMax - outMin);
  }

  // ---------------------------------------------------------------------------
  // Input normalization — everything past this point can trust its data
  // ---------------------------------------------------------------------------

  function normalizeContributions(raw) {
    if (!raw || !raw.length) return [];
    var out = [];
    for (var i = 0; i < raw.length; i++) {
      var c = raw[i];
      if (!c || typeof c !== 'object') continue;
      out.push({ date: toText(c.date), amount: toNumber(c.amount) });
    }
    // Newest first. Undated entries sink to the bottom rather than scrambling the list.
    out.sort(function (a, b) {
      if (!a.date) return 1;
      if (!b.date) return -1;
      return a.date < b.date ? 1 : (a.date > b.date ? -1 : 0);
    });
    return out;
  }

  function normalize(fundingData) {
    var data = (fundingData && typeof fundingData === 'object') ? fundingData : {};

    var rawOfficial = (data.official && typeof data.official === 'object') ? data.official : {};
    var rawReelection = (rawOfficial.reelection && typeof rawOfficial.reelection === 'object')
      ? rawOfficial.reelection
      : null;

    // When app.js passes only `funding.donors`, there is no official to label the
    // center node with. Fall back to a neutral label rather than "undefined".
    var hasOfficial = !!toText(rawOfficial.name);

    var official = {
      id: toText(rawOfficial.id) || 'official',
      name: toText(rawOfficial.name) || 'Funding',
      hasOfficial: hasOfficial,
      office: toText(rawOfficial.office),
      reelection: rawReelection ? {
        active: rawReelection.active === true,
        electionDate: toText(rawReelection.election_date),
        committee: toText(rawReelection.committee)
      } : null
    };

    var rawDonors = Array.isArray(data.donors) ? data.donors : [];
    var donors = [];

    for (var i = 0; i < rawDonors.length; i++) {
      var d = rawDonors[i];
      if (!d || typeof d !== 'object') continue;

      var contributions = normalizeContributions(
        Array.isArray(d.contributions) ? d.contributions : null
      );

      var total = toNumber(d.total);
      if (total <= 0 && contributions.length) {
        // total missing or zero but we have line items — derive it.
        for (var j = 0; j < contributions.length; j++) total += contributions[j].amount;
      }

      var rawType = toText(d.type).toLowerCase();
      var type = Object.prototype.hasOwnProperty.call(TYPE_COLORS, rawType) ? rawType : 'unknown';

      donors.push({
        // Index-based id: donor names are not guaranteed unique, element ids must be.
        id: 'donor-' + i,
        name: toText(d.name) || 'Unnamed donor',
        type: type,
        rawType: rawType,
        total: total,
        employer: toText(d.employer),
        contributions: contributions
      });
    }

    return { official: official, donors: donors };
  }

  // ---------------------------------------------------------------------------
  // Elements + style
  // ---------------------------------------------------------------------------

  function buildElements(model) {
    var donors = model.donors;
    var elements = [];
    var i;

    var minTotal = Infinity;
    var maxTotal = 0;
    for (i = 0; i < donors.length; i++) {
      if (donors[i].total < minTotal) minTotal = donors[i].total;
      if (donors[i].total > maxTotal) maxTotal = donors[i].total;
    }
    if (!isFinite(minTotal)) minTotal = 0;

    elements.push({
      group: 'nodes',
      data: {
        id: model.official.id,
        kind: 'official',
        label: model.official.name,
        size: OFFICIAL_SIZE,
        color: OFFICIAL_COLOR,
        concentric: maxTotal + (maxTotal || 1) // keeps the official alone in the center ring
      }
    });

    for (i = 0; i < donors.length; i++) {
      var donor = donors[i];
      elements.push({
        group: 'nodes',
        data: {
          id: donor.id,
          kind: 'donor',
          label: donor.name,
          size: sqrtScale(donor.total, minTotal, maxTotal, DONOR_SIZE_MIN, DONOR_SIZE_MAX),
          color: TYPE_COLORS[donor.type] || UNKNOWN_TYPE_COLOR,
          concentric: donor.total,
          donor: donor
        }
      });
      elements.push({
        group: 'edges',
        data: {
          id: 'edge-' + i,
          source: model.official.id,
          target: donor.id,
          width: sqrtScale(donor.total, minTotal, maxTotal, EDGE_WIDTH_MIN, EDGE_WIDTH_MAX),
          color: TYPE_COLORS[donor.type] || UNKNOWN_TYPE_COLOR
        }
      });
    }

    return { elements: elements, minTotal: minTotal, maxTotal: maxTotal };
  }

  function buildStyle() {
    return [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'width': 'data(size)',
          'height': 'data(size)',
          'label': 'data(label)',
          'color': '#6b7076',
          'font-size': 10.5,
          'font-weight': 400,
          'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 7,
          'text-wrap': 'ellipsis',
          'text-max-width': 110,
          // Hide labels instead of letting them turn to mush when zoomed out.
          'min-zoomed-font-size': 7,
          'text-background-color': '#ffffff',
          'text-background-opacity': 0.85,
          'text-background-padding': 2,
          'text-background-shape': 'roundrectangle',
          'border-width': 0,
          'transition-property': 'border-width, border-color',
          'transition-duration': 120
        }
      },
      {
        selector: 'node[kind = "official"]',
        style: {
          'label': 'data(label)',
          'color': '#ffffff',
          'font-size': 13,
          'font-weight': 500,
          'text-valign': 'center',
          'text-margin-y': 0,
          'text-max-width': 80,
          'text-wrap': 'wrap',
          'text-background-opacity': 0,
          'min-zoomed-font-size': 0
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 'data(width)',
          'line-color': EDGE_COLOR,
          'opacity': 1,
          'curve-style': 'straight'
        }
      },
      {
        selector: 'node.fg-hover',
        style: { 'border-width': 6, 'border-color': 'data(color)', 'border-opacity': 0.22 }
      },
      {
        selector: 'node.fg-active',
        style: { 'border-width': 6, 'border-color': 'data(color)', 'border-opacity': 0.45 }
      },
      {
        // The one place color reaches the edges: the connection you're inspecting.
        selector: 'edge.fg-active',
        style: { 'line-color': 'data(color)', 'opacity': 0.85 }
      }
    ];
  }

  function buildLayout(donorCount, maxTotal) {
    // Concentric by contribution size: biggest donors land nearest the official.
    // Ring count scales with donor count so 30 nodes don't crowd a single ring.
    var ringCount = donorCount <= 12 ? 1 : (donorCount <= 22 ? 2 : 3);
    var levelWidth = (maxTotal || 1) / ringCount;

    return {
      name: 'concentric',
      concentric: function (node) { return toNumber(node.data('concentric')); },
      levelWidth: function () { return levelWidth; },
      // Ring radius is driven by node size + this spacing. The inner ring holds the
      // biggest donors, so it needs *more* room as the donor count grows, not less.
      minNodeSpacing: donorCount > 22 ? 58 : (donorCount > 12 ? 48 : 44),
      avoidOverlap: true,
      equidistant: false,
      spacingFactor: 1,
      padding: 60, // labels hang below nodes; keeps the outer ring's text off the edge
      fit: true,
      animate: false
    };
  }

  // ---------------------------------------------------------------------------
  // Tooltip
  // ---------------------------------------------------------------------------

  var TOOLTIP_CSS = [
    'position:absolute',
    'z-index:10',
    'display:none',
    'box-sizing:border-box',
    'max-width:290px',
    'max-height:60%',
    'overflow-y:auto',
    'padding:14px 16px',
    'border:1px solid rgba(0,0,0,0.07)',
    'border-radius:8px',
    'background:#ffffff',
    'box-shadow:0 2px 14px rgba(0,0,0,0.07)',
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif',
    'font-size:12.5px',
    'line-height:1.5',
    'color:#2b2f33'
  ].join(';');

  function createTooltip(container) {
    var el = document.createElement('div');
    el.className = 'funding-graph-tooltip';
    el.setAttribute('role', 'dialog');
    el.style.cssText = TOOLTIP_CSS;
    container.appendChild(el);
    return el;
  }

  function donorTooltipHtml(donor) {
    var parts = [];

    parts.push(
      '<div style="display:flex;align-items:flex-start;gap:8px;">' +
        '<div style="flex:1;min-width:0;">' +
          '<div style="font-weight:600;font-size:14px;">' + escapeHtml(donor.name) + '</div>' +
          '<div style="margin-top:2px;font-size:11px;text-transform:uppercase;letter-spacing:0.04em;color:' +
            (TYPE_COLORS[donor.type] || UNKNOWN_TYPE_COLOR) + ';">' +
            escapeHtml(donor.rawType || 'unknown type') +
          '</div>' +
        '</div>' +
        '<button type="button" data-fg-close="1" aria-label="Close" ' +
          'style="flex:none;border:0;background:transparent;cursor:pointer;font-size:18px;' +
          'line-height:1;padding:0 2px;color:#9ca3af;">&times;</button>' +
      '</div>'
    );

    parts.push(
      '<div style="margin-top:8px;font-size:11px;color:#6b7280;">Employer</div>' +
      '<div>' + (donor.employer ? escapeHtml(donor.employer) : '&mdash;') + '</div>'
    );

    parts.push(
      '<div style="margin-top:8px;font-size:11px;color:#6b7280;">Total contributed</div>' +
      '<div style="font-weight:600;font-size:16px;">' + escapeHtml(formatMoney(donor.total)) + '</div>'
    );

    parts.push(
      '<div style="margin-top:10px;padding-top:8px;border-top:1px solid #f0f1f3;' +
      'font-size:11px;color:#6b7280;">Contributions (' + donor.contributions.length + ')</div>'
    );

    if (!donor.contributions.length) {
      parts.push('<div style="color:#9ca3af;">No itemized contributions on file.</div>');
    } else {
      var rows = [];
      for (var i = 0; i < donor.contributions.length; i++) {
        var c = donor.contributions[i];
        rows.push(
          '<div style="display:flex;justify-content:space-between;gap:12px;padding:3px 0;">' +
            '<span style="color:#4b5563;">' + escapeHtml(formatDate(c.date)) + '</span>' +
            '<span style="font-variant-numeric:tabular-nums;">' + escapeHtml(formatMoney(c.amount)) + '</span>' +
          '</div>'
        );
      }
      parts.push(rows.join(''));
    }

    return parts.join('');
  }

  function officialTooltipHtml(official) {
    var parts = [];

    parts.push(
      '<div style="display:flex;align-items:flex-start;gap:8px;">' +
        '<div style="flex:1;min-width:0;">' +
          '<div style="font-weight:600;font-size:14px;">' + escapeHtml(official.name) + '</div>' +
          (official.office
            ? '<div style="margin-top:2px;color:#6b7280;">' + escapeHtml(official.office) + '</div>'
            : '') +
        '</div>' +
        '<button type="button" data-fg-close="1" aria-label="Close" ' +
          'style="flex:none;border:0;background:transparent;cursor:pointer;font-size:18px;' +
          'line-height:1;padding:0 2px;color:#9ca3af;">&times;</button>' +
      '</div>'
    );

    var r = official.reelection;
    if (r && r.active) {
      parts.push(
        '<div style="margin-top:10px;padding-top:8px;border-top:1px solid #f0f1f3;' +
        'font-size:11px;color:#6b7280;">Re-election</div>'
      );
      if (r.electionDate) {
        parts.push('<div>' + escapeHtml(formatDate(r.electionDate)) + '</div>');
      }
      if (r.committee) {
        parts.push('<div style="color:#4b5563;">' + escapeHtml(r.committee) + '</div>');
      }
      if (!r.electionDate && !r.committee) {
        parts.push('<div style="color:#4b5563;">Active</div>');
      }
    }

    return parts.join('');
  }

  // ---------------------------------------------------------------------------
  // Main entry point
  // ---------------------------------------------------------------------------

  function looksLikeContainer(value) {
    return (typeof value === 'string') || !!(value && value.nodeType === 1);
  }

  // Two call styles exist in this project and both are supported, so no teammate
  // has to change a line to integrate:
  //   app.js (current):  renderFundingGraph(funding.donors, "funding-graph")
  //   component spec:    renderFundingGraph("funding-graph", funding)
  // The payload may be the full funding object or a bare donors array.
  function resolveArgs(a, b) {
    var aIsContainer = looksLikeContainer(a);
    var bIsContainer = looksLikeContainer(b);

    var containerRef, payload;
    if (aIsContainer && !bIsContainer) { containerRef = a; payload = b; }
    else if (bIsContainer && !aIsContainer) { containerRef = b; payload = a; }
    else if (aIsContainer) { containerRef = a; payload = b; } // ambiguous — trust arg order
    else { containerRef = b; payload = a; }

    return {
      containerRef: containerRef,
      fundingData: Array.isArray(payload) ? { donors: payload } : payload
    };
  }

  function renderFundingGraph(a, b) {
    if (typeof cytoscape !== 'function') {
      console.error('[graph.js] Cytoscape.js is not loaded. Add its <script> tag before graph.js.');
      return null;
    }

    var args = resolveArgs(a, b);
    var containerRef = args.containerRef;
    var fundingData = args.fundingData;

    var container = (typeof containerRef === 'string')
      ? document.getElementById(containerRef)
      : containerRef; // also accept an element, in case the page owner already has one

    if (!container) {
      console.error('[graph.js] No container element found for: ' + containerRef);
      return null;
    }

    // Tear down a previous render into this same container (re-clicking officials).
    destroyExisting(container);

    // The tooltip is positioned absolutely inside the container, so the container
    // must be a positioning context. Teammates own the CSS, so only set it if needed.
    if (global.getComputedStyle && getComputedStyle(container).position === 'static') {
      container.style.position = 'relative';
    }
    // A zero-height container renders an invisible graph — the single most common
    // way this silently "doesn't work". Warn loudly and keep the demo alive.
    if (container.clientHeight === 0) {
      console.warn('[graph.js] Container #' + (container.id || '(no id)') +
        ' has zero height; applying a ' + FALLBACK_MIN_HEIGHT + 'px fallback. Give it a height in CSS.');
      container.style.minHeight = FALLBACK_MIN_HEIGHT + 'px';
    }

    var model = normalize(fundingData);
    if (!model.donors.length) {
      console.warn('[graph.js] No usable donors in fundingData; rendering the official alone.');
    }

    var built = buildElements(model);

    var cy = cytoscape({
      container: container,
      elements: built.elements,
      style: buildStyle(),
      layout: buildLayout(model.donors.length, built.maxTotal),
      minZoom: 0.2,
      maxZoom: 3,
      boxSelectionEnabled: false,
      autoungrabify: false
    });

    var tooltip = createTooltip(container);
    var activeNode = null;

    function hideTooltip() {
      tooltip.style.display = 'none';
      tooltip.innerHTML = '';
      if (activeNode) {
        cy.elements('.fg-active').removeClass('fg-active');
        activeNode = null;
      }
    }

    function positionTooltip() {
      if (!activeNode || tooltip.style.display === 'none') return;

      var point = activeNode.renderedPosition(); // px, relative to the container
      var radius = (activeNode.renderedOuterWidth() || 0) / 2;
      var gap = 12;

      var tipW = tooltip.offsetWidth;
      var tipH = tooltip.offsetHeight;
      var boxW = container.clientWidth;
      var boxH = container.clientHeight;
      var margin = 8;

      // Prefer to the right of the node; flip left if it would overflow.
      var left = point.x + radius + gap;
      if (left + tipW > boxW - margin) left = point.x - radius - gap - tipW;
      left = Math.min(Math.max(left, margin), Math.max(margin, boxW - tipW - margin));

      var top = point.y - tipH / 2;
      top = Math.min(Math.max(top, margin), Math.max(margin, boxH - tipH - margin));

      tooltip.style.left = Math.round(left) + 'px';
      tooltip.style.top = Math.round(top) + 'px';
    }

    function showTooltip(node, html) {
      cy.elements('.fg-active').removeClass('fg-active');
      activeNode = node;
      node.addClass('fg-active');
      node.connectedEdges().addClass('fg-active');

      tooltip.innerHTML = html;
      tooltip.style.display = 'block';
      tooltip.scrollTop = 0;
      positionTooltip(); // measured after display:block so offsetWidth/Height are real
    }

    // --- events -------------------------------------------------------------

    cy.on('tap', 'node[kind = "donor"]', function (event) {
      var donor = event.target.data('donor');
      if (!donor) return;
      showTooltip(event.target, donorTooltipHtml(donor));
    });

    cy.on('tap', 'node[kind = "official"]', function (event) {
      // Nothing to show when app.js passed only the donors array.
      if (!model.official.hasOfficial) { hideTooltip(); return; }
      showTooltip(event.target, officialTooltipHtml(model.official));
    });

    // Tap on empty canvas closes.
    cy.on('tap', function (event) {
      if (event.target === cy) hideTooltip();
    });

    cy.on('mouseover', 'node', function (event) {
      event.target.addClass('fg-hover');
      container.style.cursor = 'pointer';
    });
    cy.on('mouseout', 'node', function (event) {
      event.target.removeClass('fg-hover');
      container.style.cursor = '';
    });

    // Keep the tooltip glued to its node through pan, zoom, and node drags.
    cy.on('pan zoom resize', positionTooltip);
    cy.on('position', 'node', function (event) {
      if (activeNode && event.target.id() === activeNode.id()) positionTooltip();
    });

    function onTooltipClick(event) {
      var el = event.target;
      while (el && el !== tooltip) {
        if (el.getAttribute && el.getAttribute('data-fg-close')) { hideTooltip(); return; }
        el = el.parentNode;
      }
    }
    tooltip.addEventListener('click', onTooltipClick);

    // Clicking anywhere outside the graph container also closes.
    function onDocumentClick(event) {
      if (!container.contains(event.target)) hideTooltip();
    }
    document.addEventListener('click', onDocumentClick, true);

    function onKeyDown(event) {
      if (event.key === 'Escape' || event.keyCode === 27) hideTooltip();
    }
    document.addEventListener('keydown', onKeyDown);

    // Containers that start hidden (tabs, accordions) or resize need a re-fit,
    // otherwise the graph renders at the wrong size or not at all.
    var resizeObserver = null;
    if (typeof ResizeObserver === 'function') {
      resizeObserver = new ResizeObserver(function () {
        cy.resize();
        positionTooltip();
      });
      resizeObserver.observe(container);
    }

    var record = {
      container: container,
      cy: cy,
      cleanup: function () {
        document.removeEventListener('click', onDocumentClick, true);
        document.removeEventListener('keydown', onKeyDown);
        tooltip.removeEventListener('click', onTooltipClick);
        if (resizeObserver) resizeObserver.disconnect();
        if (tooltip.parentNode) tooltip.parentNode.removeChild(tooltip);
        container.style.cursor = '';
      }
    };
    mounted.push(record);

    // Make cy.destroy() also run our cleanup, so the page owner only needs one call.
    var nativeDestroy = cy.destroy.bind(cy);
    cy.destroy = function () {
      removeRecord(record);
      record.cleanup();
      return nativeDestroy();
    };

    return cy;
  }

  function removeRecord(record) {
    var i = mounted.indexOf(record);
    if (i !== -1) mounted.splice(i, 1);
  }

  function destroyExisting(container) {
    for (var i = mounted.length - 1; i >= 0; i--) {
      if (mounted[i].container !== container) continue;
      // cy.destroy() is wrapped above, so it removes the record and runs cleanup too.
      try { mounted[i].cy.destroy(); } catch (e) { /* already gone */ }
    }
    container.innerHTML = '';
  }

  global.renderFundingGraph = renderFundingGraph;
})(window);
