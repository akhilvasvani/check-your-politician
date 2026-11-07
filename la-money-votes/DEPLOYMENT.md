# Deploying Check Your Politician

The deployment target is the Vercel project for
`akhilvasvani/check-your-politician`, with `la-money-votes/` as its root.
The owner's public domain is `lapolitician.akhilvasvani.com`.
November 6 authenticated inspection verified project ID
`prj_I1kOylFB27M1pABXw5luy5pgkjXv` in team `team-politicheck`
(`team_aPlAJHap7jEuwyrs7qWcc9OL`). The public domain maps to READY production
deployment `dpl_HqsZGeeJAKYML6H8X5fuj1cj5iXb`, built from `main` at
`25a51ebe617f5d24c4a7c405a6498c2104f1a2fd`. Both the public domain and
`check-your-politician.vercel.app` are verified, with no branch-specific
domain assignment. The old feature-branch custom-domain assignment is historical.
The connector did not return the configured root directory or production-branch
setting. Confirm those settings and refresh deployment identity before any
approved push, preview creation or promotion.

## Project configuration

Use the Other framework preset and leave Build, Install and Output Directory
settings at their static-project defaults. The project serves HTML, CSS,
JavaScript and JSON, plus Node serverless APIs under `api/`.
The connected project currently specifies Node `24.x`. Completed local tests
used Node 24.22.1; the preserved CI configuration uses Node 22 and has not run
for this local branch. Do not describe Node 22 as the verified Vercel runtime.
Function execution ceilings for the release are in `vercel.json`.
The application uses built-in `fetch` without an npm install step.

Any DNS operation must identify the exact existing record and desired value
from the Vercel project first. The release target is the named subdomain.
Root-domain changes are outside this release's authorization.

## Separate environments

| Setting | Development | Preview | Production |
| --- | --- | --- | --- |
| Static pages | Local HTTP server | Exact approved commit | Exact approved release commit |
| Paid APIs | Mocks by default | Disabled until bounded smoke approval | Enabled only after release gates and spending approval |
| Supabase | Disposable database for tests | Explicitly identified read target | Verified production read target |
| Rate limiter | Explicit local memory mode permitted | Durable shared store required | Durable shared store required |
| Credentials | Per-process environment | Vercel Preview scope | Vercel Production scope |

Changing a Vercel environment variable requires a new deployment to affect
running functions. Record only credential presence and environment scope in
release reports. Keep values in the approved secret store.

The November 6 names-only inspection found `SUPABASE_URL` and
`SUPABASE_ANON_KEY` in Preview only. Production has neither name. The durable
limiter's `KV_REST_API_URL`/`KV_REST_API_TOKEN` and `PERPLEXITY_API_KEY` are
configured for Preview and Production. Neither paid-endpoint kill-switch name
is configured. The later owner-approved read confirmed only the non-secret
Preview Supabase URL, identifying project `pwbothxnfjnxkhrcxyvd`. Credential
values/validity and live limiter behavior were not inspected. Production
transcript enablement requires a separately approved
configuration and deployment after the source and database gates pass.

## Server environment

| Variable | Purpose |
| --- | --- |
| `PERPLEXITY_API_KEY` | Server-only Sonar generation and transcript query embeddings |
| `SUPABASE_URL` | Exact verified transcript project URL |
| `SUPABASE_ANON_KEY` | Read credential for transcript and coverage RPCs |
| `KV_REST_API_URL`, `KV_REST_API_TOKEN` | Durable Upstash REST limiter configuration |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | Alternate limiter configuration names |
| `ASK_AI_DISABLED=true` | Disable paid web-answer generation |
| `TRANSCRIPT_SEARCH_DISABLED=true` | Disable paid transcript search |
| `ALLOW_IN_MEMORY_LIMITER=true` | Explicit development-only limiter, refused on Vercel or in production |
| `RATE_LIMIT_MAX_REQUESTS` | Ask-AI requests per client in its window, default 5 |
| `RATE_LIMIT_WINDOW_SECONDS` | Ask-AI window, default 600 seconds |
| `TRANSCRIPT_RATE_LIMIT_PER_MIN` | Per-client transcript minute ceiling, default 10 |
| `TRANSCRIPT_RATE_LIMIT_PER_HOUR` | Per-client transcript hourly ceiling, default 60 |

Both paid surfaces also share an aggregate client ceiling. Confirm current
values in `api/_lib/request-safety.js` and the [operations runbook](release/OPERATIONS.md)
before approval. The read APIs require the intended read credential.
`SUPABASE_SERVICE_ROLE_KEY` belongs only in an approved ingestion environment.

On Vercel the limiter reads `x-vercel-forwarded-for` when `VERCEL=1`.
Verify the deployment ingress and header replacement behavior before claiming
spoof-resistant rate limiting. Other hosts use the socket peer and require a
separate ingress review. A configured durable store still needs approved
end-to-end verification, including its outage behavior.

## Review and release

1. Record project ID, deployment ID, commit SHA, branch and alias mapping.
2. Confirm offline suites, disposable PostgreSQL/pgvector tests, corpus coverage,
   relevance evaluation and independent speaker attribution have passed.
3. Review exact environment scopes, durable limits, provider spending caps and
   the previous known-good deployment. Use disabled paid surfaces until an
   approved paid smoke test is ready.
4. Obtain approval for the exact push/PR/preview operation. Record its resulting
   preview URL and verify that it serves the reviewed SHA.
5. Test the homepage and all 16 profiles at desktop and 390px, including source
   links, donor controls, public-action scope, freshness failure, transcript
   partial failure, keyboard access and floating-button clearance.
6. Obtain explicit approval for the exact merge/deployment/promotion action,
   naming the target project, commit, alias, side effects and rollback target.
7. After approval, verify deployed identity, assets/data and static profiles.
   Run paid endpoint smoke only within the separately approved call budget.

An ordinary local static server cannot execute `/api/*`. Use it for static
and mocked browser checks, and label those results accordingly. Local mocks
and prior GitHub checks do not establish current preview or production behavior.

## Recovery

Record the last verified deployment ID and SHA before promotion. A proposed
rollback must specify the exact deployment and alias action and receive the
applicable approval. Provider failures can be contained by the paid-surface
kill switches through an approved environment update and redeployment.
Static profiles remain usable during paid-provider outages.

Finance snapshot recovery uses the publication journal described in
[CONTRACT.md](CONTRACT.md). Transcript replacement recovery requires the
approved cohort backup and exact model/version scope described in
[OPERATIONS.md](release/OPERATIONS.md).
