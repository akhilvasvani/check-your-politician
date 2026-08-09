/*!
 * treemap.js — donor tile ("heat-grid") visualization
 *
 * A treemap-style donor visualization: every donor is a tile, tile AREA
 * scales proportionally to that donor's total contributions, and color
 * encodes donor type (individual / PAC / business), matching the same
 * TYPE_COLORS convention used by css/style.css.
 * This is not a geographic heat map — see the on-page caption this module
 * renders, which states that explicitly.
 *
 * Layout: a small, dependency-free implementation of the "squarified
 * treemap" algorithm (Bruls, Huizing, van Wijk, 2000) — no charting library
 * required, consistent with this project's "no framework, no build step"
 * approach (see README).
 *
 * Exposes exactly one global: renderDonorTreemap(containerId, fundingData).
 * Falls back to a visible message (and leaves the existing sortable donor
 * table as the text/table equivalent) if there is no usable donor data.
 */
(function (global) {
  'use strict';

  var TYPE_COLORS = {
    individual: '#4a6fa5',
    pac: '#c67b4a',
    business: '#5d8a6f'
  };
  var UNKNOWN_TYPE_COLOR = '#9aa0a6';
  var TYPE_LABELS = { individual: 'Individual', pac: 'PAC', business: 'Business' };

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatMoney(amount) {
    var n = typeof amount === 'number' ? amount : parseFloat(amount) || 0;
    try {
      return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
    } catch (e) {
      return '$' + Math.round(n);
    }
  }

  function formatDate(value) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
    if (!m) return value || '';
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var mi = parseInt(m[2], 10) - 1;
    if (mi < 0 || mi > 11) return value;
    return months[mi] + ' ' + parseInt(m[3], 10) + ', ' + m[1];
  }

  // ---------------------------------------------------------------------
  // Squarified treemap layout
  // ---------------------------------------------------------------------

  function worstRatio(row, length) {
    var sum = 0, max = 0, min = Infinity;
    for (var i = 0; i < row.length; i++) {
      sum += row[i];
      if (row[i] > max) max = row[i];
      if (row[i] < min) min = row[i];
    }
    var sq = length * length;
    return Math.max((sq * max) / (sum * sum), (sum * sum) / (sq * min));
  }

  // Lays `values` (already sorted descending, all > 0, summing to
  // width*height) into a list of {x,y,w,h} in the same order as `values`.
  //
  // Classical squarified-treemap layout (Bruls, Huizing, van Wijk 2000): each
  // "row" is placed flush against the SHORTER side of the remaining free
  // rectangle (that shared side is the "w" fed into worstRatio), and the row
  // extends into the longer dimension. Concretely:
  //   - free rect is TALLER than wide (rw < rh): the row is a horizontal
  //     strip spanning the full width rw; its height is rowSum/rw, and items
  //     within it sit side by side.
  //   - free rect is WIDER than tall (rw >= rh): the row is a vertical
  //     column spanning the full height rh; its width is rowSum/rh, and
  //     items within it stack top to bottom.
  // Getting this backwards (using the long side as the fixed dimension)
  // silently produces degenerate, ever-thinner strips for the later items —
  // that was the original bug here, caught via a standalone algorithm test
  // with 30 equal-value donors before shipping.
  function squarify(values, x, y, w, h) {
    var result = [];

    function layoutRow(row, rx, ry, rw, rh) {
      var rowSum = row.reduce(function (a, b) { return a + b; }, 0);
      var out = [];
      var offset = 0;
      var layoutHorizontal = rw < rh;
      for (var i = 0; i < row.length; i++) {
        if (layoutHorizontal) {
          var itemH = rowSum > 0 ? (row[i] / rw) : 0;
          out.push({ x: rx, y: ry + offset, w: rw, h: itemH });
          offset += itemH;
        } else {
          var itemW = rowSum > 0 ? (row[i] / rh) : 0;
          out.push({ x: rx + offset, y: ry, w: itemW, h: rh });
          offset += itemW;
        }
      }
      return out;
    }

    function recurse(vals, rx, ry, rw, rh) {
      if (!vals.length || rw <= 0 || rh <= 0) return;
      if (vals.length === 1) {
        result.push.apply(result, layoutRow([vals[0]], rx, ry, rw, rh));
        return;
      }

      var length = Math.min(rw, rh);
      var row = [vals[0]];
      var i = 1;
      while (i < vals.length) {
        var testRow = row.concat([vals[i]]);
        if (worstRatio(testRow, length) <= worstRatio(row, length)) {
          row = testRow;
          i++;
        } else {
          break;
        }
      }

      var rowSum = row.reduce(function (a, b) { return a + b; }, 0);
      var placed;
      var restRx, restRy, restRw, restRh;

      if (rw < rh) {
        // Horizontal strip along the top, full width rw.
        var rowH = rw > 0 ? rowSum / rw : 0;
        placed = layoutRow(row, rx, ry, rw, rowH);
        restRx = rx; restRy = ry + rowH; restRw = rw; restRh = rh - rowH;
      } else {
        // Vertical column along the left, full height rh.
        var rowW = rh > 0 ? rowSum / rh : 0;
        placed = layoutRow(row, rx, ry, rowW, rh);
        restRx = rx + rowW; restRy = ry; restRw = rw - rowW; restRh = rh;
      }

      result.push.apply(result, placed);
      recurse(vals.slice(row.length), restRx, restRy, restRw, restRh);
    }

    recurse(values, x, y, w, h);
    return result;
  }

  // ---------------------------------------------------------------------
  // Data prep
  // ---------------------------------------------------------------------

  function donorTotal(d) {
    return typeof d.total === 'number' ? d.total : parseFloat(d.total) || 0;
  }

  function reportingPeriodLabel(donors) {
    var min = null, max = null;
    donors.forEach(function (d) {
      (d.contributions || []).forEach(function (c) {
        var day = /^(\d{4}-\d{2}-\d{2})/.exec(String(c.date || ''));
        if (!day) return;
        if (!min || day[1] < min) min = day[1];
        if (!max || day[1] > max) max = day[1];
      });
    });
    if (!min || !max) return null;
    return formatDate(min) + ' \u2013 ' + formatDate(max);
  }

  // ---------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------

  function tileDetailHtml(donor, total, share) {
    var typeLabel = TYPE_LABELS[donor.type] || donor.type || 'Unknown category';
    var latestSourced = (donor.contributions || []).find(function (c) { return c.source_url; });
    var parts = [];
    parts.push('<div class="treemap-detail-name">' + escapeHtml(donor.name) + '</div>');
    parts.push(
      '<div class="treemap-detail-row"><span class="type-badge type-' + escapeHtml(donor.type || 'unknown') + '">' +
        escapeHtml(typeLabel) + '</span></div>'
    );
    parts.push(
      '<div class="treemap-detail-row"><strong>' + escapeHtml(formatMoney(total)) + '</strong> total &middot; ' +
        share.toFixed(1) + '% of shown donors</div>'
    );
    if (donor.employer) {
      parts.push('<div class="treemap-detail-row muted">Employer: ' + escapeHtml(donor.employer) + '</div>');
    }
    parts.push(
      '<div class="treemap-detail-row muted">' + (donor.contributions || []).length + ' itemized contribution' +
        ((donor.contributions || []).length === 1 ? '' : 's') + '</div>'
    );
    if (latestSourced) {
      parts.push(
        '<div class="treemap-detail-row"><a href="' + escapeHtml(latestSourced.source_url) +
          '" target="_blank" rel="noopener noreferrer">View a filing record</a></div>'
      );
    } else {
      parts.push('<div class="treemap-detail-row muted">No verified filing link on file for this donor.</div>');
    }
    return parts.join('');
  }

  function render(container, detailPanel, donors) {
    var width = container.clientWidth || 640;
    var height = Math.max(320, Math.min(560, width * 0.55));
    container.style.height = height + 'px';

    var sorted = donors
      .map(function (d, i) { return { donor: d, total: Math.max(donorTotal(d), 0.01), index: i }; })
      .sort(function (a, b) { return b.total - a.total; });

    var sumTotal = sorted.reduce(function (s, d) { return s + d.total; }, 0);
    var area = width * height;
    var values = sorted.map(function (d) { return (d.total / sumTotal) * area; });

    var rects = squarify(values, 0, 0, width, height);

    container.innerHTML = '';
    rects.forEach(function (r, i) {
      var entry = sorted[i];
      var donor = entry.donor;
      var color = TYPE_COLORS[donor.type] || UNKNOWN_TYPE_COLOR;
      var share = (entry.total / sumTotal) * 100;

      var tile = document.createElement('button');
      tile.type = 'button';
      tile.className = 'treemap-tile';
      var big = r.w > 46 && r.h > 26;
      tile.style.left = r.x + 'px';
      tile.style.top = r.y + 'px';
      tile.style.width = Math.max(r.w - 2, 1) + 'px';
      tile.style.height = Math.max(r.h - 2, 1) + 'px';
      tile.style.background = color;
      tile.setAttribute(
        'aria-label',
        donor.name + ', ' + (TYPE_LABELS[donor.type] || 'unknown type') + ', ' +
          formatMoney(entry.total) + ', ' + share.toFixed(1) + ' percent of shown donors'
      );
      if (big) {
        tile.innerHTML =
          '<span class="treemap-tile-name">' + escapeHtml(donor.name) + '</span>' +
          '<span class="treemap-tile-amount">' + escapeHtml(formatMoney(entry.total)) + '</span>';
      }

      function activate() {
        detailPanel.innerHTML = tileDetailHtml(donor, entry.total, share);
        detailPanel.hidden = false;
        container.querySelectorAll('.treemap-tile.active').forEach(function (t) { t.classList.remove('active'); });
        tile.classList.add('active');
      }

      tile.addEventListener('mouseenter', activate);
      tile.addEventListener('focus', activate);
      tile.addEventListener('click', activate);

      container.appendChild(tile);
    });
  }

  function renderDonorTreemap(containerId, fundingData) {
    var container = document.getElementById(containerId);
    if (!container) return;

    var panel = document.getElementById(containerId + '-detail');
    var captionEl = document.getElementById(containerId + '-caption');
    var emptyEl = document.getElementById(containerId + '-empty');

    var donors = (fundingData && Array.isArray(fundingData.donors)) ? fundingData.donors.filter(function (d) {
      return donorTotal(d) > 0;
    }) : [];

    if (!donors.length) {
      container.hidden = true;
      if (panel) panel.hidden = true;
      if (emptyEl) {
        emptyEl.hidden = false;
        emptyEl.textContent = 'No donor data available for the current filing snapshot.';
      }
      if (captionEl) captionEl.textContent = '';
      return;
    }

    container.hidden = false;
    if (emptyEl) emptyEl.hidden = true;

    if (captionEl) {
      var period = reportingPeriodLabel(donors);
      captionEl.textContent = period
        ? 'Each tile is one itemized donor record from the current filing snapshot, sized by total contributions. Data available for ' + period + '. Tile area is not a geographic heat map.'
        : 'Each tile is one itemized donor record from the current filing snapshot, sized by total contributions. Tile area is not a geographic heat map.';
    }

    render(container, panel, donors);

    var resizeTimer = null;
    if (typeof ResizeObserver === 'function' && !container.dataset.treemapObserved) {
      container.dataset.treemapObserved = '1';
      new ResizeObserver(function () {
        if (resizeTimer) clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () { render(container, panel, donors); }, 150);
      }).observe(container);
    }
  }

  global.renderDonorTreemap = renderDonorTreemap;
})(window);
