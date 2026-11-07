# Remote validation proposal

Prepared November 6, 2026 Pacific, with read-only observations through
November 7 at 04:02 UTC. This is a reviewable proposal. Remote push, draft PR,
configuration changes and deployment remain subject to the owner's approval
under section 4 of the weekend mandate. No such action was performed while
preparing this document.

## Exact targets and SHA binding

| Item | Observed value |
| --- | --- |
| Repository | `akhilvasvani/check-your-politician` |
| Local branch / proposed remote head | `release/weekend-2026-11-08` |
| Local head when preparation began | `f0c0c40f8536720b7fb057efa02440e38518f945` |
| Final approved source SHA | `<APPROVED_RELEASE_SHA>` — release lead binds after preparation commits |
| Draft PR base | `main` |
| Connected GitHub main | `25a51ebe617f5d24c4a7c405a6498c2104f1a2fd` |
| Vercel project | `prj_I1kOylFB27M1pABXw5luy5pgkjXv` / `check-your-politician` |
| Vercel team | `team_aPlAJHap7jEuwyrs7qWcc9OL` / `team-politicheck` |
| Current production deployment | `dpl_HqsZGeeJAKYML6H8X5fuj1cj5iXb`, READY, source `git`, main at `25a51ebe617f5d24c4a7c405a6498c2104f1a2fd` |
| Production domain | `lapolitician.akhilvasvani.com` |

The final SHA is deliberately unresolved while preparation continues. Fill it
in the final approval record, together with the reviewed PR body and command,
after the source tree is committed and clean. An approval of the preparation
head does not cover subsequent commits. Avoid a self-referential commit hash
inside the commit being approved.

`git remote -v` currently returns no remotes. An `origin/main` tracking ref
exists locally, but the proposed push uses the explicit repository URL.
Before execution, re-read the connected main ref, target release ref and open
PRs. A moved base requires checking the integrated diff and CI expectations
again. An existing release branch or PR requires reconciliation before creation.

## Verified configuration and remaining uncertainty

The connected project response reports Node `24.x`, framework `null`, and
Vercel Authentication enabled for `all_except_custom_domains`. Both
`lapolitician.akhilvasvani.com` and `check-your-politician.vercel.app` are verified
project domains with no `gitBranch` or custom-environment assignment. These
metadata fields do not establish a tested access boundary for a new preview.

The latest production is a Git deployment from main. A recent READY deployment
`dpl_HJLAisUEP4h3Hspt7r6WmZDnz3zf` records branch `automated/data-refresh` at
`c6281bb7f45abb57e1e737ec466083655517d7f4` with a non-production target. This
demonstrates past preview creation. Vercel normally deploys branch pushes and
production-branch changes through its Git integration; therefore treat the
proposed branch push as potentially deployment-triggering.
[Vercel Git documentation](https://vercel.com/docs/git)

The plugin's project response omits Git connection settings, deployment
enablement/branch rules, configured production branch, root directory, build,
install and output commands, and ignored-build rules. The deployment's nested
project contains only `id`, `name` and `framework`. Current rules for
`release/weekend-2026-11-08` remain unverified. The next safe read is the known
project's Git, Environments and Build and Deployment settings, without opening
environment-value controls or changing fields. A bounded CUA attempt at
`https://vercel.com/team-politicheck/check-your-politician/settings/git` could
not open: `Browser is not available: iab`; browser inventory was empty. No
authenticated settings page was inspected. An enabled browser session or a
connector exposing those safe fields is needed to finish this read.

GitHub reports main `protected=true`. Its branch summary shows no required
status-check contexts, and the repository ruleset list is empty. The full
branch-protection GET returns 403, `Resource not accessible by integration`.
Review requirements, administrator enforcement and push restrictions therefore
remain unknown. Preserve protection and require the validation results below
regardless of whether GitHub enforces them automatically.

The existing release packet's names-and-targets inventory finds Supabase
variables scoped to Preview and no `ASK_AI_DISABLED` or
`TRANSCRIPT_SEARCH_DISABLED` entries. This preparation did not read environment
values or credentials. Presence does not establish a working HTTP credential.
Production transcript configuration remains a separate release gate.

Safe metadata evidence is recorded locally in
`work/release/remote-validation/observations.json`. Checked-in CI uses Node 22,
while Vercel reports Node 24.x; remote preview smoke must cover that runtime.

## Events and side effects

| Proposed event | Checked-in GitHub Actions behavior | Other effects to account for |
| --- | --- | --- |
| First push of the release branch, before a PR | No `ci.yml` push run because its push filter is main; no guard or refresh run | Publishes the reviewed source/history to GitHub. Vercel may build a preview. GitHub/Vercel notifications, statuses and app hooks may run. |
| Open draft PR to main | `la-money-votes CI` (`test`) and `Guard non-goals (transcript-rag branches)` (`guard`) are expected because the changed paths and release branch match | Draft status does not suppress these jobs. Vercel may attach checks/comments or create/update a preview. |
| Later push to that open PR | PR `synchronize` reruns both matching jobs | Another preview build may occur. Each changed SHA needs its applicable approval. |
| Merge or push to main | Matching main push runs CI; guard is a PR job | May deploy production and change public aliases. Requires a separate final release decision. |
| Existing schedule or manual refresh dispatch | `refresh-data.yml` only runs on Monday 15:00 UTC schedule, gated to the first Monday Pacific, or explicit `workflow_dispatch` | It fetches Socrata data and proposes an automated data-refresh PR. Branch push and PR creation do not dispatch it. |

The local tree has exactly these three workflows. Connected main currently
contains `ci.yml` and `refresh-data.yml`; the guard and CI integration changes
are part of this proposed PR. CI has read-only contents permission, runs
offline Python/Node checks, validates committed data, dry-runs the publication
build and uploads its report. It does not provision PostgreSQL or run provider
batches. The database step explicitly expects all collected integration tests to
skip. Specifically, it collects the original 18-case replacement module; the new
A/B review module is exercised only in the documented local PG16/PG17 runs.
Hosted CI does not execute the 45-case disposable review suite.
No deploy action appears in these workflows. External GitHub Apps and webhooks
were not inventoried, so absence of other external reactions is unverified.

`pull_request` defaults to opened, synchronized and reopened events. CI checks
the PR merge ref by default; record both the event's head SHA and tested merge
SHA, rather than equating them. A merge conflict can prevent PR checks from
running. [GitHub workflow event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request)

## Proposed actions after approval

1. Resolve the missing Git/preview settings and confirm the production branch
   is main, the application root is `la-money-votes`, and build/install/output
   behavior is appropriate for the static app. Check ignored-build rules for
   this branch and identify any extra project targets. Record observed values,
   without changing settings or inferring them from a previous successful build.
2. Prepare a separate, explicit configuration approval if the push can create a
   preview. The recommended preview gate is `ASK_AI_DISABLED=true` and
   `TRANSCRIPT_SEARCH_DISABLED=true`, scoped only to Preview branch
   `release/weekend-2026-11-08` on the project/team above. Capture names/scopes,
   never secrets. New settings apply to subsequent deployments. This setting
   change is not authorized by the preparation task. With those gates verified
   on the resulting preview, the proposed validation budget is zero paid
   requests and zero shared database writes. Build/hosting usage is still
   possible; a dollar cap has not been independently established.
3. Bind the final source SHA, review the exact diff and PR body, and obtain
   approval for one push plus one draft PR, explicitly including any automatic
   preview build and hosting effects. Do not combine this with permission to
   merge, dispatch workflows, deploy manually or promote production.
4. Run the following preconditions and push only after that approval. These
   commands assume the repository root and existing authorized authentication;
   they do not extract credentials or configure a new remote.

   ```sh
   set -euo pipefail
   approved_sha='<APPROVED_RELEASE_SHA>'
   test "$(git branch --show-current)" = 'release/weekend-2026-11-08'
   test -z "$(git status --porcelain)"
   test "$(git rev-parse HEAD)" = "$approved_sha"
   git diff --check 25a51ebe617f5d24c4a7c405a6498c2104f1a2fd..."$approved_sha"
   git push https://github.com/akhilvasvani/check-your-politician.git \
     "$approved_sha:refs/heads/release/weekend-2026-11-08"
   ```

   Run sequentially with failure stopping execution. No force push is proposed.
   Before the push, confirm via a read-only branch lookup that this will create
   the intended branch, or review the exact existing remote head if it exists.
5. Verify the remote ref equals the approved SHA, then use the GitHub connector's
   `create_pull_request` operation with this reviewed structured payload:

   ```json
   {
     "repository_full_name": "akhilvasvani/check-your-politician",
     "base": "main",
     "head": "release/weekend-2026-11-08",
     "draft": true,
     "maintainer_can_modify": false,
     "title": "Prepare weekend release: transcript safety, evidence and operations",
     "body": "<reviewed body from la-money-votes/release/REMOTE_PR_DRAFT.md>"
   }
   ```

   The local body file is the concrete draft for approval. Replace its final-SHA
   placeholder when binding approval, then pass that exact text as `body`.
   Creation publishes the text and may notify repository subscribers. If the
   request result is ambiguous, read open PRs before retrying to avoid duplicates.
6. Read the resulting PR, checks and deployment metadata. Record PR URL, base and
   head SHA, workflow event, run/check identities, merge SHA, conclusion and build
   report. Both expected jobs must succeed for the exact current PR context.
   Missing, skipped or stale checks require investigation; old PR #22 checks do
   not validate this integration. Do not dispatch or rerun a workflow implicitly.
7. Find the preview by exact project, branch and approved SHA. Record deployment
   ID, hostname, target, READY/error state, Git SHA and protection. No manual
   deployment or share/bypass link is included. Confirm production still points
   to the baseline deployment. A missing preview is a configuration observation,
   not authorization to create one manually.
8. On an authorized accessible preview, verify static assets and all 16 profile
   routes, freshness/source disclosures, desktop/mobile layout, keyboard paths,
   coverage fallback and source-separated search states. Read-only coverage may
   access the live database, so record that separately from mocked UI states.
   Paid endpoint success paths use local fixtures until a later exact request
   and budget approval. Verify the kill-switch 503 responses only after confirming
   the deployed gates and exact SHA. Avoid submitting queries on an ungated
   preview. Protected-browser access must use an available authorized session;
   stop if unavailable rather than creating access links or retrieving cookies.
9. Add remote evidence to the release packet and keep the PR draft while its
   documented source, attribution, evaluation, security and production gates
   remain open. Passing remote CI and a preview does not complete those gates.

## Recovery and approval boundaries

If a push is rejected or its result is uncertain, read the remote ref and
deployment list before retrying. If CI fails, preserve the failure, fix locally,
run relevant checks and bind the next proposed push to its new SHA. Keep the PR
draft. Do not weaken guards, force-push or delete a remote branch to recover.

If the preview fails, inspect safe build status/output and preserve its identity.
No promotion is needed for validation. If a deployment unexpectedly targets
production or changes the public alias, stop and record the observed identity.
Prepare an explicit rollback decision naming baseline
`dpl_HqsZGeeJAKYML6H8X5fuj1cj5iXb`, its main SHA and affected domains. A rollback,
deployment cancellation, environment change or alias operation requires its own
applicable approval. No automatic production recovery mutation is proposed.

This proposal covers source publication, a draft review and bounded remote
validation only. Paid requests, shared SQL/grant changes, caption ingestion,
browser-cookie access, workflow dispatch/schedule edits, merge, manual deployment,
production promotion and branch deletion retain their separate approval gates.
The overall release decision and current evidence remain in
[RELEASE_PACKET.md](RELEASE_PACKET.md) and [OPERATIONS.md](OPERATIONS.md).
