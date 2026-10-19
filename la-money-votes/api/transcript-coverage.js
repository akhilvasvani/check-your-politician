// api/transcript-coverage.js
//
// Read-only M3.2 endpoint for the per-official disclosure shown above the
// transcript search input. This does not call an embedding model.
//
// Contract:
//   GET /api/transcript-coverage?official_id=cd14-official
//   200 -> {
//     official_id,
//     speaking_turns,
//     meeting_count,
//     first_meeting_date,
//     last_meeting_date,
//     thin
//   }
//
// "Thin" is deliberately a disclosure rule, not a relevance/confidence cue.
// The provisional thresholds come from the current nine-meeting distribution:
// fewer than 20 parent speaking turns OR fewer than 5 distinct meetings.

const {
  sanitizeString,
  transcriptCoverageRpc,
} = require("./_lib/transcript-search-lib");

const MIN_TURNS_FOR_NON_THIN = 20;
const MIN_MEETINGS_FOR_NON_THIN = 5;
const OFFICIAL_ID_PATTERN = /^[a-z0-9-]{1,64}$/;

module.exports = async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    res.status(405).json({ error: "Method not allowed. Use GET." });
    return;
  }

  const officialId = sanitizeString(
    req.query && req.query.official_id,
    64
  ).trim();
  if (!OFFICIAL_ID_PATTERN.test(officialId)) {
    res.status(400).json({ error: "A valid official_id is required." });
    return;
  }

  try {
    const rows = await transcriptCoverageRpc({ officialId });
    const row = Array.isArray(rows) && rows.length ? rows[0] : {};
    const speakingTurns = Math.max(0, Number(row.speaking_turns) || 0);
    const meetingCount = Math.max(0, Number(row.meeting_count) || 0);

    res.setHeader(
      "Cache-Control",
      "public, max-age=300, s-maxage=300, stale-while-revalidate=600"
    );
    res.status(200).json({
      official_id: officialId,
      speaking_turns: speakingTurns,
      meeting_count: meetingCount,
      first_meeting_date: row.first_meeting_date || null,
      last_meeting_date: row.last_meeting_date || null,
      thin:
        speakingTurns < MIN_TURNS_FOR_NON_THIN ||
        meetingCount < MIN_MEETINGS_FOR_NON_THIN,
    });
  } catch (err) {
    console.error("[transcript-coverage] coverage lookup failed:", err);
    res.status(502).json({
      error: "Transcript coverage is temporarily unavailable.",
    });
  }
};

module.exports.MIN_TURNS_FOR_NON_THIN = MIN_TURNS_FOR_NON_THIN;
module.exports.MIN_MEETINGS_FOR_NON_THIN = MIN_MEETINGS_FOR_NON_THIN;
