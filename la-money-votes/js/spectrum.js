/*!
 * spectrum.js — political-spectrum card
 *
 * Renders a horizontal spectrum ("Progressive" - "Liberal" - "Center" -
 * "Conservative") from a data/officials/<id>/spectrum.json record. This is
 * explicitly presented as a research assessment, not an objective fact:
 * every rendering includes the fixed methodology disclosure, a confidence
 * indicator, a last-reviewed date, and clickable evidence links. When the
 * record's status is "not_assessed" (the shipped default for every official
 * — see CONTRACT.md), the component renders "Not yet assessed" instead of
 * guessing a placement.
 *
 * Exposes two globals:
 *   renderSpectrumCard(containerId, spectrumData)   — full profile-page card
 *   renderSpectrumCompact(containerId, spectrumData) — compact summary
 */
(function (global) {
  'use strict';

  var ZONES = [
    { key: 'progressive', label: 'Progressive', from: 0, to: 25 },
    { key: 'liberal', label: 'Liberal', from: 25, to: 50 },
    { key: 'center', label: 'Center', from: 50, to: 75 },
    { key: 'conservative', label: 'Conservative', from: 75, to: 100 }
  ];

  var DIMENSION_LABELS = {
    housing: 'Housing',
    policing_public_safety: 'Policing & public safety',
    labor: 'Labor',
    climate: 'Climate',
    transportation: 'Transportation'
  };

  var CONFIDENCE_LABELS = { low: 'Low confidence', medium: 'Medium confidence', high: 'High confidence' };

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDate(value) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ''));
    if (!m) return null;
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var mi = parseInt(m[2], 10) - 1;
    if (mi < 0 || mi > 11) return value;
    return months[mi] + ' ' + parseInt(m[3], 10) + ', ' + m[1];
  }

  function zonesHtml() {
    return ZONES.map(function (z) {
      return '<span class="spectrum-zone spectrum-zone-' + z.key + '">' + escapeHtml(z.label) + '</span>';
    }).join('');
  }

  function barHtml(position, label, notAssessed) {
    var pct = typeof position === 'number' ? Math.max(0, Math.min(100, position)) : null;
    return (
      '<div class="spectrum-bar' + (notAssessed ? ' spectrum-bar-unassessed' : '') + '" role="img" ' +
      'aria-label="' + (notAssessed ? 'Not yet assessed' : escapeHtml(label) + ', position ' + Math.round(pct) + ' of 100') + '">' +
      '<div class="spectrum-track">' + zonesHtml() +
      (pct !== null ? '<div class="spectrum-marker" style="left:' + pct + '%" aria-hidden="true"></div>' : '') +
      '</div></div>'
    );
  }

  function evidenceListHtml(evidence) {
    if (!evidence || !evidence.length) {
      return '<p class="spectrum-evidence-empty muted">No cited evidence on file yet.</p>';
    }
    return (
      '<ul class="spectrum-evidence-list">' +
      evidence
        .map(function (e) {
          var dateLabel = formatDate(e.date);
          return (
            '<li><a href="' + escapeHtml(e.url) + '" target="_blank" rel="noopener noreferrer">' +
            escapeHtml(e.title) + '</a>' + (dateLabel ? ' <span class="muted">(' + escapeHtml(dateLabel) + ')</span>' : '') +
            '</li>'
          );
        })
        .join('') +
      '</ul>'
    );
  }

  function issueRowHtml(issue) {
    var label = DIMENSION_LABELS[issue.dimension] || issue.dimension;
    if (issue.status !== 'assessed' || typeof issue.position !== 'number') {
      return (
        '<div class="spectrum-issue">' +
        '<div class="spectrum-issue-head"><span class="spectrum-issue-label">' + escapeHtml(label) + '</span>' +
        '<span class="spectrum-not-assessed-tag">Not yet assessed</span></div>' +
        barHtml(null, label, true) +
        '</div>'
      );
    }
    return (
      '<div class="spectrum-issue">' +
      '<div class="spectrum-issue-head"><span class="spectrum-issue-label">' + escapeHtml(label) + '</span>' +
      (issue.label ? '<span class="spectrum-issue-value">' + escapeHtml(issue.label) + '</span>' : '') + '</div>' +
      barHtml(issue.position, issue.label, false) +
      evidenceListHtml(issue.evidence) +
      '</div>'
    );
  }

  function renderSpectrumCard(containerId, data) {
    var el = document.getElementById(containerId);
    if (!el) return;

    if (!data) {
      el.innerHTML = '<p class="spectrum-not-assessed-tag">Not yet assessed</p>';
      return;
    }

    var notAssessed = data.status !== 'assessed';
    var reviewed = formatDate(data.reviewed_at);
    var confidenceLabel = data.confidence ? (CONFIDENCE_LABELS[data.confidence] || data.confidence) : null;

    var html = [];
    html.push('<p class="spectrum-methodology">' + escapeHtml(data.methodology_note ||
      'Assessment based on documented public positions and voting record.') + '</p>');

    html.push('<div class="spectrum-overall">');
    if (notAssessed) {
      html.push('<span class="spectrum-not-assessed-tag">Not yet assessed</span>');
      html.push(barHtml(null, null, true));
    } else {
      var overall = data.overall || {};
      if (overall.label) html.push('<div class="spectrum-overall-label">' + escapeHtml(overall.label) + '</div>');
      html.push(barHtml(overall.position, overall.label, false));
    }
    html.push('</div>');

    html.push('<div class="spectrum-meta">');
    if (confidenceLabel) html.push('<span class="spectrum-confidence-badge">' + escapeHtml(confidenceLabel) + '</span>');
    html.push('<span class="spectrum-reviewed">Date last reviewed: ' + (reviewed ? escapeHtml(reviewed) : 'Not yet reviewed') + '</span>');
    html.push('</div>');

    html.push('<h4 class="spectrum-evidence-heading">Evidence</h4>');
    html.push(evidenceListHtml(data.evidence));

    if (Array.isArray(data.issues) && data.issues.length) {
      html.push('<h4 class="spectrum-issues-heading">Issue positions</h4>');
      html.push('<div class="spectrum-issues">' + data.issues.map(issueRowHtml).join('') + '</div>');
    }

    el.innerHTML = html.join('');
  }

  function renderSpectrumCompact(containerId, data) {
    var el = document.getElementById(containerId);
    if (!el) return;

    if (!data || data.status !== 'assessed' || !data.overall || typeof data.overall.position !== 'number') {
      el.innerHTML = '<span class="spectrum-not-assessed-tag spectrum-not-assessed-tag-compact">Not yet assessed</span>';
      return;
    }

    el.innerHTML =
      (data.overall.label ? '<span class="spectrum-overall-label-compact">' + escapeHtml(data.overall.label) + '</span>' : '') +
      barHtml(data.overall.position, data.overall.label, false);
  }

  global.renderSpectrumCard = renderSpectrumCard;
  global.renderSpectrumCompact = renderSpectrumCompact;
})(window);
