const { canonicalOfficial, withRequest } = require("./_lib/request-safety");
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
  transcriptCoverageRpc,
} = require("./_lib/transcript-search-lib");

const MIN_TURNS_FOR_NON_THIN = 20;
const MIN_MEETINGS_FOR_NON_THIN = 5;

module.exports = withRequest("transcript-coverage", async function handler(req, res) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET");
    res.status(405).json({ error: "Method not allowed. Use GET." });
    return;
  }

  const officialId = req.query && req.query.official_id;
  if (!canonicalOfficial(officialId, true)) {
    res.status(400).json({ error: "A valid official_id is required." });
    return;
  }

  try {
    const rows = await transcriptCoverageRpc({ officialId });
    if (!Array.isArray(rows) || rows.length !== 1) throw new Error("Missing coverage aggregate");
    const row = rows[0];
    const values = [row.speaking_turns, row.meeting_count];
    if (!values.every((value) => typeof value === "number" || (typeof value === "string" && /^(0|[1-9][0-9]*)$/.test(value)))) {
      throw new Error("Invalid coverage aggregate");
    }
    const speakingTurns = Number(row.speaking_turns);
    const meetingCount = Number(row.meeting_count);
    if (row.speaking_turns == null || row.meeting_count == null || !Number.isSafeInteger(speakingTurns) || !Number.isSafeInteger(meetingCount) || speakingTurns < 0 || meetingCount < 0) throw new Error("Invalid coverage aggregate");

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
    console.warn("[transcript-coverage] coverage lookup failed");
    res.status(502).json({
      error: "Transcript coverage is temporarily unavailable.",
    });
  }
});

module.exports.MIN_TURNS_FOR_NON_THIN = MIN_TURNS_FOR_NON_THIN;
module.exports.MIN_MEETINGS_FOR_NON_THIN = MIN_MEETINGS_FOR_NON_THIN;
