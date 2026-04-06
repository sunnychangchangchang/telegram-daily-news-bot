import html
import os
import re
import difflib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

import feedparser
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

CLIENT = Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL = "claude-sonnet-4-20250514"
ET = ZoneInfo("America/New_York")

RSS_FEEDS = {
    "macro": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "http://feeds.bbci.co.uk/news/business/rss.xml",
        "https://news.google.com/rss/search?q=federal+reserve+interest+rate+inflation&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=global+economy+macro+GDP+CPI&hl=en-US&gl=US&ceid=US:en",
    ],
    "trump": [
        "https://news.google.com/rss/search?q=trump+tariff+policy&hl=en-US&gl=US&ceid=US:en",
    ],
    "markets": [
        "https://news.google.com/rss/search?q=stock+market+SP500+nasdaq&hl=en-US&gl=US&ceid=US:en",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    ],
    "ai": [
        "https://news.google.com/rss/search?q=AI+model+artificial+intelligence+release&hl=en-US&gl=US&ceid=US:en",
        "https://www.theverge.com/rss/index.xml",
        "https://techcrunch.com/feed/",
    ],
}

TOPIC_KEYWORDS = {
    "macro": ["fed", "federal reserve", "interest rate", "cpi", "gdp", "inflation",
              "economy", "macro", "central bank", "recession", "monetary", "fiscal",
              "employment", "jobs", "unemployment", "treasury", "bond", "yield"],
    "trump": ["trump", "tariff", "trade war", "executive order", "white house",
              "administration", "policy", "sanction", "diplomat", "foreign"],
    "markets": ["s&p", "sp500", "nasdaq", "dow", "stock", "market", "equity",
                "nikkei", "hang seng", "shanghai", "ftse", "dax", "rally", "selloff",
                "bull", "bear", "correction", "ipo", "earnings"],
    "ai": ["ai", "artificial intelligence", "llm", "gpt", "claude", "gemini",
           "openai", "anthropic", "google deepmind", "nvidia", "machine learning",
           "model", "chatbot", "generative"],
}

_FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    """Remove HTML tags and unescape HTML entities."""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


_MDV2_ESCAPE = re.compile(r'([_*\[\]()~`>#+=|{}.!-])')
_MDV2_KEEP   = re.compile(r'(\*[^*\n]+\*|\[[^\]\n]+\]\(https?://[^)\n]+\))')


def escape_mdv2(text: str) -> str:
    """
    Escape MarkdownV2 special chars throughout, preserving *bold* and [text](url) syntax.
    - Plain text: all special chars escaped
    - Bold *inner*: special chars inside also escaped (Telegram requires this)
    - Link [text](url): link text escaped, URL left as-is
    """
    # Normalise **double-asterisk bold** → *single*
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'*\1*', text)
    parts = _MDV2_KEEP.split(text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            if part.startswith('*') and part.endswith('*'):
                inner = _MDV2_ESCAPE.sub(r"\\\1", part[1:-1])
                result.append(f'*{inner}*')
            else:
                # Link [text](url) — escape text portion, leave URL intact
                m = re.match(r'\[([^\]]+)\]\((https?://[^)]+)\)', part)
                if m:
                    link_text = _MDV2_ESCAPE.sub(r"\\\1", m.group(1))
                    result.append(f'[{link_text}]({m.group(2)})')
                else:
                    result.append(part)
        else:
            result.append(_MDV2_ESCAPE.sub(r"\\\1", part))
    return "".join(result)


def _esc(s: str) -> str:
    """Escape a plain-text string for MarkdownV2 (no formatting preserved)."""
    return _MDV2_ESCAPE.sub(r"\\\1", str(s))


# ── RSS ───────────────────────────────────────────────────────────────────────

def parse_pub_date(entry) -> datetime | None:
    for field in ("published", "updated", "pubDate"):
        val = entry.get(field)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                continue
    return None


def is_recent(dt: datetime | None, hours: int = 12) -> bool:
    if dt is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt >= cutoff


def deduplicate(articles: list[dict], threshold: float = 0.6) -> list[dict]:
    """Remove near-duplicate articles by title similarity."""
    unique = []
    for article in articles:
        title = article["title"].lower()
        is_dup = any(
            difflib.SequenceMatcher(None, title, u["title"].lower()).ratio() > threshold
            for u in unique
        )
        if not is_dup:
            unique.append(article)
    return unique


def is_relevant(title: str, topic: str) -> bool:
    return any(kw in title.lower() for kw in TOPIC_KEYWORDS[topic])


def fetch_news() -> dict[str, list[dict]]:
    """Fetch RSS feeds, deduplicating both within and across topics."""
    results: dict[str, list[dict]] = {t: [] for t in RSS_FEEDS}
    global_seen_urls: set[str] = set()  # prevents same article appearing in two topics

    for topic, urls in RSS_FEEDS.items():
        candidates = []
        seen_urls: set[str] = set()

        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if link in seen_urls or link in global_seen_urls:
                        continue
                    seen_urls.add(link)

                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    dt = parse_pub_date(entry)
                    if not is_recent(dt):
                        continue

                    general_feeds = [
                        "reuters.com/reuters/businessNews",
                        "cnbc.com/id/100003114",
                        "bbci.co.uk/news/business",
                        "theverge.com/rss",
                        "techcrunch.com/feed",
                    ]
                    is_general = any(g in url for g in general_feeds)
                    if is_general and not is_relevant(title, topic):
                        continue

                    # Keep summary only if it adds information beyond the title
                    raw = entry.get("summary") or entry.get("description", "")
                    if raw:
                        cleaned = strip_html(raw)[:200]
                        similarity = difflib.SequenceMatcher(
                            None, cleaned.lower(), title.lower()
                        ).ratio()
                        summary = cleaned if len(cleaned) >= 30 and similarity < 0.8 else ""
                    else:
                        summary = ""

                    candidates.append({
                        "title": title,
                        "link": link,
                        "source": feed.feed.get("title", url),
                        "published": dt.isoformat() if dt else "",
                        "summary": summary,
                    })
            except Exception as e:
                print(f"[WARN] Failed to fetch {url}: {e}")

        candidates.sort(key=lambda x: x["published"], reverse=True)
        deduped = deduplicate(candidates)[:5]
        results[topic] = deduped
        global_seen_urls.update(a["link"] for a in deduped)
        print(f"[INFO] {topic}: {len(results[topic])} articles")

    return results


def build_news_block(topic: str, articles: list[dict]) -> str:
    if not articles:
        return f"No recent news for {topic}."
    lines = []
    for i, a in enumerate(articles, 1):
        summary_line = f"\n   Summary: {a['summary']}" if a.get("summary") else ""
        lines.append(
            f"{i}. {a['title']}\n   Source: {a['source']}{summary_line}\n   URL: {a['link']}"
        )
    return "\n\n".join(lines)


# ── Economic calendar ─────────────────────────────────────────────────────────

def _parse_ff_date(date_str: str) -> datetime:
    """Parse ForexFactory date string (handles both -0500 and -05:00 offset formats)."""
    normalized = re.sub(r'([+-])(\d{2})(\d{2})$', r'\1\2:\3', date_str)
    dt = datetime.fromisoformat(normalized)
    return dt.replace(tzinfo=ET) if dt.tzinfo is None else dt.astimezone(ET)


def fetch_calendar() -> list[dict]:
    """Fetch upcoming high-impact USD events within the next 72 hours."""
    now    = datetime.now(ET)
    cutoff = now + timedelta(hours=72)
    events = []

    for url in _FF_URLS:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if not resp.ok:
                print(f"[WARN] Calendar HTTP {resp.status_code} from {url}")
                continue
            for e in resp.json():
                if e.get("country") != "USD":
                    continue
                if e.get("impact") != "High":
                    continue
                if e.get("actual"):  # already released
                    continue
                try:
                    dt = _parse_ff_date(e["date"])
                except Exception:
                    continue
                if dt <= now or dt > cutoff:
                    continue
                events.append({**e, "_dt": dt})
        except Exception as ex:
            print(f"[WARN] Calendar fetch failed ({url}): {ex}")

    events.sort(key=lambda x: x["_dt"])
    return events[:5]


def format_calendar_section(events: list[dict]) -> str:
    """Build a MarkdownV2 calendar section to append to the main message."""
    if not events:
        return ""

    lines = ["\n⚠️ Upcoming Key Events"]
    for e in events:
        dt: datetime = e["_dt"]
        date_part = _esc(dt.strftime("%m/%d"))
        weekday   = _esc(dt.strftime("%a"))
        time_part = _esc(dt.strftime("%H:%M"))
        name      = _esc(e.get("title", ""))
        forecast  = _esc(e.get("forecast") or "TBD")
        previous  = _esc(e.get("previous") or "—")

        lines.append(
            f"・{date_part} \\({weekday}\\) {time_part} ET\n"
            f"  *{name}*\n"
            f"  Forecast {forecast}  Prev {previous}"
        )

    return "\n".join(lines)


# ── Claude summarisation ──────────────────────────────────────────────────────

def summarize(news: dict[str, list[dict]], edition: str, date_str: str) -> str:
    """Call Claude to produce a single English market briefing message."""
    macro_block   = build_news_block("macro",   news["macro"])
    trump_block   = build_news_block("trump",   news["trump"])
    markets_block = build_news_block("markets", news["markets"])
    ai_block      = build_news_block("ai",      news["ai"])

    edition_icon = "🌅 Morning" if edition == "morning" else "🌙 Evening"

    prompt = f"""You are a professional financial news analyst. Write all content in English.
Today is {date_str} ET, edition: {edition_icon}.

Below are RSS news articles grouped by topic. Produce a single briefing message in the specified format.

---
Macro & Fed:
{macro_block}

Trump & Policy:
{trump_block}

Markets:
{markets_block}

AI & Tech:
{ai_block}
---

### Format rules (Telegram MarkdownV2):
- Bold: single asterisk *text* (e.g. *Macro & Fed*, *$NVDA*)
- Hyperlinks: [Source: Brief title](full URL)
- Plain text: no extra symbols, no HTML tags

### Message format:

🌐 Daily Market Briefing
📅 {date_str}  |  {edition_icon}

📊 *Macro & Fed*
Integrate background, market reaction, and forward implications into one fluent paragraph (max 3 sentences).
▸ [Source: Brief title](full URL)
Watchlist: sector name · sector name　$TICKER1  $TICKER2  $TICKER3

🇺🇸 *Trump & Policy*
(same format: paragraph + source link + watchlist)

📈 *Markets*
(same format)

🤖 *AI & Tech*
(same format)

---
Rules:
- Only use URLs provided above — never fabricate links.
- Watchlist: 1-2 sector names, then 2-3 most directly related US tickers.
- If a topic has no articles, write (No recent news) and omit the watchlist line.
- Output the message only — no extra commentary.
"""

    response = CLIENT.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return escape_mdv2(response.content[0].text.strip())


# ── Telegram ──────────────────────────────────────────────────────────────────

def split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split a message into chunks of at most max_len characters, breaking at newlines."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk in split_message(text):
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": chunk,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, json=payload, timeout=30)
        if not resp.ok:
            print(f"[WARN] MarkdownV2 rejected: {resp.text}")
            fallback = {k: v for k, v in payload.items() if k != "parse_mode"}
            resp2 = requests.post(url, json=fallback, timeout=30)
            resp2.raise_for_status()


def send_error(message: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": f"⚠️ Bot Error:\n{message}",
        }, timeout=30)
    except Exception:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    now_et = datetime.now(ET)
    hour = now_et.hour
    edition = "morning" if 6 <= hour < 18 else "evening"
    date_str = now_et.strftime("%B %d, %Y")

    print(f"[INFO] Running {edition} edition — {date_str} ET")

    try:
        news = fetch_news()
    except Exception as e:
        send_error(f"fetch_news() failed: {e}")
        raise

    calendar = fetch_calendar()
    print(f"[INFO] calendar: {len(calendar)} upcoming events")

    try:
        msg = summarize(news, edition, date_str)
    except Exception as e:
        send_error(f"summarize() failed: {e}")
        raise

    cal_section = format_calendar_section(calendar)
    if cal_section:
        msg = msg + "\n" + cal_section

    try:
        send_telegram(msg)
        print("[INFO] Message sent.")
    except Exception as e:
        send_error(f"send_telegram() failed: {e}")
        raise


if __name__ == "__main__":
    main()
