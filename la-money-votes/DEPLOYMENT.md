# Deploying `la-money-votes` to Vercel (subdomain only)

This document covers deploying the **`la-money-votes`** site to Vercel on a
**subdomain** (e.g. `politician.akhilvasvani.com` or
`civic.akhilvasvani.com`) so it can host the "Ask about this official"
serverless search feature (`api/ask-official.js`), which needs a Node.js
runtime and therefore can't run on GitHub Pages (static-only).

**This must never touch the root domain.** `akhilvasvani.com` and its
existing GitHub Pages deployment (`.github/workflows/deploy-pages.yml`,
triggered on every push to `main`) are completely independent of this Vercel
project and are not modified by anything below. Vercel is an *additional*
place this site is also deployed to, on its own subdomain, not a
replacement.

## 1. Is a build step required?

No. `la-money-votes/` is a static site (`index.html`, `official.html`,
`css/`, `js/`, `data/`) plus one serverless function (`api/ask-official.js`).
There is nothing to compile or bundle — Vercel can deploy the directory as-is
with:

- **Build Command:** _(leave empty / none)_
- **Output Directory:** _(leave default — the root of this directory)_
- **Install Command:** _(leave empty / none — the function has no npm
  dependencies; it only uses Node's built-in `fetch`)_

## 2. Import the repo into Vercel

1. Go to [vercel.com/new](https://vercel.com/new) and sign in.
2. Click **Import Project** and select the `akhilvasvani/check-your-politician`
   GitHub repository (grant Vercel access to it if prompted).
3. On the "Configure Project" screen:
   - **Framework Preset:** `Other` (no framework — plain static + one
     serverless function).
   - **Root Directory:** click "Edit" and set it to `la-money-votes`. This is
     the important part — it tells Vercel that `la-money-votes/` (not the
     repo root, which also holds unrelated files like `README.md` and
     `LICENSE`) is what gets deployed, and that `la-money-votes/api/*.js`
     is where its serverless functions live.
   - Leave Build/Output/Install commands empty, per step 1.
4. Click **Deploy**. Vercel will give you a `*.vercel.app` preview URL once
   it finishes — confirm `index.html` and an official profile page load
   there before continuing.
5. **Do not merge/promote to a production alias without explicit approval.**
   Use a preview deployment (a branch/PR deployment, not the `main`-tracking
   production deployment) until asked to go further.

## 3. Add the subdomain in Vercel

1. In the Vercel dashboard, open this project → **Settings → Domains**.
2. Enter your chosen subdomain, e.g. `politician.akhilvasvani.com` (anything
   other than the bare `akhilvasvani.com` root — do not add the root domain
   here).
3. Vercel will show you a CNAME target to add at your DNS registrar — it
   looks like `cname.vercel-dns.com` (Vercel displays the exact value for
   your project; use what it shows you, the value below is the common
   default but always copy the one Vercel gives you).

## 4. Add the CNAME record at your domain registrar

At whichever registrar/DNS provider hosts `akhilvasvani.com`'s DNS (**not**
in this repo, and **not** in GitHub Pages settings), add a new DNS record:

| Field | Value |
| --- | --- |
| Type | `CNAME` |
| Host / Name | the subdomain prefix only, e.g. `politician` (some registrars want just `politician`, others want `politician.akhilvasvani.com` — follow your registrar's own convention) |
| Target / Value | the CNAME value Vercel showed you in step 3, e.g. `cname.vercel-dns.com` |
| TTL | default / automatic is fine |

Do **not** touch any existing record for the root `@`/`akhilvasvani.com`
host or any other existing subdomain — this should be a single new record,
additive only.

DNS propagation can take anywhere from a few minutes to a few hours.
Vercel's Domains page will show the subdomain as "Valid Configuration" once
it detects the record.

## 5. Set `PERPLEXITY_API_KEY` as an environment variable

The Ask-AI feature needs a Perplexity API key **on the server only** — it
must never appear in any committed file or in client-side code.

1. In the Vercel dashboard: project → **Settings → Environment Variables**.
2. Add a new variable:
   - **Key:** `PERPLEXITY_API_KEY`
   - **Value:** your Perplexity API key (from
     [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api))
   - **Environments:** check Production, Preview, and Development as
     needed (at minimum, whichever environment you're testing against).
3. Redeploy (Vercel prompts you to redeploy after adding/changing an
   environment variable — env vars are only picked up by new deployments,
   not the currently-running one).

`api/ask-official.js` reads this via `process.env.PERPLEXITY_API_KEY` at
request time and never returns it in any response.

## 6. Verify

Once deployed and DNS has propagated:

- Visit `https://<your-subdomain>.akhilvasvani.com/` — the citywide map and
  official cards should load, matching what you saw locally.
- Open a council-district profile (e.g. `?id=cd11-official`) and the
  Mayor's profile (`?id=mayor-bass`) — confirm the "Ask about ..." module
  renders between the donor table and the Voting & Proposal Record section,
  and that submitting a test question returns an answer with citations.
- On a narrow (mobile-width) viewport, confirm the floating "Ask AI" button
  appears bottom-right and scrolls to/focuses the module.
- Separately, confirm `https://akhilvasvani.com` (GitHub Pages) still loads
  exactly as before — this deployment should have had zero effect on it.

## What NOT to do here

- Do not add the bare `akhilvasvani.com` (or `www.akhilvasvani.com`) as a
  domain on this Vercel project.
- Do not change GitHub Pages settings, `.github/workflows/deploy-pages.yml`,
  or any existing DNS record for the root domain.
- Do not commit `PERPLEXITY_API_KEY` (or any secret) into this repo, a
  `.env` file, or a Vercel config file that gets committed. Vercel's
  Environment Variables UI (step 5) is the only place it should live.
- Do not merge this feature branch to `main` or promote a Vercel deployment
  to the production alias without explicit approval — keep this on a
  preview/branch deployment until told otherwise.
