# Practice annotation import and diagnostics

Recorded November 7, 2026 Pacific. Practice only; **0 items count toward final acceptance**.

## Freeze and provenance

The supplied original annotation text is retained byte-for-byte in [original-submission.txt](original-submission.txt), including opening entries and later corrections. The revision directives are separately preserved in [revision-instructions.txt](revision-instructions.txt). No distinct earlier attachment is invented.

The normalized revision was frozen before opening the prediction key: SHA-256 `c2074fd24cdb68ef8e18dabd51cebced51361b2f9672a8d1630d69f09595bf46`. [freeze-receipt.json](freeze-receipt.json) is the pre-comparison receipt; [comparison-access-receipt.json](comparison-access-receipt.json) records the subsequent first key read. Neither the original submission nor frozen labels was rewritten after comparison.

All 12 video IDs and target intervals come from the original worksheet and match the pre-existing key/canonical artifact references. No video ID was inferred from a timestamp-only link. No video was replayed or caption probe run in this processing. Audiovisual statements below remain the user’s evidence claims, not independent verification by this agent.

## Applied revision rules

Items 01–07 and 09 retain the submitted names, roles and evidence. Only “Unresolved: None” in 02/03 becomes “No”. No source-supported spelling correction has been established; Luigi Verano, Rose Kato and Naji Ali remain exactly as submitted.

Item 08 keeps Rose Kato, with transcript-based continuity explicitly distinguished from visual evidence. Item 10 uses Unknown / Presiding chair or Council President / unresolved personal identity; warning 01:06:54–01:07:07 and handoff 01:07:08 are retained. Item 11 uses the requested presiding-chair wording and preserves the quoted speech, without treating that quotation as identity proof. Item 12 withdraws Rodriguez and retains chair/clerk procedural speech with personal identities and boundaries unresolved. The target intervals remain unchanged even where evidence times differ.

## Denominators and limits

- 12 total practice items; 10 submitted resolved named identities (01–09,11); 2 unresolved identity items (10,12).
- Of those 10 named submissions, 7 (02,04–09) support a limited label comparison with the evidence qualifiers below. Three (01,03,11) are held for source/target alignment or whole-interval boundary clarification. These diagnostic holds do not change the user’s labels.
- The resolver supplied 3 explicit personal names: Item 02 agrees; Items 01/03 disagree with the submitted names and remain unadjudicated. The other 9 outputs are generic roles, not personal-name predictions.
- Within the 7-item limited-comparison subset, only Item 02 has a personal-name model output; the other 6 are role-level outputs. No overall or twelve-item identity accuracy is calculated. Unknowns are not counted as correct or incorrect identities, and generic chair/clerk/speaker roles are not treated as incorrect personal-name guesses.
- Items 11/12 have mixed-speaker/boundary concerns (overlapping the groups above, not an extra denominator). Item 10 also has an evidence interval after its target. No councilmember-attribution precision or final acceptance result is inferred.

## Item-level comparison

| Item | Original video / target | Frozen user annotation | Previously hidden prediction | Diagnostic result |
| --- | --- | --- | --- | --- |
| 01 | `H-OkhDWvgYE` 00:44:08–00:44:12 | Eunisses Hernandez; No | Imelda Padilla (councilmember) | Submitted name differs from prediction. Evidence at 00:44:45 is outside target 00:44:08–00:44:12. Do not score the disagreement as adjudicated or overwrite the label. |
| 02 | `MBjio010l60` 00:46:06–00:46:29 | John Lee; No | John Lee (councilmember) | John Lee matches the personal-name prediction; submitted evidence covers the target. This is label agreement, not independently replayed audiovisual verification. |
| 03 | `QePVCuF0iAY` 00:46:44–00:46:49 | Luigi Verano; No | Traci Park (councilmember) | Submitted clerk identity differs from Traci Park prediction. Evidence describes a 14-ayes result; the worksheet quote concerns an amendment on item 14. Resolve the speech/source alignment before scoring. |
| 04 | `H-OkhDWvgYE` 00:42:37–00:42:56 | Marqueece Harris-Dawson; No | Council President (presiding) | Model predicts the presiding role, not Marqueece Harris-Dawson personally. User reports a chyron at 00:42:42–00:42:56; the target starts five seconds earlier. Broad role agrees; exact identity is not a model output. |
| 05 | `MBjio010l60` 00:41:52–00:42:40 | Bob Blumenfield; No | Council President (presiding) | Model predicts a generic presiding role, not Bob Blumenfield. User reports President Pro Tempore; compatible broad function, distinct submitted title. |
| 06 | `H-OkhDWvgYE` 00:43:23–00:44:02 | Luigi Verano; No | Clerk (clerk) | Model predicts Clerk; submitted Luigi Verano spelling preserved. Role agrees; no personal-name model prediction. |
| 07 | `MBjio010l60` 00:49:28–00:49:45 | Luigi Verano; No | Clerk (clerk) | Model predicts Clerk; submitted Luigi Verano spelling preserved. Role agrees; no personal-name model prediction. |
| 08 | `H-OkhDWvgYE` 01:19:56–01:20:01 | Rose Kato; No | Speaker (public-speaker) | Rose Kato remains submitted identity. The 01:19:51–01:19:58 claim partly overlaps the target; continuity to 01:22:32 is transcript-based, unverified and not visual. Generic Speaker is a broad non-official role only. |
| 09 | `MBjio010l60` 00:58:19–00:59:00 | Naji Ali; No | Speaker (public-speaker) | Naji Ali spelling preserved. Model predicts generic Speaker. Presentation/honoree speech is not by itself proof of a formal public-comment turn; broad non-official role is compatible. |
| 10 | `QePVCuF0iAY` 01:06:01–01:06:45 | Unknown; Yes — personal identity not established | Speaker (public-speaker) | Unknown is not an identity match or mismatch. Submitted chair role differs from model public-speaker, but 01:06:54–01:07:08 evidence follows the original 01:06:01–01:06:45 target. Preserve warning/handoff times; role disagreement needs target-aligned review. |
| 11 | `hyhgFSAqBRM` 02:09:59–02:10:05 | Marqueece Harris-Dawson; No | Council President (presiding) | Keep submitted Marqueece Harris-Dawson identity for the chair. Generic presiding prediction fits vote-management speech; target also includes "12 AYES", a possible additional procedural voice. Neither quotation nor model establishes personal identity or exact boundaries for the whole interval. |
| 12 | `oPUdYYi9HyE` 03:10:09–03:10:21 | Unresolved chair/clerk identities; Yes — exact personal identities and speaker boundaries unresolved | Council President (presiding) | Rodriguez attribution withdrawn. Chair/clerk procedural interpretation retained. Generic presiding prediction can describe a chair component, not establish all speakers. The worksheet places "13 AYES, 1 NO" after target; clerk timing within target remains unresolved. |

## Follow-up needed before treating conflicts as verified errors

For 01, review H-OkhDWvgYE at 00:44:08–00:44:12, not the cited 00:44:45. For 03, review QePVCuF0iAY at 00:46:44–00:46:49 and distinguish the amendment utterance from the reported vote result. For 10, establish the role/speaker at 01:06:01–01:06:45 separately from the later warning/handoff. For 11, establish speaker boundaries across 02:09:59–02:10:05, especially the “12 AYES” tail. For 12, preserve unresolved boundaries rather than importing the clerk’s following vote result into the target. These are diagnostic review needs, not automatic requests to run new video/caption tooling.

No resolver or corpus labels were changed. Future held-out acceptance must use an independently labeled, frozen ≥100-turn sample from the verified release corpus, excluding this now-unblinded practice set.
