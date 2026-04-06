# Telegram Finance Bot

A scheduled Telegram bot that delivers daily market briefings to a channel. Powered by Claude AI for news summarisation and ForexFactory for economic calendar data.

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
```

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/telegram-bot.git
cd telegram-bot
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
- **Telegram Channel ID**: Add your bot as admin to a channel. Use `@channel_name` for public channels, or forward a message to `@userinfobot` for the `-100xxxxxxxxxx` ID of private channels
- **Anthropic API Key**: [console.anthropic.com](https://console.anthropic.com)

### 3. Run setup

```bash
bash setup.sh
```

Installs Python dependencies, verifies `.env`, and registers cron jobs at **11:00 AM ET** and **11:00 PM ET**.

## Manual Run

```bash
# Chinese edition
python3 main.py

# English edition
python3 main_en.py
```

Expected output:
```
[INFO] Running morning edition — April 06, 2026 ET
[INFO] macro: 5 articles
[INFO] trump: 4 articles
[INFO] markets: 5 articles
[INFO] ai: 5 articles
[INFO] calendar: 2 upcoming events
[INFO] Message sent.
```

## View Logs

```bash
tail -f bot.log
```

## File Structure

| File | Description |
|------|-------------|
| `main.py` | Chinese edition |
| `main_en.py` | English edition |
| `setup.sh` | Installs dependencies and registers cron jobs |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `.env` | Your private keys — **do not commit** |
| `bot.log` | Runtime log (auto-created) |

## Requirements

- Python 3.10+
- Anthropic API key
- Telegram Bot Token

## Notes

- **Economic calendar** uses an unofficial ForexFactory JSON feed. If unavailable (404/429/timeout), the calendar section is silently skipped and the briefing still sends.
- **MarkdownV2 fallback**: if Telegram rejects the formatted message, it automatically retries as plain text.
- **Cron requires the machine to be on.** For always-on scheduling, deploy to a VPS or use GitHub Actions.
- **API cost estimate**: ~3,000–4,000 tokens per run. At 60 runs/month ≈ $0.10–0.20 USD.
