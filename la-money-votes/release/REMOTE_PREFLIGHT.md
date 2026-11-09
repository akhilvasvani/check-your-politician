# Remote preflight — November 8, 2026

**Ready for one precise approval request; no push, PR or deployment is authorized yet.**
The owner supplied the previously missing dashboard settings. They are recorded
below as owner-reported screenshot values, not a new authenticated connector read.
This updates the existing record; no new review packet is generated.

## Exact settings and target

| Setting | Supplied value |
| --- | --- |
| Production branch | `main` |
| Preview branch tracking | Enabled for all unassigned branches |
| Preview custom domains | None shown |
| Custom environments | Zero |
| Framework | Other |
| Root directory | `la-money-votes` |
| Displayed build/install/development command and output overrides | All off |
| Include outside-root files | Enabled |
| Skip unchanged-root/dependency deployments | Enabled |
| Ignored Build Step | Automatic |
| Node | `24.x` |

Vercel target remains project `prj_I1kOylFB27M1pABXw5luy5pgkjXv`
(`check-your-politician`), team `team_aPlAJHap7jEuwyrs7qWcc9OL`
(`team-politicheck`). `release/weekend-2026-11-08` is an unassigned non-production
branch, so a Git push/PR can automatically create a **Preview** build/deployment.
Automatic skip behavior can suppress a build; it is not a promise of no deployment.
The release diff changes the application root. Draft PR status does not disable
Preview creation. Existing production aliases are not intended to move; Preview
may receive generated branch/deployment URLs, with no Preview custom domain shown.

**Preview shares Supabase `pwbothxnfjnxkhrcxyvd`**, organization `la-politician`,
`us-west-2`. The narrowly approved November 7 Preview `SUPABASE_URL` read established
that hostname with no branch-specific override. No environment value was reread
or changed in this update. Preview has existing provider/limiter variable names;
valid paid endpoints remain in the deployed source but are excluded from initial
validation. No assurance about unrelated clients' activity or cost is implied.

## Current source and remote preconditions

Source inspection started at full local HEAD
`9903a16636576b8bceac3d93343e49d2170377e1` on
`release/weekend-2026-11-08`. The new adjudication, cancellation receipts and this
settings reconciliation will produce a documentation-only successor. The final
full HEAD is bound in the approval request after that commit; **9e4507f is not
its target**. Any subsequent edit invalidates that binding.

Fresh GitHub reads confirmed:

- Base `main`: `25a51ebe617f5d24c4a7c405a6498c2104f1a2fd`, protected=true;
  it remains an ancestor of the local branch.
- No matching `refs/heads/release/weekend-2026-11-08` remote ref.
- No PR in any state for this repository's release head and main base.
- No Git remote is configured locally; use the explicit repository URL.

Full branch-protection administration details remain inaccessible; a branch
summary is not permission to bypass enforcement. This action does not merge.
Recheck exact local HEAD, clean tree, remote base/ref/PR immediately before an
approved write. Stop on drift or uncertain results; do not force-push or silently
rebase, amend, create duplicate PRs, redeploy or dispatch jobs.

## Build/install and runtime reconciliation

The only tracked Vercel configuration is `la-money-votes/vercel.json`. It sets
four function duration limits (30s Ask-AI/search/public-comment, 10s coverage).
There is no tracked `vercel.ts`/other Vercel config, deployment-enable/branch rule,
build/install/output/ignore command, cron, rewrite, or function-install override.
There is no tracked package.json, package lock, workspace/lifecycle hook,
Dockerfile/Procfile, middleware, symlink or submodule. No public/ output directory
exists under the app root. Node API imports use local modules/JSON and built-ins.

With Other, all displayed command overrides off and no package build/install
scripts, the reviewed source/configuration has **no build/install invocation of
ingestion, migrations or paid providers**. The platform packages static assets
and Node functions; its own installation/packaging activity may download platform
dependencies and emit logs. Other defaults to public/ if present, otherwise the
project root. Outside-root access permits build dependencies; it does not execute
standalone Python/SQL automatically. Ignored local work/tooling is untracked and
will not be part of the proposed Git push.
[Build configuration](https://vercel.com/docs/builds/configure-a-build),
[Git configuration](https://vercel.com/docs/project-configuration/git-configuration).

Module source inspection found no ingestion, migration, provider or other network
call at initialization. Network calls are inside request handlers/helpers.
Loading a profile can automatically GET transcript coverage: a read RPC plus
request logging, with no embedding/limiter write. Valid transcript-search and
Ask-AI requests can write shared limiter counters and call paid providers, so
those paths are explicitly excluded. Installing B is a separate SQL action;
repository SQL files and the standalone ingestion adapter are not build hooks.

## Expected remote actions and validation boundary

One normal, non-force push of the final approved SHA to
`https://github.com/akhilvasvani/check-your-politician.git`, ref
`refs/heads/release/weekend-2026-11-08`, then one draft PR to `main`,
`maintainer_can_modify=false`, using [the prepared draft](REMOTE_PR_DRAFT.md).
The proposed title is **Integrate transcript evidence and release safeguards**.

| Trigger | Expected behavior |
| --- | --- |
| Release push | Git source publication and possible automatic Vercel Preview; CI's push filter is main only |
| Matching draft PR opened/synchronized/reopened | `la-money-votes CI / test` and `Guard non-goals / guard`; draft does not suppress them |
| CI/guard | Offline tests, schema checks, dry build, frozen-path guard; runner/action downloads, logs, checks/statuses, build-report artifact |
| Vercel Git integration | Possible Preview build/deployment, generated URLs, build/runtime logs, statuses/comments/notifications |
| Existing refresh workflow | Schedule/manual dispatch only; this push/PR does not dispatch its external data reads/branch/PR writes |

CI uses Python3.11/Node22; Vercel uses Node24.x. CI collects/skips the 18 original
PostgreSQL cases and does not run the local 45-case A/B suite. Recorded 45/45
PG16.14 and45/45 PG17.6 evidence is retained; no full suite rerun is claimed.
Other installed app hooks are not exhaustively inventoried; standard platform
logs/artifacts/statuses/notifications are included in the requested approval.

Initial Preview validation is limited to deployment/source identity and status,
CI/guard outcomes, safe build logs, static homepage/profile/assets and ordinary
read-only coverage requests, plus wrong-method or empty-body API rejection checks
that return before limiter/provider/RPC work. No valid transcript-search,
public-comment search or Ask-AI submission; no paid call, replacement invocation,
ingestion, migration or corpus write. No settings/credential/environment changes,
manual deployment, redeployment, merge, production promotion or workflow dispatch.
Broader validation requires separate approval. Release remains **NO-GO**.
