# Telegram Finance Bot

A scheduled Telegram bot that delivers daily market briefings to a channel. Powered by Claude AI for news summarisation and ForexFactory for economic calendar data.

> **Subscribe to the live channel: [t.me/sunnydailynews](https://t.me/sunnydailynews)**

## Features

- Fetches and deduplicates real-time news from RSS feeds (Reuters, CNBC, BBC, Google News, The Verge, TechCrunch)
- Summarises each topic into a concise paragraph using Claude API
- Suggests sector watchlist tickers relevant to each news item
- Pulls upcoming high-impact USD economic events (next 72 hours) from ForexFactory
- Two editions per day: morning and evening
- Available in **Chinese** (`main.py`) and **English** (`main_en.py`)

## Output Example

```
🌐 Daily Market Briefing
📅 April 06, 2026  |  🌅 Morning

📊 *Macro & Fed*
One-paragraph summary integrating background, market reaction, and implications.
▸ Reuters: Fed signals rate hold through summer
Watchlist: Bonds · Financials　$TLT  $XLF  $JPM

🇺🇸 *Trump & Policy*
...

📈 *Markets*
...

🤖 *AI & Tech*
...

⚠️ Upcoming Key Events

・04/08 (Tue) 08:30 ET
  *Core CPI (MoM)*
  Forecast 0.3%  Prev 0.4%

・04/10 (Fri) 08:30 ET
  *Nonfarm Payrolls*
  Forecast 185K  Prev 151K
```

## Automated Scheduling (GitHub Actions)

This bot runs automatically via GitHub Actions — no server required.

The workflow (`.github/workflows/bot.yml`) is scheduled at **8:00 AM ET** and **8:00 PM ET** daily. GitHub handles DST by running at both UTC offsets:

| Edition | Summer (EDT) | Winter (EST) |
|---------|-------------|-------------|
| Morning | 12:00 UTC | 13:00 UTC |
| Evening | 00:00 UTC | 01:00 UTC |

To set up automated runs on your own fork:

1. Fork this repo
2. Go to **Settings → Secrets and variables → Actions**
3. Add three secrets:

| Secret | Value |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from `@BotFather` |
| `TELEGRAM_CHANNEL_ID` | Your channel ID (e.g. `@mychannel`) |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

4. Go to **Actions → Daily Market Briefing → Run workflow** to test manually

## Local Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/sunnychangchangchang/telegram-daily-news-bot.git
cd telegram-daily-news-bot
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHANNEL_ID=@your_channel_or_-100xxxxxxxxxx
ANTHROPIC_API_KEY=your_anthropic_api_key
```

**How to get each key:**
- **Telegram Bot Token**: Message `@BotFather` on Telegram → `/newbot`
- **Telegram Channel ID**: Use `@channel_name` for public channels, or forward a message to `@userinfobot` for the `-100xxxxxxxxxx` ID of private channels
- **Anthropic API Key**: [console.anthropic.com](https://console.anthropic.com)

### 3. Run setup (Mac — registers cron jobs)

```bash
bash setup.sh
```

### 4. Manual run

```bash
# Chinese edition
python3 main.py

# English edition
python3 main_en.py
```

## File Structure

| File | Description |
|------|-------------|
| `main.py` | Chinese edition |
| `main_en.py` | English edition |
| `.github/workflows/bot.yml` | GitHub Actions scheduled workflow |
| `setup.sh` | Local cron job setup (Mac) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `.env` | Your private keys — **do not commit** |

## Requirements

- Python 3.10+
- Anthropic API key
- Telegram Bot Token

## Notes

- **Economic calendar** uses an unofficial ForexFactory JSON feed. If unavailable (404/429/timeout), the calendar section is silently skipped and the briefing still sends.
- **MarkdownV2 fallback**: if Telegram rejects the formatted message, it automatically retries as plain text.
- **API cost estimate**: ~3,000–4,000 tokens per run. At 60 runs/month ≈ $0.10–0.20 USD.
