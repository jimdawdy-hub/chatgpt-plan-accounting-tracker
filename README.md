# ChatGPT Plan Accounting Tracker

A local dashboard for reconciling Codex usage telemetry, ChatGPT plan/workspace credits, and exported billable credit events.

This is modeled after the Claude Usage Tracker, but OpenAI/Codex accounting needs an extra reconciliation layer because the exports are not one single ledger:

- Codex daily JSON exports show internal sessions, turns, models, token counts, and internal Codex credits.
- Workspace usage JSON shows daily totals with model and client breakdowns.
- ChatGPT credit usage CSVs show visible billable credit events such as `chat.completion.5.pro`.
- Purchased credits or workspace allocations may be consumed by categories that are not obvious in a single export.

## Installation For Non-Technical Users

This app runs locally on your own computer. It does not send your data anywhere.

### Step 1: Install Python

Windows:

1. Go to https://www.python.org/downloads/
2. Download the latest Python 3 installer.
3. Run the installer.
4. On the first installer screen, check **Add Python to PATH**.
5. Click **Install Now**.

Mac:

1. Go to https://www.python.org/downloads/
2. Download the latest Python 3 installer for macOS.
3. Open the downloaded `.pkg` file and follow the prompts.

Linux:

Most Linux systems already include Python. If not, use your system's app store or package manager. On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

### Step 2: Download This App

If you are comfortable with Git:

```bash
git clone https://github.com/jimdawdy-hub/chatgpt-plan-accounting-tracker.git
cd chatgpt-plan-accounting-tracker
```

If you are not comfortable with Git:

1. Open the GitHub page for this project.
2. Click the green **Code** button.
3. Click **Download ZIP**.
4. Unzip the downloaded file.
5. Open the unzipped folder.

### Step 3: Open a Terminal in the App Folder

Windows:

1. Open the app folder in File Explorer.
2. Click the address bar.
3. Type `cmd` and press Enter.

Mac:

1. Open the app folder in Finder.
2. Right-click the folder.
3. Choose **New Terminal at Folder**. If you do not see that option, open Terminal and drag the folder into the Terminal window after typing `cd `.

Linux:

1. Open the app folder in your file manager.
2. Right-click inside the folder.
3. Choose **Open in Terminal**.

### Step 4: Install the App Requirements

Windows:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Mac/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Run the App

Windows:

```bat
python app.py
```

Mac/Linux:

```bash
python3 app.py
```

Then open this address in your browser:

http://127.0.0.1:5050

Leave the terminal window open while you use the dashboard. To stop the app, click the terminal window and press `Ctrl+C`.

## Quick Run For Technical Users

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

On startup and when you click **Sync Reports**, the app scans:

- `./data`
- `~/Downloads`

It currently recognizes:

- `codex-daily-sessions-messages-counts-*.json`
- `codex-daily-workspace-usage-counts-*.json`
- `*Credit Usage Report*.csv`
- any CSV with `date_partition`, `usage_type`, `usage_credits`, and `usage_quantity` columns

## Gathering Data

Extra credit usage, meaning purchased credits outside included plan usage, can be downloaded from:

https://chatgpt.com/admin/billing?tab=plan

Use:

```text
Credit Balance -> three-dot menu -> Download Usage Data
```

Leave the downloaded CSV in `~/Downloads`, then click **Sync Reports** in the dashboard. The importer scans `~/Downloads` automatically.

Codex usage reports can be downloaded from:

https://chatgpt.com/codex/cloud/settings/analytics

Use:

```text
Workspace view -> Export -> Usage report
Workspace view -> Export -> Message Count report
User view -> Export -> Usage report
User view -> Export -> Message Count report
```

Leave the downloaded JSON files in `~/Downloads`, then click **Sync Reports**. The importer currently recognizes the daily workspace and daily user/session report shapes from these exports.

## Methodology

The tracker keeps internal Codex telemetry and visible billable credit events separate. That is intentional. A large internal Codex-credit number does not necessarily mean the same number of purchased or billable credits was consumed.

The dashboard reports:

- internal Codex credits from JSON exports
- `on_demand_credits` from JSON exports
- visible billable credits from CSV exports
- the gap between internal telemetry credits and visible billable events
- selected-plan net value: internal credit-equivalent usage value minus plan base cost minus visible extra credit cost
- model mix and token mix
- client attribution, including `CODEX_UNKNOWN_DEFAULT`

## Codex Rate Card

Token-rate estimates are based on OpenAI's Codex rate card:

https://help.openai.com/en/articles/20001106-codex-rate-card#codex-rate-card-token-based-pricing

As fetched on May 17, 2026, the token-based Codex rate card lists credits per 1M input, cached input, and output tokens for models including GPT-5.5, GPT-5.4, GPT-5.4-Mini, GPT-5.3-Codex, and GPT-5.2.

The rate-card estimate is useful as a cross-check against the `credits` field in the Codex exports. It is not an invoice.

## Direct API Equivalent

The Models section also estimates what the same token buckets would cost at standard OpenAI API pricing, using uncached input, cached input, and output rates separately.

Current standard API rates used:

| Model | Input / 1M | Cached input / 1M | Output / 1M |
|-------|------------|-------------------|-------------|
| GPT-5.5 | $5.00 | $0.50 | $30.00 |
| GPT-5.4 | $2.50 | $0.25 | $15.00 |
| GPT-5.4 Mini | $0.75 | $0.075 | $4.50 |

Sources:

- https://developers.openai.com/api/docs/models/compare
- https://developers.openai.com/api/docs/models/gpt-5.4-mini

The dashboard projects direct API equivalent forward 30 days from the entered plan start date. It compares that projected API token cost against the selected monthly plan cost. For per-model rows, the selected plan cost is allocated proportionally by each model's share of projected API spend, so the per-model savings rows add up to the overall selected-plan savings estimate.

## Plan Scope

The app is intended to support:

- ChatGPT Free
- ChatGPT Go
- ChatGPT Plus
- ChatGPT Pro
- Business Codex
- ChatGPT Business
- ChatGPT Enterprise

Business and Enterprise workspaces may have allocations, purchased credits, admin controls, or contract terms that change what appears as billable usage.

## Base Plan Rates

Base plan rates are sourced from the ChatGPT pricing page:

https://chatgpt.com/pricing/

Current USD defaults used by the tracker:

| Plan | Base rate used in math | Notes |
|------|------------------------|-------|
| Free | $0/month | Limited Codex access |
| Go | $8/month | Regional availability and local price may vary |
| Plus | $20/month | Expanded Codex usage |
| Pro | $200/month | Pro reasoning and maximum Codex tasks |
| Business Codex | $0 fixed seat fee + usage | No fixed seat fee; pay as you go based on usage |
| Business ChatGPT & Codex | $25/seat/month | 2-seat minimum; default math uses 2 seats = $50/month |
| Enterprise | Custom | Contract pricing and terms |

The dashboard adds visible billable credits from the credit usage CSV to these base rates as a simple reconciliation view. This is plan accounting, not a formal invoice.

The **Net Plan Value** card uses the selected plan, seat count, and plan start date at the top of the dashboard. It assumes the observed purchase ratio of `$20 = 500 credits`, or `$0.04/credit`, then computes:

```text
internal Codex credits value - selected plan base cost - visible billable credits value
```

For Enterprise, the value is left as custom because the base price is contract-specific.

The **30-Day Projection** uses usage currently available since the entered plan start date, computes the current daily credit pace, and projects that forward to 30 days:

```text
(credits since start date / elapsed days) * 30 * $0.04
```

That projected usage value is compared against the selected plan's monthly base cost. For Business, the base cost is:

```text
max(entered seats, 2) * $25
```

The app does not project savings for other plans by default, because lower tiers may not permit the same Codex workload. Other plans are shown as base-cost context only unless their actual quota/credit allowance can be imported.

## What We Know About Codex Limits

OpenAI's public docs currently describe Codex limits qualitatively rather than publishing fixed numeric caps for every plan. The app therefore records known policy instead of pretending to know exact quotas:

| Plan | Known Codex treatment |
|------|-----------------------|
| Free | Temporary limited Codex access; prompted to upgrade for Codex rather than add credits |
| Go | Temporary limited Codex access; prompted to upgrade for Codex rather than add credits |
| Plus | Codex included; included usage is used first, then eligible users can buy credits |
| Pro | Codex included with higher limits than Plus; eligible users can buy credits |
| Business Codex | No fixed seat fee; pay as you go based on Codex usage |
| Business ChatGPT & Codex | Workspace Codex access with credits/spend controls and admin settings |
| Enterprise | Contract/workspace-specific, with possible legacy rate-card treatment for a small subset |

Sources:

- https://help.openai.com/en/articles/11369540-codex-in-chatgpt-faq
- https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-freegopluspro
- https://help.openai.com/en/articles/20001106-codex-rate-card#codex-rate-card-token-based-pricing
