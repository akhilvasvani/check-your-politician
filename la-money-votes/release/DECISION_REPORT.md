# Consolidated decision report — NO-GO

Prepared November 7, 2026 Pacific. Final proposed source: `<FINAL_REVIEW_HEAD>`
on `release/weekend-2026-11-08`; intended draft PR base main at
`25a51ebe617f5d24c4a7c405a6498c2104f1a2fd`. The export binds the new commit;
the old head eb06c4e is not the approval target after these annotation/report
changes. No shared SQL or remote action is approved or performed.

| Decision | Current state |
| --- | --- |
| Practice review | 12 revised items frozen before comparison; originals retained; target/identity/boundary caveats below; 0 held-out credit |
| Change A | Exact unchanged SQL below, separately awaiting approval on pwbothxnfjnxkhrcxyvd; recommend first |
| Change B | Exact unchanged SQL below, separate approval after A postflight; installation only, never invocation/ingestion authorization |
| Remote publication | BLOCKED until actual Vercel production/build/branch settings are visible; normal refspec below remains a proposal |
| Release | NO-GO; source, held-out review, relevance and operational gates remain open |

**No passing suite was repeated.** The 45/45 PG 16.14 and 45/45 PG 17.6 results are
reused after verifying every recorded SQL/test input hash is unchanged. These
are disposable DB cases, not a full application rerun or live write probe.
Fresh live reads show unchanged 5,003 chunks / 3,341 parents / 9 recordings and unchanged
privilege inventory. No caption/cookie probe, ASR, paid call, corpus write,
push/PR, workflow dispatch, settings change, merge or deployment occurred.

## 1. Practice-review import and diagnostics


Recorded November 7, 2026 Pacific. Practice only; **0 items count toward final acceptance**.

### Freeze and provenance

The supplied original annotation text is retained byte-for-byte in [original-submission.txt](practice-review/original-submission.txt), including opening entries and later corrections. The revision directives are separately preserved in [revision-instructions.txt](practice-review/revision-instructions.txt). No distinct earlier attachment is invented.

The normalized revision was frozen before opening the prediction key: SHA-256 `c2074fd24cdb68ef8e18dabd51cebced51361b2f9672a8d1630d69f09595bf46`. [freeze-receipt.json](practice-review/freeze-receipt.json) is the pre-comparison receipt; [comparison-access-receipt.json](practice-review/comparison-access-receipt.json) records the subsequent first key read. Neither the original submission nor frozen labels was rewritten after comparison.

All 12 video IDs and target intervals come from the original worksheet and match the pre-existing key/canonical artifact references. No video ID was inferred from a timestamp-only link. No video was replayed or caption probe run in this processing. Audiovisual statements below remain the user’s evidence claims, not independent verification by this agent.

### Applied revision rules

Items 01–07 and 09 retain the submitted names, roles and evidence. Only “Unresolved: None” in 02/03 becomes “No”. No source-supported spelling correction has been established; Luigi Verano, Rose Kato and Naji Ali remain exactly as submitted.

Item 08 keeps Rose Kato, with transcript-based continuity explicitly distinguished from visual evidence. Item 10 uses Unknown / Presiding chair or Council President / unresolved personal identity; warning 01:06:54–01:07:07 and handoff 01:07:08 are retained. Item 11 uses the requested presiding-chair wording and preserves the quoted speech, without treating that quotation as identity proof. Item 12 withdraws Rodriguez and retains chair/clerk procedural speech with personal identities and boundaries unresolved. The target intervals remain unchanged even where evidence times differ.

### Denominators and limits

- 12 total practice items; 10 submitted resolved named identities (01–09,11); 2 unresolved identity items (10,12).
- Of those 10 named submissions, 7 (02,04–09) support a limited label comparison with the evidence qualifiers below. Three (01,03,11) are held for source/target alignment or whole-interval boundary clarification. These diagnostic holds do not change the user’s labels.
- The resolver supplied 3 explicit personal names: Item 02 agrees; Items 01/03 disagree with the submitted names and remain unadjudicated. The other 9 outputs are generic roles, not personal-name predictions.
- Within the 7-item limited-comparison subset, only Item 02 has a personal-name model output; the other 6 are role-level outputs. No overall or twelve-item identity accuracy is calculated. Unknowns are not counted as correct or incorrect identities, and generic chair/clerk/speaker roles are not treated as incorrect personal-name guesses.
- Items 11/12 have mixed-speaker/boundary concerns (overlapping the groups above, not an extra denominator). Item 10 also has an evidence interval after its target. No councilmember-attribution precision or final acceptance result is inferred.

### Item-level comparison

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

### Follow-up needed before treating conflicts as verified errors

For 01, review H-OkhDWvgYE at 00:44:08–00:44:12, not the cited 00:44:45. For 03, review QePVCuF0iAY at 00:46:44–00:46:49 and distinguish the amendment utterance from the reported vote result. For 10, establish the role/speaker at 01:06:01–01:06:45 separately from the later warning/handoff. For 11, establish speaker boundaries across 02:09:59–02:10:05, especially the “12 AYES” tail. For 12, preserve unresolved boundaries rather than importing the clerk’s following vote result into the target. These are diagnostic review needs, not automatic requests to run new video/caption tooling.

No resolver or corpus labels were changed. Future held-out acceptance must use an independently labeled, frozen ≥100-turn sample from the verified release corpus, excluding this now-unblinded practice set.

## 2. Change A — separate exact approval packet

**NOT APPROVED. Target Supabase `pwbothxnfjnxkhrcxyvd`, la-politician,
us-west-2, database/executor postgres. This approval object covers A only.**
Neither B nor recovery, ingestion, invocation or remote publication is included.

This is the unchanged prepared A from eb06c4e. The November 7 read-only refresh
exactly matches the prior inventory; 5,003 chunks / 3,341 parents / nine recordings.
[Prior state](database-review/prior-state.json), [fresh evidence](database-review/review-refresh-2026-11-07.json),
[scope and hash](database-review/A-approval.json).

| Object / principal | Effective before | Expected after A |
| --- | --- | --- |
| public.transcript_chunks / anon, authenticated | SELECT INSERT UPDATE DELETE TRUNCATE REFERENCES TRIGGER MAINTAIN | SELECT only |
| public.transcript_chunks_id_seq / anon, authenticated | SELECT USAGE UPDATE | None |
| Both objects / PUBLIC | None | None |
| Both objects / postgres, service_role | Full existing privileges, postgres owns both | Unchanged |

No parent role memberships for anon/authenticated/service_role and no column
ACLs add access. Browser roles lack superuser/BYPASSRLS. PUBLIC and membership
paths are checked, not just direct grants. Existing inherited administrative
capabilities are preserved: postgres inherits service_role; authenticator and
supabase_realtime_admin can SET ROLE service_role but do not inherit it. Those
platform roles are not browser roles, and no membership changes are proposed.

SELECT-only RLS and EXECUTE on search_transcripts, search_public_comment and
get_transcript_coverage remain unchanged. Their STABLE/INVOKER bodies match the
reviewed hashes. Read RPCs require table SELECT, not ID-sequence privileges.
Service ingestion privileges are retained; no ingestion is authorized.

Defaults for postgres/supabase_admin can grant broad browser access to newly
created public objects. They do not regrant an existing object automatically,
but recreation can reintroduce exposure. No default or schema-wide change is
proposed; future creation must harden the exact objects in its transaction.

A explicitly holds SHARE on the transcript table while checking invariance:
ordinary SELECT is compatible; writers and stronger maintenance/DDL locks can
wait. Lock timeout 2s, individual statement timeout 15s; these do not guarantee a
total operation duration. No table rewrite. Stop/rollback on owner, role,
policy/RLS, column-ACL, exact prior ACL, corpus-count or read-function drift.
The two target counts checks occur under the lock. See full dependencies and
lock test limits in [README.md](database-review/README.md).

After commit, run the unchanged [postflight.sql](database-review/postflight.sql) and the two
independent [read-role-postflight.sql](database-review/read-role-postflight.sql) transactions.
They are READ ONLY with 10s statement bounds, invoke no application functions,
verify both browser SELECTs and expected counts 5003/3341/9, and inspect effective
privileges/read-function metadata. Read-only refresh before execution is required.
No live TRUNCATE/write-denial probe, even under rollback.

Existing tests are reused: 45/45 PG 16.14 and 45/45 PG 17.6/vector0.8.2; all recorded
SQL/test input hashes still match. Relevant cases execute reads before/after A,
deny browser DML/TRUNCATE/sequence calls, reject PUBLIC/membership/count drift,
preserve unrelated objects/defaults, restore exact old ACL, and verify concurrent
reads/write blocking and read-only postflight. These ran only on disposable DBs.
No suite was rerun for this documentation/annotation change.

### Full forward SQL

SHA-256: `245a2122c42d14e315895ef9b0de6d079030f42beb6ece04017d42ee811cb415`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.transcript_chunks IN SHARE MODE;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;

DO $acl$
DECLARE obj regclass; role_name text; expected text[]; actual text[];
BEGIN
  FOREACH obj IN ARRAY ARRAY['public.transcript_chunks'::regclass,'public.transcript_chunks_id_seq'::regclass] LOOP
    IF (SELECT relowner FROM pg_class WHERE oid=obj) <> 'postgres'::regrole THEN RAISE EXCEPTION 'Object owner drift'; END IF;
    IF EXISTS (SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid=obj
       AND (a.grantee NOT IN ('postgres'::regrole,'anon'::regrole,'authenticated'::regrole,'service_role'::regrole)
            OR a.grantor <> 'postgres'::regrole OR a.is_grantable)) THEN
      RAISE EXCEPTION 'Unexpected PUBLIC/other ACL or grantor drift';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['postgres','anon','authenticated','service_role'] LOOP
      IF obj='public.transcript_chunks'::regclass THEN
        expected := CASE WHEN current_setting('server_version_num')::int >= 170000
          THEN ARRAY['DELETE','INSERT','MAINTAIN','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE']
          ELSE ARRAY['DELETE','INSERT','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE'] END;
      ELSE expected := ARRAY['SELECT','UPDATE','USAGE']; END IF;
      SELECT array_agg(a.privilege_type ORDER BY a.privilege_type) INTO actual
        FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid=obj AND a.grantee=role_name::regrole;
      IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Prior ACL drift for % on %',role_name,obj; END IF;
    END LOOP;
  END LOOP;
END $acl$;

REVOKE ALL PRIVILEGES ON TABLE public.transcript_chunks FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.transcript_chunks TO anon, authenticated;
REVOKE ALL PRIVILEGES ON SEQUENCE public.transcript_chunks_id_seq FROM PUBLIC, anon, authenticated;

DO $deny$
DECLARE role_name text; privilege text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF NOT has_table_privilege(role_name,'public.transcript_chunks','SELECT') THEN RAISE EXCEPTION 'Required SELECT missing'; END IF;
    FOREACH privilege IN ARRAY ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
      IF has_table_privilege(role_name,'public.transcript_chunks',privilege) THEN RAISE EXCEPTION 'Unexpected browser % privilege',privilege; END IF;
    END LOOP;
    IF current_setting('server_version_num')::int >= 170000 THEN
      IF has_table_privilege(role_name,'public.transcript_chunks','MAINTAIN') THEN RAISE EXCEPTION 'Unexpected browser MAINTAIN privilege'; END IF;
    END IF;
    IF has_sequence_privilege(role_name,'public.transcript_chunks_id_seq','USAGE,SELECT,UPDATE') THEN RAISE EXCEPTION 'Browser sequence privilege remains'; END IF;
    IF NOT has_function_privilege(role_name,'public.get_transcript_coverage(text,text)','EXECUTE') THEN RAISE EXCEPTION 'Required read RPC access missing'; END IF;
  END LOOP;
END $deny$;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;
COMMIT;
```

### Full recovery SQL — separate approval

**Warning: this restores unsafe broad browser grants, including TRUNCATE and sequence mutation. Recovery is not automatic and reopens the identified exposure.**

SHA-256: `a401c88891057102cad47aad6152a45c0d9562a47784abfa872ddd8e3e228227`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
-- Restores the reviewed prior broad browser ACL; increases privilege. Approval required.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.transcript_chunks IN SHARE MODE;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;

DO $deny$
DECLARE role_name text; privilege text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF NOT has_table_privilege(role_name,'public.transcript_chunks','SELECT') THEN RAISE EXCEPTION 'Required SELECT missing'; END IF;
    FOREACH privilege IN ARRAY ARRAY['INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'] LOOP
      IF has_table_privilege(role_name,'public.transcript_chunks',privilege) THEN RAISE EXCEPTION 'Unexpected browser % privilege',privilege; END IF;
    END LOOP;
    IF current_setting('server_version_num')::int >= 170000 THEN
      IF has_table_privilege(role_name,'public.transcript_chunks','MAINTAIN') THEN RAISE EXCEPTION 'Unexpected browser MAINTAIN privilege'; END IF;
    END IF;
    IF has_sequence_privilege(role_name,'public.transcript_chunks_id_seq','USAGE,SELECT,UPDATE') THEN RAISE EXCEPTION 'Browser sequence privilege remains'; END IF;
    IF NOT has_function_privilege(role_name,'public.get_transcript_coverage(text,text)','EXECUTE') THEN RAISE EXCEPTION 'Required read RPC access missing'; END IF;
  END LOOP;
END $deny$;

GRANT ALL PRIVILEGES ON TABLE public.transcript_chunks TO anon, authenticated;
GRANT ALL PRIVILEGES ON SEQUENCE public.transcript_chunks_id_seq TO anon, authenticated;

DO $acl$
DECLARE obj regclass; role_name text; expected text[]; actual text[];
BEGIN
  FOREACH obj IN ARRAY ARRAY['public.transcript_chunks'::regclass,'public.transcript_chunks_id_seq'::regclass] LOOP
    IF (SELECT relowner FROM pg_class WHERE oid=obj) <> 'postgres'::regrole THEN RAISE EXCEPTION 'Object owner drift'; END IF;
    IF EXISTS (SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid=obj
       AND (a.grantee NOT IN ('postgres'::regrole,'anon'::regrole,'authenticated'::regrole,'service_role'::regrole)
            OR a.grantor <> 'postgres'::regrole OR a.is_grantable)) THEN
      RAISE EXCEPTION 'Unexpected PUBLIC/other ACL or grantor drift';
    END IF;
    FOREACH role_name IN ARRAY ARRAY['postgres','anon','authenticated','service_role'] LOOP
      IF obj='public.transcript_chunks'::regclass THEN
        expected := CASE WHEN current_setting('server_version_num')::int >= 170000
          THEN ARRAY['DELETE','INSERT','MAINTAIN','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE']
          ELSE ARRAY['DELETE','INSERT','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE'] END;
      ELSE expected := ARRAY['SELECT','UPDATE','USAGE']; END IF;
      SELECT array_agg(a.privilege_type ORDER BY a.privilege_type) INTO actual
        FROM pg_class c, LATERAL aclexplode(c.relacl) a WHERE c.oid=obj AND a.grantee=role_name::regrole;
      IF actual IS DISTINCT FROM expected THEN RAISE EXCEPTION 'Prior ACL drift for % on %',role_name,obj; END IF;
    END LOOP;
  END LOOP;
END $acl$;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;
COMMIT;
```

## 3. Change B — separate exact approval packet

**NOT APPROVED. Separate approval for target Supabase `pwbothxnfjnxkhrcxyvd`,
la-politician, us-west-2, database/executor postgres. Installation does not
authorize invocation, ingestion or corpus replacement.**

This is the unchanged prepared B from eb06c4e. Recommend **A first, verify A,
then separately approve B**. There is no SQL dependency requiring B first; B can
install independently, but cannot repair A's broad grants by itself.
[Scope/hash](database-review/B-approval.json), [contract](database-review/contract.json), [fresh evidence](database-review/review-refresh-2026-11-07.json).

Full callable contract:
`public.replace_transcript_chunks(p_video_id text, p_embedding_model text, p_rows jsonb)`
returns `TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)`.
Language plpgsql; VOLATILE; owner postgres; SECURITY INVOKER;
configured search_path=`pg_catalog, pg_temp`. Main table/vector references are
public-qualified; staging is pg_temp-qualified. The tested transaction/cohort
validation, advisory lock, upsert/delete and exact-result contract is preserved.

One transaction creates (not overwrites) the function, sets owner, removes
PUBLIC/anon/authenticated EXECUTE and grants service_role EXECUTE before commit.
Exact ordinary ACL is postgres/service_role EXECUTE with no grant option.
Anonymous/authenticated effective invocation is false; no parent memberships
supply an alternate path. Owner/superuser powers remain. Existing authenticator
and supabase_realtime_admin may SET ROLE service_role under platform controls;
postgres inherits service_role. These are documented existing administrative
paths, not new browser execution grants or a claim that only two login sessions
can ever execute. The INVOKER service role's existing table, sequence, TEMP,
schema/type/function privileges and BYPASSRLS enable later authorized use.

The fresh all-schema proname query found **no replacement overloads**, and no
row triggers exist on transcript_chunks. Catalog/repository dependency review
is in README; dynamic external callers cannot be disproven by pg_depend alone.
The owner default gives PUBLIC function execution and public-schema defaults
can add browser grants; B explicitly removes those in the creation transaction.
No schema-wide default or other-function grant is changed.

**Existing platform DDL effects:** extensions.pgrst_ddl_watch is enabled and
requests `NOTIFY pgrst, 'reload schema'` for CREATE/ALTER FUNCTION. Its existing
sql_drop counterpart can notify when recovery drops this non-temporary function.
These are automatic cache notifications, not replacement execution or corpus
writes. ensure_rls is limited to CREATE TABLE/CREATE TABLE AS/SELECT INTO,
so it does not apply to installation of this function. Extension-access/drop
triggers are restricted to CREATE/DROP EXTENSION; neither is in B. No row or
DDL trigger is changed. Supabase's platform watchers/PostgREST runtime were not
reproduced by the vanilla disposable45-case suite; current trigger definitions
were inspected read-only. Cache reload completion/HTTP exposure remain runtime
postflight considerations, never permission to invoke replacement as a probe.

B and recovery hold SHARE to pin corpus counts, permit ordinary SELECT, and can
block writers/stronger DDL. Lock timeout 2s; individual statement timeout 15s.
CREATE/ALTER/DROP function also takes relevant catalog locks and can conflict
with concurrent object DDL. The signature must be absent on installation.
Recovery refuses changed input/output contract, body, language, owner, security,
search_path or execution ACL and drops the exact signature without CASCADE.
Existing dependencies can block removal; do not override them.

After an approved installation, run [postflight.sql](database-review/postflight.sql) and both
[read-role-postflight.sql](database-review/read-role-postflight.sql) READ ONLY transactions.
Expect counts 5003/3341/9, unchanged A/read-RPC state, full pinned B contract,
no PUBLIC/anon/authenticated EXECUTE and service execution privilege present.
Use catalog/has_function_privilege checks, never live replacement or destructive
probes, including rollback-wrapped calls. Stop on any drift or ambiguous result.

**Reuse 45/45 PG 16.14 and 45/45 PG 17.6/vector0.8.2.** All tested input hashes still
match. Each run consists of 18 existing contract cases, the same 18 run against B,
and 9 focused hardening/recovery cases. The existing cases cover atomic rollback,
invalid/duplicate/incorrect cohort payloads, dimensions, exact intended keys,
stale-row deletion, idempotence and service access. Focused cases verify browser
invocation denial, no install-time row or table-ACL changes, overwrite refusal,
recovery to absence, full-signature/search_path drift rejection, public staging
namesake preservation and required reads. No full app rerun or live invocation
is claimed. New catalog evidence documents platform side effects separately.

### Full forward SQL

SHA-256: `818c0d9c7135644e0a6796a6f7358aa55f9526a28293dc72553481b0802cf330`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.transcript_chunks IN SHARE MODE;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;

DO $absent$ BEGIN
  IF to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)') IS NOT NULL THEN RAISE EXCEPTION 'Replacement already exists; review instead of overwriting'; END IF;
END $absent$;
create function public.replace_transcript_chunks(
    p_video_id text,
    p_embedding_model text,
    p_rows jsonb
)
returns table (
    intended_count bigint,
    upserted_count bigint,
    deleted_count bigint
)
language plpgsql
volatile
security invoker
set search_path = pg_catalog, pg_temp
as $$
declare
    v_intended   bigint;
    v_distinct   bigint;
    v_present    bigint;
    v_upserted   bigint;
    v_deleted    bigint;
    v_bad        text;
begin
    if p_video_id is null or length(trim(p_video_id)) = 0 then
        raise exception 'replace_transcript_chunks: p_video_id is required';
    end if;
    if p_embedding_model is null or length(trim(p_embedding_model)) = 0 then
        raise exception 'replace_transcript_chunks: p_embedding_model is required';
    end if;
    if p_rows is null or jsonb_typeof(p_rows) <> 'array' then
        raise exception 'replace_transcript_chunks: p_rows must be a jsonb array';
    end if;

    -- (2) Transaction-scoped lock for this (video, model) cohort. Two concurrent
    -- replacements of the same recording serialize here instead of interleaving
    -- their upsert and delete phases.
    perform pg_advisory_xact_lock(
        hashtextextended(p_video_id || '|' || p_embedding_model, 0)
    );

    -- (1) Stage the intended rows with explicit casts. A malformed payload
    -- fails here, before anything in public.transcript_chunks is touched.
    -- Dropped explicitly as well as ON COMMIT so that replacing several videos
    -- inside one transaction does not collide on the staging table.
    drop table if exists pg_temp._staged_chunks;
    create temporary table _staged_chunks on commit drop as
    select
        (e->>'video_id')::text                                as video_id,
        (e->>'meeting_date')::date                            as meeting_date,
        (e->>'chunk_idx')::int                                as chunk_idx,
        (e->>'start_sec')::real                               as start_sec,
        (e->>'end_sec')::real                                 as end_sec,
        (e->>'source_label')::text                            as source_label,
        (e->>'resolved_role')::text                           as resolved_role,
        (e->>'resolved_official_id')::text                    as resolved_official_id,
        (e->>'resolved_name')::text                           as resolved_name,
        (e->>'resolution_method')::text                       as resolution_method,
        (e->>'text')::text                                    as text,
        (e->>'token_count')::int                              as token_count,
        (e->>'turn_speaker_raw')::text                        as turn_speaker_raw,
        coalesce((e->>'sub_chunk_idx')::int, 0)               as sub_chunk_idx,
        coalesce((e->>'sub_chunk_of')::int, 1)                as sub_chunk_of,
        (e->>'embedding')::public.vector                             as embedding,
        (e->>'embedding_model')::text                         as embedding_model,
        coalesce((e->>'embedding_version')::int, 1)           as embedding_version
    from jsonb_array_elements(p_rows) as e;

    select count(*), count(distinct chunk_idx) into v_intended, v_distinct
    from pg_temp._staged_chunks;

    -- (3) Completeness and consistency checks on the staged set.
    if v_intended = 0 then
        raise exception
            'replace_transcript_chunks: refusing to replace % with an empty row set',
            p_video_id;
    end if;
    if v_distinct <> v_intended then
        raise exception
            'replace_transcript_chunks: chunk_idx values are not unique (% rows, % distinct)',
            v_intended, v_distinct;
    end if;

    -- Guard against a mixed payload silently rewriting a different cohort.
    select string_agg(distinct video_id, ',') into v_bad
    from pg_temp._staged_chunks where video_id is distinct from p_video_id;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: payload contains foreign video_id(s): %', v_bad;
    end if;
    select string_agg(distinct embedding_model, ',') into v_bad
    from pg_temp._staged_chunks where embedding_model is distinct from p_embedding_model;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: payload contains foreign embedding_model(s): %', v_bad;
    end if;

    -- Required metadata must be present on every staged row.
    select string_agg(chunk_idx::text, ',' order by chunk_idx) into v_bad
    from pg_temp._staged_chunks
    where meeting_date is null or chunk_idx is null or start_sec is null
       or end_sec is null or resolved_role is null or resolution_method is null
       or text is null or length(trim(text)) = 0 or token_count is null
       or embedding is null or sub_chunk_idx is null or sub_chunk_of is null;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: rows missing required metadata at chunk_idx: %', v_bad;
    end if;

    -- Wrong-dimension vectors must never reach the retrieval cohort.
    select string_agg(chunk_idx::text, ',' order by chunk_idx) into v_bad
    from pg_temp._staged_chunks where public.vector_dims(embedding) <> 1024;
    if v_bad is not null then
        raise exception
            'replace_transcript_chunks: non-1024-dim embedding at chunk_idx: %', v_bad;
    end if;

    -- (4) Upsert every intended row.
    insert into public.transcript_chunks (
        video_id, meeting_date, chunk_idx, start_sec, end_sec,
        source_label, resolved_role, resolved_official_id, resolved_name,
        resolution_method, text, token_count, turn_speaker_raw,
        sub_chunk_idx, sub_chunk_of, embedding, embedding_model, embedding_version
    )
    select
        video_id, meeting_date, chunk_idx, start_sec, end_sec,
        source_label, resolved_role, resolved_official_id, resolved_name,
        resolution_method, text, token_count, turn_speaker_raw,
        sub_chunk_idx, sub_chunk_of, embedding, embedding_model, embedding_version
    from pg_temp._staged_chunks
    on conflict (video_id, chunk_idx, embedding_model) do update set
        meeting_date         = excluded.meeting_date,
        start_sec            = excluded.start_sec,
        end_sec              = excluded.end_sec,
        source_label         = excluded.source_label,
        resolved_role        = excluded.resolved_role,
        resolved_official_id = excluded.resolved_official_id,
        resolved_name        = excluded.resolved_name,
        resolution_method    = excluded.resolution_method,
        text                 = excluded.text,
        token_count          = excluded.token_count,
        turn_speaker_raw     = excluded.turn_speaker_raw,
        sub_chunk_idx        = excluded.sub_chunk_idx,
        sub_chunk_of         = excluded.sub_chunk_of,
        embedding            = excluded.embedding,
        embedding_model      = excluded.embedding_model,
        embedding_version    = excluded.embedding_version,
        ingested_at          = now();
    get diagnostics v_upserted = row_count;

    -- (5) Verify the intended keys are all actually present BEFORE deleting.
    select count(*) into v_present
    from public.transcript_chunks c
    join pg_temp._staged_chunks s
      on s.video_id = c.video_id
     and s.chunk_idx = c.chunk_idx
     and s.embedding_model = c.embedding_model;

    if v_present <> v_intended then
        raise exception
            'replace_transcript_chunks: post-upsert verification failed for % (% of % intended keys present); rolling back',
            p_video_id, v_present, v_intended;
    end if;
    if v_upserted <> v_intended then
        raise exception
            'replace_transcript_chunks: upsert touched % rows; expected %; rolling back',
            v_upserted, v_intended;
    end if;

    -- (6) Only now remove stale keys, scoped strictly to this cohort.
    delete from public.transcript_chunks c
    where c.video_id = p_video_id
      and c.embedding_model = p_embedding_model
      and not exists (
          select 1 from pg_temp._staged_chunks s where s.chunk_idx = c.chunk_idx
      );
    get diagnostics v_deleted = row_count;

    return query select v_intended, v_upserted, v_deleted;
end;
$$;


ALTER FUNCTION public.replace_transcript_chunks(text,text,jsonb) OWNER TO postgres;
REVOKE ALL PRIVILEGES ON FUNCTION public.replace_transcript_chunks(text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.replace_transcript_chunks(text,text,jsonb) TO service_role;

DO $rpc$
DECLARE f oid := to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)');
BEGIN
  IF f IS NULL OR NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid=f AND proowner='postgres'::regrole
      AND NOT prosecdef AND provolatile='v' AND md5(prosrc)='dc3d667d0a6a03a86c823da31eff205f'
      AND prokind='f' AND prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
      AND pg_get_function_arguments(oid)='p_video_id text, p_embedding_model text, p_rows jsonb'
      AND pg_get_function_result(oid)='TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)'
      AND proconfig=ARRAY['search_path=pg_catalog, pg_temp']) THEN RAISE EXCEPTION 'Replacement contract/config drift'; END IF;
  IF has_function_privilege('anon',f,'EXECUTE') OR has_function_privilege('authenticated',f,'EXECUTE')
     OR NOT has_function_privilege('service_role',f,'EXECUTE') THEN RAISE EXCEPTION 'Replacement effective grants incorrect'; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.oid=f
       AND (a.grantee NOT IN ('postgres'::regrole,'service_role'::regrole) OR a.is_grantable)) THEN
    RAISE EXCEPTION 'Unexpected replacement ACL including PUBLIC';
  END IF;
END $rpc$;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;
COMMIT;
```

### Full recovery SQL — separate approval

This restores the prior function absence. No corpus rows are changed, but future ingestion callers would lose the RPC. No CASCADE or automatic retry is authorized.

SHA-256: `4ca0c947f4637fd5aa9a9310ceffaac8e25e9d57cc090bf3a74f18bfc206d263`

```sql
-- REVIEW ONLY. Target Supabase pwbothxnfjnxkhrcxyvd. Separate approval required.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
LOCK TABLE public.transcript_chunks IN SHARE MODE;

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;

DO $rpc$
DECLARE f oid := to_regprocedure('public.replace_transcript_chunks(text,text,jsonb)');
BEGIN
  IF f IS NULL OR NOT EXISTS (SELECT 1 FROM pg_proc WHERE oid=f AND proowner='postgres'::regrole
      AND NOT prosecdef AND provolatile='v' AND md5(prosrc)='dc3d667d0a6a03a86c823da31eff205f'
      AND prokind='f' AND prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
      AND pg_get_function_arguments(oid)='p_video_id text, p_embedding_model text, p_rows jsonb'
      AND pg_get_function_result(oid)='TABLE(intended_count bigint, upserted_count bigint, deleted_count bigint)'
      AND proconfig=ARRAY['search_path=pg_catalog, pg_temp']) THEN RAISE EXCEPTION 'Replacement contract/config drift'; END IF;
  IF has_function_privilege('anon',f,'EXECUTE') OR has_function_privilege('authenticated',f,'EXECUTE')
     OR NOT has_function_privilege('service_role',f,'EXECUTE') THEN RAISE EXCEPTION 'Replacement effective grants incorrect'; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a WHERE p.oid=f
       AND (a.grantee NOT IN ('postgres'::regrole,'service_role'::regrole) OR a.is_grantable)) THEN
    RAISE EXCEPTION 'Unexpected replacement ACL including PUBLIC';
  END IF;
END $rpc$;
DROP FUNCTION public.replace_transcript_chunks(text,text,jsonb);

DO $check$
DECLARE n bigint; parents bigint; videos bigint;
BEGIN
  IF current_user <> 'postgres' THEN RAISE EXCEPTION 'Expected reviewed executor postgres'; END IF;
  IF (SELECT relowner <> 'postgres'::regrole OR NOT relrowsecurity FROM pg_class WHERE oid='public.transcript_chunks'::regclass) THEN
    RAISE EXCEPTION 'Owner/RLS drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member IN ('anon'::regrole,'authenticated'::regrole,'service_role'::regrole)) THEN
    RAISE EXCEPTION 'Role membership drift; review inherited privileges';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Browser role bypass drift';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.transcript_chunks'::regclass AND attacl IS NOT NULL) THEN
    RAISE EXCEPTION 'Column ACL drift; review before changing table privileges';
  END IF;
  IF (SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks') <> 1
     OR NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='transcript_chunks'
       AND policyname='transcript_chunks_read_anon' AND cmd='SELECT' AND qual='true'
       AND roles @> ARRAY['anon','authenticated']::name[] AND cardinality(roles)=2 AND permissive='PERMISSIVE') THEN
    RAISE EXCEPTION 'Read policy drift';
  END IF;
  SELECT count(*), count(*) FILTER(WHERE sub_chunk_idx=0), count(DISTINCT video_id)
    INTO n,parents,videos FROM public.transcript_chunks;
  IF (n,parents,videos) IS DISTINCT FROM (5003::bigint,3341::bigint,9::bigint) THEN
    RAISE EXCEPTION 'Corpus counts drift; refresh approval';
  END IF;
  IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace ns ON ns.oid=p.pronamespace
      WHERE ns.nspname='public' AND NOT p.prosecdef AND p.provolatile='s' AND
       (p.proname,md5(p.prosrc)) IN (
        ('search_transcripts','67e13f5e574b0ef81e124b42256b775d'),
        ('search_public_comment','33e4ba028630765299b3359a19b9a396'),
        ('get_transcript_coverage','22161cc4439ed49a91aae3b0146c2d7e'))) <> 3 THEN
    RAISE EXCEPTION 'Read RPC drift';
  END IF;
END $check$;
COMMIT;
```

## 4. Remote preflight and exact proposed action

**Push BLOCKED. No remote action or settings change is approved.** The configured
production branch, release-branch deployment rules and build commands remain
unverified. Draft PR status does not prevent a Vercel Preview deployment.

### Source and remote identities

The starting local branch was `release/weekend-2026-11-08`, full head
`eb06c4e210d4e4457a5d862bb134243b0f61c3f3`. It matched the requested baseline.
Two pre-existing untracked .DS_Store files meant that the initial working tree
was not fully clean. They were preserved, and repository-local .gitignore now
excludes macOS Finder metadata. Annotation/review files create a new commit;
the final clean head is bound in the exported approval record after committing.
**Do not reuse the old head or an approval tied to it.**

Fresh GitHub reads confirmed main
`25a51ebe617f5d24c4a7c405a6498c2104f1a2fd`, protected=true, no matching remote
release ref and no open release-head/main-base PR. No Git remote is configured
locally; the proposal uses the explicit repository URL. Full protection rules
remain inaccessible from the earlier authorized read; the current branch
summary does not establish review/enforcement requirements.

### Observed configuration versus unknowns

| Question | Read-only finding |
| --- | --- |
| Exact project/team | prj_I1kOylFB27M1pABXw5luy5pgkjXv / team_aPlAJHap7jEuwyrs7qWcc9OL, check-your-politician / team-politicheck |
| Current production | READY dpl_HqsZGeeJAKYML6H8X5fuj1cj5iXb, source git, main at 25a51ebe617f5d24c4a7c405a6498c2104f1a2fd |
| Configured production branch | **Unknown.** A production deployment sourced from main is evidence of that deployment, not a read of the current branch setting. |
| Release-branch environment | No custom environments returned for this branch. Its exact built-in Preview/Production mapping remains unverified until Git branch rules are visible. |
| Automatic Preview behavior | Historical Git preview creation is established; current enablement/ignored-build/branch rules are omitted by both project-detail and project-list connectors. Treat a push as potentially deploying; do not push while unknown. |
| Build/startup settings | Node 24.x, framework null. Actual root/build/install/output/ignored-build commands not returned. |
| Attached domains | lapolitician.akhilvasvani.com and check-your-politician.vercel.app are verified, no branch/custom-environment binding. Current production deployment owns those aliases plus project/main-generated aliases. Potential release-push alias effects remain blocked on branch mapping. |
| Browser fallback | In-app browser is now available, but exact Git settings redirected to Vercel login, then GitHub sign-in. No credentials entered; no authenticated settings read occurred. No Vercel CLI is installed on PATH; none installed. |
| Standard Preview database | The only reread environment value was the previously approved non-secret SUPABASE_URL: hostname pwbothxnfjnxkhrcxyvd.supabase.co. It is scoped to Preview; no release-specific environment override was returned. Standard Preview therefore shares the existing database. The unresolved release-branch target mapping remains a separate gate. |
| Credential/cost controls | Supabase anonymous key is Preview-only by name/scope; no service-role key name was returned. Perplexity and limiter names exist for Preview/Production. Neither kill-switch name is configured. No secret value or credential validity was read/tested. |

Evidence: [remote-preflight-2026-11-07.json](remote-preflight-2026-11-07.json).
The fresh main/ref/PR and configuration reads made no remote mutation.

### Checked-in workflows and external effects

| Event | Actions in the reviewed source | Effects / limits |
| --- | --- | --- |
| First release-branch push, before PR | CI push filter is main only; guard is pull_request only; refresh is schedule/workflow_dispatch only | Publishes Git source; Vercel Git integration or other external hooks may react. No manual deployment, migration or workflow dispatch is implied. |
| Open/synchronize/reopen matching draft PR | la-money-votes CI / test and Guard non-goals / guard | Offline Python/Node tests, schema validation, dry build, guard; runner/dependency downloads, GitHub logs/checks and build-report artifact upload. No checked-in migration/ingestion/provider batch is invoked. Draft does not suppress jobs or Vercel Preview. |
| Deployment/deployment_status event | No checked-in workflow listens for these events | Vercel/GitHub App statuses/comments and other uninventoried hooks remain possible. |
| Main push/merge | Matching CI push job | May publish production through Git; separate approval required. |
| Existing refresh schedule/manual dispatch | Monday 15:00 UTC, first-Monday-Pacific gate; manual dispatch bypasses date gate | Reads live Socrata data, writes generated files, creates/updates automated/data-refresh branch and PR. This has external writes and can trigger a separate Git preview; neither branch push nor this draft PR dispatches it. |

CI uses Python 3.11 / Node 22; Vercel project reports Node 24.x. CI explicitly collects
and skips the original 18-case PostgreSQL module. It does not run the local 45-case
A/B suite. Existing 45/45 PG 16.14 and 45/45 PG 17.6 evidence is retained; no suite
was rerun. The GitHub Actions artifact upload is an external platform write,
even though the CI contents permission is read-only and it does not mutate the
Supabase corpus. Existing app/webhook behavior outside these three workflows
has not been exhaustively inventoried.

### Build, startup and verification write assessment

The tracked repository has no package.json, dependency install lifecycle hook,
Dockerfile/Procfile, or framework startup command. la-money-votes/vercel.json
only sets four function duration limits; it defines no build/install command,
cron or migration. The inspected JavaScript module imports initialize constants
and request handlers; they do not execute migrations, ingestion or network calls
at module load. SQL files are inert unless an explicit command runs them.
The standalone Python ingestion/backfill tools are not invoked by these CI jobs.

This source inspection cannot establish that an unknown dashboard build/install
command is safe. **Build/startup shared-write behavior remains unverified until
those exact settings are read.** No build or preview was launched to find out.

For the existing application handlers:

- GET transcript coverage calls the STABLE/INVOKER read RPC and writes request
  logs, with no embedding, Redis counter or Supabase corpus mutation in the
  inspected code. Loading a profile can automatically request this coverage.
- Valid transcript-search requests write shared Redis limiter counters, then
  call paid embeddings and read RPCs. Valid Ask-AI requests likewise write
  limiter counters and can call paid generation. These are not authorized
  verification probes, even though search does not replace transcript rows.
- The preview secret names permit those paths if credentials work. No validity
  test was performed. API source accepts anonymous read credentials and contains
  no replacement call; the replacement adapter is a separately gated CLI.
- The proposed zero-paid, no-corpus-write validation would require separately
  reviewed branch-scoped kill switches before any valid query submission. Their
  early returns precede limiter/provider calls. Do not change settings under
  this inspection instruction. Actual zero-external-write claims would also
  need to account for deployment/log/status/artifact activity; none is implied.

### Exact proposed action, after unresolved preconditions and separate approval

The final head is substituted into the exported copy of this plan and approval
record. Until the missing production branch, release mapping and exact build
commands are verified, **do not request or execute a blind push**. Resolve the
read-only settings access first. No setting may be changed just to avoid Preview.

The contemplated normal, non-force push is:

```sh
git push https://github.com/akhilvasvani/check-your-politician.git \
  <FINAL_REVIEW_HEAD>:refs/heads/release/weekend-2026-11-08
```

Intended PR: repository akhilvasvani/check-your-politician, base main, head
release/weekend-2026-11-08, draft=true, maintainer_can_modify=false. Review the
bound [draft text](REMOTE_PR_DRAFT.md). Before any approved execution, require a
clean tree, exact approved SHA, unchanged/reconciled remote base, absence or
review of the target ref/PR, and resolved deployment effects. Check the remote
ref before retrying an uncertain push/PR result.

If read-only settings establish automatic Preview creation, the later approval
must expressly include **one source push, one draft PR, expected CI/guard and
automatic Vercel Preview build/deployment**, plus platform logs/artifacts/statuses
and possible notifications. It must identify project, branch, SHA, environment,
domain effects and approved validation scope. No merge, manual deploy,
promotion, workflow dispatch, env change, paid calls, ingestion or shared SQL
is included. Current evidence does not yet support that approval request.

## 5. Remaining release gates

| Gate | Evidence available | Unresolved requirement/action |
| --- | --- | --- |
| Original requirements |Proposed 25-group matrix from recovered M2/M3 plans and owner decisions | Original M1/M4/M5 details and synthesis requirement remain unknown/unwaived; no new search invented them |
| DB boundary |Read-only state verified; unchanged prepared A/B; PG16/17 tests reused |Separate A approval, read-only postflight, separate B approval, read-only postflight; no live replacement probe |
| Current usable corpus |Historical 9 recordings / 5,003 chunks / 3,341 parents reconciled |Verified manual captions/current committee material; release corpus fixed only after separately approved source/cost/write plan |
| Caption diagnosis |Final listing unclassified_tool_error/code 1; cookie access unknown; download/parsing not reached; no caption payload tested |Probing stays stopped; this is not absent captions or proven authentication failure |
| Relevance | 30/36 original queries replayed offline, 234/234 pooled candidates; prior results retained |Six missing traces, supplemental/committee cases and full live acceptance; no new paid evaluation |
| Practice attribution |Revised human labels imported without overwrite; contradictions and unresolved boundaries retained |Target-aligned follow-up for 01/03/10 and boundaries 11/12; generic role outputs are not personal-name identity judgments |
| Held-out attribution |Requirement preserved | At least 100 independently labeled held-out turns from verified expanded corpus; Council/committee strata, unresolved handling and councilmember precision≥0.85; practice contributes 0 |
| Deployment/configuration |Production deployment identity, names/scopes and standard Preview DB target verified |Actual production branch/release mapping/build behavior unknown; browser sign-in needed; push remains blocked |
| Operations |Local code/mocks and prior app baseline accepted |Production transcript configuration, live HTTP credential behavior, durable limiter/ingress/spending bounds and approved preview verification |
| Release | NO-GO |All applicable gates and exact-SHA release approval |

The current practice comparison is explicitly unblinded only after the revision
freeze. The future held-out sample must remain independent of these practice
items and diagnostics. No model answer replaced a user annotation.

Next approval object is **A only**, identified by its target and forward SQL hash
above. After A is separately approved/applied and read-only postflight passes,
B requires its own approval. No technical dependency requires reversing that
order. The remote action cannot proceed while deployment behavior is unknown.
