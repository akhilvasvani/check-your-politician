# Read-only remote preflight — November 7, 2026

**Push BLOCKED. No remote action or settings change is approved.** The configured
production branch, release-branch deployment rules and build commands remain
unverified. Draft PR status does not prevent a Vercel Preview deployment.

## Source and remote identities

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

## Observed configuration versus unknowns

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

## Checked-in workflows and external effects

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

## Build, startup and verification write assessment

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

## Exact proposed action, after unresolved preconditions and separate approval

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
