# A private click-through on Render

This file is only on the test branch. It is not part of the fix that goes upstream.

The test site is one free web service. It serves the public pages, the read API, Find Artists & Studios, and Glowtbook. The data is the invented demo (made-up studios and artists). It is recreated every time the service starts.

## Open it

Sign in to [Render](https://dashboard.render.com), then open this link:

https://render.com/deploy?repo=https://github.com/jasonrobertbauer-create/glass-database/tree/cursor/render-test-4acf

Render shows one free web service named `glass-database-test`. You do not have to type any settings. Choose the free plan if it asks, then deploy.

The first build takes a few minutes. When it finishes, the dashboard shows an address ending in `onrender.com`.

If the button does not open the repo, use the dashboard instead: **New → Blueprint**, connect GitHub, pick `jasonrobertbauer-create/glass-database`, branch `cursor/render-test-4acf`, and apply `render.yaml`.

## What you do not have to fill in

Nothing is required. These are already set:

| Name | What it does |
| --- | --- |
| `PYTHON_VERSION` | Python 3.12.11 |
| `GLASSDB_PROXY_APPS` | Serves the directory and Glowtbook through the one public address |
| `ROOT_PATH` | Keeps the API docs at `/api/docs` |
| `GLASSDB_MODERATION` | New submissions wait for review (there is no admin page on this test site) |
| `GLASSDB_SESSION_SECRET` | Render invents this. Leave it. |

`PUBLIC_BASE_URL` is optional. Leave it empty and the site uses the `onrender.com` address Render assigns.

## Optional, only if you want them later

Leave these unset for the click-through. The site works without them.

| Name | If you set it |
| --- | --- |
| `GLASSDB_ADMIN_TOKEN` | Unlocks private columns (including the demo ethnicity, gender, and birth year) on the API. Leave blank so the public pages stay public-only. |
| Google sign-in (`client_id`, `client_secret` in a secrets file) | Not wired on this test site. Without it, sign-in says it is not set up, and the fingerprint pages still open. |
| `DISCORD_WEBHOOK_URL` | Would post new submissions to Discord. Not needed. |
| `GLASSDB_DEV_LOGIN` | Do not set this on the public test address. It would let anyone pretend to be signed in. |

## Cost

The service is on Render's **free** plan. The expected charge for running it is **$0**. Render's free plan includes a monthly allowance of build minutes and outbound traffic. This blueprint does not add a database or a disk, which are the parts that can cost money.

## Limits

- After about 15 minutes with no visitors, the free service goes to sleep. The next visit takes about a minute while it wakes up. Render shows a loading page during that time.
- Anything you add (a note, a vote, an upload) is forgotten when the service sleeps, restarts, or is deployed again. The invented demo comes back on its own.
- The admin console is not running. On a public link it would be open to anyone.
- The fingerprint camera page opens, and sign-in shows that it is not set up. Measuring a piece on the printed mat, and signing a Content Credential, need extra software that is not installed here, so those two steps do not run on the test site. The rest of the page still works.
- This is a place to click through the edits. It is not the live site, and it should not be given real personal data.
