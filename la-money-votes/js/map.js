/*!
 * map.js — Citywide official map (index.html only)
 *
 * Renders a Leaflet map of Los Angeles with:
 *   - one clickable/focusable marker per City Council district (1-15),
 *     positioned at a representative point inside that district's official
 *     adopted boundary (data/districts.json, sourced from LA GeoHub)
 *   - a visually distinct Mayor marker at Los Angeles City Hall, clearly
 *     labeled "Mayor" and never implying a district
 *   - a simplified district-boundary shading layer (data/geo/council_districts.geojson)
 *   - a hover/focus panel with name, title, district, and a concise funding
 *     summary drawn from each official's own funding.json
 *
 * Every marker is rendered as a real <a href="official.html?id=..."> element,
 * so keyboard Tab order, screen readers, and "open in new tab" all work the
 * same way they would for any other link on the page — no custom keyboard
 * handling required for activation.
 *
 * Exposes exactly one global:
 *   initCitywideMap(containerId, options?)
 * options.focusId (optional) centers/zooms the map on that official's
 * marker and gives it a highlighted ring class (citymap-marker-focused) —
 * used by official.html to show "district map context" on profile pages.
 * Depends on Leaflet (window.L) already being on the page. If Leaflet or any
 * data file fails to load, this module fails quietly (console warning) and
 * leaves the always-present #official-list grid in index.html as the
 * no-JS/JS-failure fallback — see app.js:loadOfficialsIndex().
 */
/* global L */
(function (global) {
  'use strict';

  var LA_CENTER = [34.05, -118.35];
  var LA_ZOOM = 9;

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

  async function fetchJson(url) {
    var res = await fetch(url);
    if (!res.ok) throw new Error(url + ' -> ' + res.status);
    return res.json();
  }

  // Builds { total, donorCount, topDonor: {name, total} | null } from a
  // funding.json payload. Returns null (not zeros) when donors can't be read,
  // so the tooltip can say "Funding data unavailable" instead of "$0".
  function summarizeFunding(funding) {
    if (!funding || !Array.isArray(funding.donors)) return null;
    var donors = funding.donors;
    var total = 0;
    var top = null;
    for (var i = 0; i < donors.length; i++) {
      var t = typeof donors[i].total === 'number' ? donors[i].total : parseFloat(donors[i].total) || 0;
      total += t;
      if (!top || t > top.total) top = { name: donors[i].name, total: t };
    }
    return { total: total, donorCount: donors.length, topDonor: top };
  }

  function tooltipHtml(entry) {
    var parts = [];
    parts.push('<div class="citymap-tip-name">' + escapeHtml(entry.name) + '</div>');
    parts.push('<div class="citymap-tip-title">' + escapeHtml(entry.title) + '</div>');
    if (entry.party) {
      parts.push('<div class="citymap-tip-party">Party: ' + escapeHtml(entry.party) + '</div>');
    }
    if (entry.summary) {
      parts.push(
        '<div class="citymap-tip-funding">' +
          escapeHtml(formatMoney(entry.summary.total)) +
          ' raised &middot; ' +
          entry.summary.donorCount +
          ' donor' + (entry.summary.donorCount === 1 ? '' : 's') +
          '</div>'
      );
      if (entry.summary.topDonor) {
        parts.push(
          '<div class="citymap-tip-topdonor">Top donor: ' +
            escapeHtml(entry.summary.topDonor.name) + ' (' + escapeHtml(formatMoney(entry.summary.topDonor.total)) + ')</div>'
        );
      }
    } else {
      parts.push('<div class="citymap-tip-funding muted">Funding summary unavailable</div>');
    }
    parts.push('<div class="citymap-tip-cta">View full profile &rarr;</div>');
    return parts.join('');
  }

  function buildMarkerIcon(entry) {
    var isMayor = entry.role === 'mayor';
    var label = isMayor ? '&#9733;' : String(entry.district);
    var cls = isMayor ? 'citymap-marker citymap-marker-mayor' : 'citymap-marker citymap-marker-district';
    var ariaLabel = isMayor
      ? entry.name + ', Mayor of Los Angeles'
      : entry.name + ', LA City Council District ' + entry.district + ' — view profile';
    var html =
      '<a href="official.html?id=' + encodeURIComponent(entry.officialId) + '" class="' + cls + '" ' +
      'aria-label="' + escapeHtml(ariaLabel) + '" data-official-id="' + escapeHtml(entry.officialId) + '">' +
      '<span aria-hidden="true">' + label + '</span></a>';

    return L.divIcon({
      className: 'citymap-marker-wrap',
      html: html,
      iconSize: isMayor ? [34, 34] : [26, 26],
      iconAnchor: isMayor ? [17, 17] : [13, 13]
    });
  }

  function createSharedTooltip(mapContainer) {
    var el = document.createElement('div');
    el.className = 'citymap-tooltip';
    el.setAttribute('role', 'status');
    el.hidden = true;
    mapContainer.appendChild(el);
    return el;
  }

  async function initCitywideMap(containerId, options) {
    var container = document.getElementById(containerId);
    if (!container) return;
    options = options || {};
    var focusId = options.focusId || null;

    if (typeof L === 'undefined') {
      console.warn('[map.js] Leaflet is not loaded; skipping citywide map. The official list below still works.');
      renderMapError(container);
      return;
    }

    var districts, officials;
    try {
      var results = await Promise.all([
        fetchJson('data/districts.json'),
        fetchJson('data/officials.json')
      ]);
      districts = results[0];
      officials = results[1];
    } catch (err) {
      console.warn('[map.js] Could not load map data:', err);
      renderMapError(container);
      return;
    }

    var officialsById = {};
    officials.forEach(function (o) { officialsById[o.id] = o; });

    // Funding summaries are best-effort: a missing/failed fetch for one
    // official must not block the map or any other official's tooltip.
    var allIds = districts.districts.map(function (d) { return d.official_id; }).concat([districts.mayor.official_id]);
    var summaries = {};
    await Promise.all(
      allIds.map(function (id) {
        return fetchJson('data/officials/' + id + '/funding.json')
          .then(function (funding) { summaries[id] = summarizeFunding(funding); })
          .catch(function () { summaries[id] = null; });
      })
    );

    if (container.clientHeight === 0) container.style.minHeight = '480px';

    var map = L.map(container, {
      scrollWheelZoom: false,
      attributionControl: true
    }).setView(LA_CENTER, LA_ZOOM);

    // Council district centers cluster tightly around downtown relative to
    // the full sprawl of the city (San Pedro to Sylmar), so a fixed overview
    // zoom leaves adjacent downtown markers overlapping and unclickable.
    // fitBounds recomputes the best-fit zoom for the *actual* container size
    // (desktop vs. mobile, citywide map vs. profile-page mini-map), which
    // maximizes separation between markers instead of using one guessed
    // zoom for every layout.
    var allCenters = districts.districts.map(function (d) { return d.center; }).concat([districts.mayor.center]);
    try {
      map.fitBounds(L.latLngBounds(allCenters), { padding: [28, 28], maxZoom: focusId ? LA_ZOOM + 4 : 12 });
    } catch (err) {
      console.warn('[map.js] fitBounds failed, falling back to default view:', err);
    }

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Re-enable scroll-zoom only once the map has focus/click, so the page
    // itself still scrolls normally for a visitor just skimming the page.
    map.on('focus', function () { map.scrollWheelZoom.enable(); });
    map.on('blur', function () { map.scrollWheelZoom.disable(); });

    // District boundary shading — decorative context only; every fact shown
    // to the user comes from districts.json/officials.json/funding.json, not
    // from this geometry file (see CONTRACT.md).
    try {
      var geo = await fetchJson('data/geo/council_districts.geojson');
      L.geoJSON(geo, {
        style: function () {
          return { color: '#8a94a6', weight: 1, fillColor: '#c9d3e0', fillOpacity: 0.25 };
        },
        onEachFeature: function (feature, layer) {
          layer.on('mouseover', function () { layer.setStyle({ fillOpacity: 0.45, weight: 2 }); });
          layer.on('mouseout', function () { layer.setStyle({ fillOpacity: 0.25, weight: 1 }); });
        }
      }).addTo(map);
    } catch (err) {
      console.warn('[map.js] Could not load district boundary geometry; markers still render.', err);
    }

    var tooltip = createSharedTooltip(container);
    var focusedMarker = null;

    function showTooltip(marker, entry) {
      tooltip.innerHTML = tooltipHtml(entry);
      tooltip.hidden = false;
      var point = map.latLngToContainerPoint(marker.getLatLng());
      var tipW = tooltip.offsetWidth || 240;
      var left = Math.min(Math.max(point.x - tipW / 2, 8), container.clientWidth - tipW - 8);
      var top = Math.max(point.y - (tooltip.offsetHeight || 90) - 26, 8);
      tooltip.style.left = left + 'px';
      tooltip.style.top = top + 'px';
    }

    function hideTooltip() {
      tooltip.hidden = true;
      tooltip.innerHTML = '';
    }

    function wireEntry(entry) {
      var icon = buildMarkerIcon(entry);
      // Build the marker "detached" and wire its DOM listeners in the
      // 'add' callback registered *before* addTo(map) runs. addTo() fires
      // 'add' synchronously, so registering the listener afterward (as an
      // earlier version of this file did) misses the event entirely and
      // hover/focus tooltips silently never appear.
      var marker = L.marker(entry.center, { icon: icon, keyboard: false, alt: entry.name, riseOnHover: true });
      var isFocused = focusId && entry.officialId === focusId;

      // The marker's DOM node is the <a> we built above — wire native focus
      // and hover events directly to it rather than Leaflet's own mouse-only
      // event system, so keyboard users get the same tooltip sighted mouse
      // users get.
      marker.on('add', function () {
        var el = marker.getElement();
        if (!el) return;
        var link = el.querySelector('a');
        if (!link) return;
        link.addEventListener('mouseenter', function () { showTooltip(marker, entry); });
        link.addEventListener('mouseleave', hideTooltip);
        link.addEventListener('focus', function () { showTooltip(marker, entry); });
        link.addEventListener('blur', hideTooltip);
        if (isFocused) link.classList.add('citymap-marker-focused');
      });

      marker.addTo(map);
      if (isFocused) focusedMarker = marker;
    }

    districts.districts.forEach(function (d) {
      var o = officialsById[d.official_id] || {};
      wireEntry({
        officialId: d.official_id,
        role: 'council',
        district: d.district,
        name: o.name || 'District ' + d.district,
        title: 'LA City Council District ' + d.district,
        party: o.party && o.party.affiliation,
        center: d.center,
        summary: summaries[d.official_id]
      });
    });

    var mo = officialsById[districts.mayor.official_id] || {};
    wireEntry({
      officialId: districts.mayor.official_id,
      role: 'mayor',
      name: mo.name || 'Mayor',
      title: 'Mayor of Los Angeles — elected citywide, not tied to a district',
      party: mo.party && mo.party.affiliation,
      center: districts.mayor.center,
      summary: summaries[districts.mayor.official_id]
    });

    setTimeout(function () {
      map.invalidateSize();
      if (focusedMarker) {
        map.setView(focusedMarker.getLatLng(), Math.max(LA_ZOOM + 4, 13));
      }
    }, 50);
  }

  function renderMapError(container) {
    container.innerHTML =
      '<p class="citymap-error">The interactive map could not load. ' +
      'See the full list of officials below.</p>';
  }

  global.initCitywideMap = initCitywideMap;
})(window);
