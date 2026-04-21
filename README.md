# Layer-0 News Triage Service

Automated news triage pipeline built around the [Layer-0 skill](./skill/SKILL.md). Pulls headlines from GDELT + Polygon + RSS every 15 minutes during US market hours, runs them through Claude with your framework as the reasoning kernel, and routes the output:

- **Score ≥ 7** → instant push to Telegram
- **Score 4–6** → accumulated in a daily email digest sent at 5:30 pm ET
- **Score < 4** → logged as noise

Runs on GitHub Actions. Nothing to host, nothing to keep running. State persists across runs by being committed back to the repo (dedupe store + digest accumulator).

## Prerequisites

You'll need four accounts/keys. Everything except Anthropic has a free tier that works for this use case.

| Service | Required? | Cost |
|---|---|---|
| [Anthropic API key](https://console.anthropic.com/) | **Yes** | ~$40–115/month at 15-min cadence (Sonnet 4.6 with prompt caching) |
| [Polygon.io](https://polygon.io/) | Optional but recommended | Free tier works with reduced data; $29/mo Starter unlocks full news |
| Telegram bot | **Yes** | Free — see [TELEGRAM_SETUP.md](./TELEGRAM_SETUP.md) |
| SMTP credentials (Gmail app password works) | Only for digest | Free |

## Setup — 10 minutes

### 1. Fork or clone this repo to your GitHub account

It must be your own repo because the service commits state back on each run.

```bash
git clone <this-repo> my-triage
cd my-triage
```

### 2. Customize your portfolio

Open `skill/assets/portfolio_example.json` and edit it to reflect your actual holdings. The `thesis` field matters — phrases like *"legal risk"*, *"credit stress"*, or *"accounting"* trigger Layer 2 overrides that gate bullish news on that ticker. See the skill itself for the full mechanic.

```json
{
  "positions": [
    {
      "ticker": "MPC",
      "position_usd": 18000,
      "cost_basis": 145.20,
      "thesis": "Refining margin capture; Hormuz reopening triggers trim-into-strength"
    },
    ...
  ]
}
```

Rename to `portfolio.json` or leave as `portfolio_example.json` — the reasoning layer reads whichever exists.

### 3. Add repository secrets

In GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Add one secret per key listed below.

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | From console.anthropic.com |
| `POLYGON_API_KEY` | From polygon.io (optional — leave unset if not using) |
| `TELEGRAM_BOT_TOKEN` | From BotFather — see [TELEGRAM_SETUP.md](./TELEGRAM_SETUP.md) |
| `TELEGRAM_CHAT_ID` | From `getUpdates` call |
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | e.g. `587` |
| `SMTP_USER` | Your email address |
| `SMTP_PASSWORD` | Gmail *app password*, not your account password. [Generate one here](https://myaccount.google.com/apppasswords). |
| `DIGEST_TO_EMAIL` | Where the daily digest goes (can be the same as SMTP_USER) |

### 4. Enable workflow permissions

In GitHub: **Settings → Actions → General → Workflow permissions** → select **Read and write permissions**. Required so the workflow can commit `data/state.json` back.

### 5. Test locally (optional but recommended)

Before turning on the cron, verify everything works:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys

# Sanity check: tests all sources and sends a Telegram hello. Does NOT call Claude.
python -m src.main test

# One full run end-to-end:
python -m src.main triage
```

### 6. Push to GitHub and watch it run

```bash
git add -A
git commit -m "Initial setup"
git push
```

The triage workflow runs every 15 minutes Mon–Fri during the 11:00–22:00 UTC window. You can trigger it manually from the Actions tab → Triage → Run workflow. First manual run is a good idea to confirm everything's wired up.

## Customization

### Change the news sources

- **RSS feeds**: edit `RSS_FEEDS` in `src/config.py`. Add, remove, or swap feeds freely.
- **GDELT query**: edit `GDELT_QUERY` in `src/config.py`. The current query covers major geopolitical and macro themes; narrow or broaden as needed. [GDELT DOC API syntax](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/).
- **Polygon**: always pulls the latest 30 minutes of tagged news; nothing to configure.

### Change the cadence

Edit `.github/workflows/triage.yml`:

- Every 5 minutes: `cron: "*/5 11-22 * * 1-5"` (minimum for GitHub Actions cron)
- Every 30 minutes: `cron: "*/30 11-22 * * 1-5"` (halves your Claude cost)
- Hourly: `cron: "0 11-22 * * 1-5"`

### Change the thresholds

Set `RELEVANCE_PUSH_THRESHOLD` and `RELEVANCE_DIGEST_MIN` in the workflow env block. Defaults are 7 and 4 respectively. Raise the push threshold to get fewer pings; raise the digest minimum to filter more aggressively from the daily email.

### Change the model

Set `CLAUDE_MODEL` in the workflow env block. Options:

- `claude-haiku-4-5` — ~$40/mo. Noticeably weaker reasoning on multi-layer confluence.
- `claude-sonnet-4-6` — default. Matches the output quality you reviewed during skill development.
- `claude-opus-4-7` — ~$190/mo. Overkill for routine triage.

### Use the 1-hour prompt cache

At 15-min cadence, a 1-hour cache amortizes the skill content across ~3 calls instead of paying cache-write every run. Set `USE_EXTENDED_CACHE = True` at the top of `src/reasoning.py`. This requires the `extended-cache-ttl-2025-04-11` beta on your Anthropic account — if you hit an error, flip it back to `False`.

## Troubleshooting

**The workflow fails with `Missing required env var: ANTHROPIC_API_KEY`.**
Secret isn't set in GitHub. Settings → Secrets → verify it's there. Secret names are case-sensitive.

**Workflow runs but no Telegram alerts arrive.**
Most likely: `TELEGRAM_CHAT_ID` is wrong. Run `python -m src.main test` locally to verify. Second most likely: everything scored below 7 — check `data/outputs/` (local run only) for the actual JSON.

**`Failed to parse Claude response as JSON` in logs.**
Rare but not impossible — the model wrapped its reply in a code fence or added a preamble. Check the logged first 500 chars. If it keeps happening, tighten the system prompt in `src/reasoning.py` with an even more explicit "JSON only" instruction.

**`state.json` commit fails with "rejected".**
Two workflow runs tried to push at once. The workflow has a 3-retry rebase loop, but if it gives up, the next successful run will re-learn the dedup state (at the cost of a few duplicate headlines that run).

**GDELT returns zero items.**
GDELT sometimes rate-limits or returns empty windows. Rarely a problem — the other sources pick up the slack. Persistent zeros across multiple runs → check the query syntax.

**Polygon returns zero items.**
On the free tier, news endpoints are limited. Either upgrade to Starter, or leave `POLYGON_API_KEY` unset and rely on GDELT + RSS.

## Costs at the default cadence

At 15-min cadence × 11-hour daily window × 5 weekdays = ~220 calls/week ≈ 950 calls/month.

| Model | Without caching | With 5-min cache | With 1-hour cache |
|---|---|---|---|
| Haiku 4.5 | ~$55 | ~$35 | ~$20 |
| Sonnet 4.6 | ~$170 | ~$110 | ~$65 |
| Opus 4.7 | ~$280 | ~$180 | ~$110 |

Default is Sonnet 4.6 with 5-min cache. Flip to 1-hour cache to cut ~40% off.

## Extending

This is a starter service. Natural next steps:

- **Pre-filter with Haiku before Sonnet.** Run a cheap Haiku pass that marks obvious noise, then send only the survivors to Sonnet. Cuts cost ~40% without meaningfully hurting quality.
- **Add more notification tiers.** Score ≥ 9 could trigger an SMS via Twilio, while ≥ 7 stays on Telegram.
- **Persist triage outputs to a cloud store.** The current setup writes `data/outputs/*.json` locally only. Shipping them to S3/R2 lets you build a history dashboard.
- **Multi-asset pipelines.** The skill is equity-focused today. A second skill covering rates or FX could run on the same infrastructure with a different system prompt.
- **Paper-trading integration.** Feed the `affected_tickers` + `stance` output into a paper-trade API to backtest the pipeline's signals before sizing them live.

## Architecture

```
News sources (GDELT, Polygon, RSS)
         │
         ▼
  Orchestrator (src/main.py)
  ├─ Fetch (parallel per source, failures isolated)
  ├─ Dedupe (content-hash against data/state.json)
  └─ Batch
         │
         ▼
  Claude API call (src/reasoning.py)
  ├─ System prompt: SKILL.md + references + portfolio.json (cached)
  └─ User prompt: the batch as JSON
         │
         ▼
  Router (src/router.py)
  ├─ score ≥ 7 → Telegram (src/notifiers/telegram.py)
  └─ 4 ≤ score < 7 → daily digest accumulator (src/notifiers/email_digest.py)
         │
         ▼
  State persistence (src/state.py)
  └─ data/state.json committed back to the repo
```

Every stage is independently testable. `python -m src.main test` runs all of them except the Claude call.

## License and disclaimers

This is decision-support tooling, not financial advice. The skill applies *your* framework to news — it does not invent recommendations. The suggested stances (probe / full / reduce / stand_down) are outputs of your framework's rules, not endorsements. Review every alert before acting.
