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

TELEGRAM_BOT_TOKEN = re.sub(r'\s', '', os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

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

_EVENT_NAMES: dict[str, str] = {
    # 就業
    "Nonfarm Payrolls": "非農就業人數",
    "Unemployment Rate": "失業率",
    "Average Hourly Earnings (MoM)": "平均時薪 月增率",
    "Average Hourly Earnings (YoY)": "平均時薪 年增率",
    "ADP Nonfarm Employment Change": "ADP 非農就業變化",
    "JOLTs Job Openings": "職位空缺數",
    "Initial Jobless Claims": "初領失業救濟金",
    "Continuing Jobless Claims": "持續領失業救濟金",
    "Labor Force Participation Rate": "勞動參與率",
    # 通膨
    "CPI (MoM)": "CPI 月增率",
    "CPI (YoY)": "CPI 年增率",
    "Core CPI (MoM)": "核心 CPI 月增率",
    "Core CPI (YoY)": "核心 CPI 年增率",
    "PPI (MoM)": "PPI 月增率",
    "PPI (YoY)": "PPI 年增率",
    "Core PPI (MoM)": "核心 PPI 月增率",
    "Core PPI (YoY)": "核心 PPI 年增率",
    "PCE Price Index (MoM)": "PCE 物價指數 月增率",
    "PCE Price Index (YoY)": "PCE 物價指數 年增率",
    "Core PCE Price Index (MoM)": "核心 PCE 月增率",
    "Core PCE Price Index (YoY)": "核心 PCE 年增率",
    # 聯準會
    "Fed Interest Rate Decision": "聯準會利率決議",
    "FOMC Statement": "FOMC 聲明",
    "FOMC Press Conference": "聯準會記者會",
    "FOMC Meeting Minutes": "FOMC 會議紀要",
    "Fed Chair Powell Speaks": "聯準會主席鮑威爾發言",
    "Fed Monetary Policy Report": "聯準會貨幣政策報告",
    # GDP
    "GDP (QoQ)": "GDP 季增率",
    "GDP (YoY)": "GDP 年增率",
    "GDP Growth Rate QoQ Adv": "GDP 季增率（初估）",
    "GDP Growth Rate QoQ 2nd Est": "GDP 季增率（二次修正）",
    "GDP Growth Rate QoQ Final": "GDP 季增率（終值）",
    "GDP Price Index (QoQ)": "GDP 平減指數",
    # 消費 / 零售
    "Retail Sales (MoM)": "零售銷售 月增率",
    "Core Retail Sales (MoM)": "核心零售銷售 月增率",
    "Personal Income (MoM)": "個人收入 月增率",
    "Personal Spending (MoM)": "個人消費支出 月增率",
    "Consumer Confidence": "消費者信心指數",
    "CB Consumer Confidence": "世界大企業研究所消費者信心",
    "Michigan Consumer Sentiment": "密大消費者信心",
    "Michigan Consumer Sentiment Prel": "密大消費者信心（初估）",
    # 製造業 / PMI
    "ISM Manufacturing PMI": "ISM 製造業 PMI",
    "ISM Services PMI": "ISM 服務業 PMI",
    "S&P Global Manufacturing PMI": "標普全球製造業 PMI",
    "S&P Global Services PMI": "標普全球服務業 PMI",
    "S&P Global Composite PMI": "標普全球綜合 PMI",
    "Philadelphia Fed Manufacturing Index": "費城聯邦製造業指數",
    "Empire State Manufacturing Index": "紐約聯邦製造業指數",
    "Chicago PMI": "芝加哥 PMI",
    "Richmond Fed Manufacturing Index": "里奇蒙聯邦製造業指數",
    "Factory Orders (MoM)": "工廠訂單 月增率",
    "Durable Goods Orders (MoM)": "耐久財訂單 月增率",
    "Core Durable Goods Orders (MoM)": "核心耐久財訂單 月增率",
    "Industrial Production (MoM)": "工業生產 月增率",
    "Capacity Utilization Rate": "產能利用率",
    # 房市
    "Housing Starts": "新屋開工",
    "Building Permits": "建築許可",
    "Existing Home Sales": "成屋銷售",
    "New Home Sales": "新屋銷售",
    "Pending Home Sales (MoM)": "成屋簽約銷售 月增率",
    "Case-Shiller Home Price Index (MoM)": "凱斯席勒房價指數 月增率",
    # 貿易 / 其他
    "Trade Balance": "貿易帳",
    "Current Account": "經常帳",
    "Government Budget Value": "政府預算值",
    "Wholesale Inventories (MoM)": "批發庫存 月增率",
    "Business Inventories (MoM)": "企業庫存 月增率",
    # 公債標售
    "2-Year Note Auction": "2 年期公債標售",
    "3-Year Note Auction": "3 年期公債標售",
    "5-Year Note Auction": "5 年期公債標售",
    "7-Year Note Auction": "7 年期公債標售",
    "10-Year Note Auction": "10 年期公債標售",
    "20-Year Bond Auction": "20 年期公債標售",
    "30-Year Bond Auction": "30 年期公債標售",
}

_WEEKDAY_ZH = ["一", "二", "三", "四", "五", "六", "日"]


# ── Helpers ──────────────────────────────────────────────────────────────────

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
    - Bold *inner*: special chars inside also escaped (Telegram still requires this)
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
    title_lower = title.lower()
    return any(kw in title_lower for kw in TOPIC_KEYWORDS[topic])


def fetch_news() -> dict[str, list[dict]]:
    """Fetch RSS feeds, deduplicating both within and across topics."""
    results: dict[str, list[dict]] = {t: [] for t in RSS_FEEDS}
    global_seen_urls: set[str] = set()  # prevents same article in two topics

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
    """Parse ForexFactory date string (handles -0500 and -05:00 offset formats)."""
    normalized = re.sub(r'([+-])(\d{2})(\d{2})$', r'\1\2:\3', date_str)
    dt = datetime.fromisoformat(normalized)
    return dt.replace(tzinfo=ET) if dt.tzinfo is None else dt.astimezone(ET)


def fetch_calendar() -> list[dict]:
    """Fetch upcoming high-impact USD events in the next 72 hours."""
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
                if e.get("actual"):   # already released
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

    lines = ["\n⚠️ 近三日關鍵事件"]
    for e in events:
        dt: datetime = e["_dt"]
        date_part = _esc(dt.strftime("%m/%d"))
        weekday   = _esc(_WEEKDAY_ZH[dt.weekday()])
        time_part = _esc(dt.strftime("%H:%M"))

        en_name = e.get("title", "")
        zh_name = _EVENT_NAMES.get(en_name, "")
        if zh_name:
            name_line = f"  {_esc(zh_name)}（{_esc(en_name)}）"
        else:
            name_line = f"  {_esc(en_name)}"

        forecast = _esc(e.get("forecast") or "待公布")
        previous = _esc(e.get("previous") or "—")

        lines.append(
            f"・{date_part} \\({weekday}\\) {time_part} ET\n"
            f"{name_line}\n"
            f"  預估 {forecast}　前值 {previous}"
        )

    return "\n".join(lines)


# ── Claude summarisation ──────────────────────────────────────────────────────

def summarize(news: dict[str, list[dict]], edition: str, date_str: str) -> str:
    """Call Claude to produce a single market briefing message."""
    macro_block   = build_news_block("macro",   news["macro"])
    trump_block   = build_news_block("trump",   news["trump"])
    markets_block = build_news_block("markets", news["markets"])
    ai_block      = build_news_block("ai",      news["ai"])

    edition_icon = "🌅 早報" if edition == "morning" else "🌙 晚報"

    prompt = f"""你是一位專業的金融新聞分析師，使用繁體中文撰寫所有內容。今天是 {date_str} ET，版本：{edition_icon}。

以下是依主題分類的 RSS 新聞標題、摘要與連結，請依照指定格式產出一則訊息。

---
總體經濟與聯準會：
{macro_block}

川普與政策：
{trump_block}

市場行情：
{markets_block}

AI 與科技：
{ai_block}
---

### 格式規範（Telegram MarkdownV2）：
- 粗體用單星號：*文字*（例如：*總體經濟與聯準會*、*$NVDA*）
- 超連結用：[來源名稱：繁體中文簡短標題](完整網址)
- 普通文字不加任何符號，不使用 HTML 標籤

### 訊息格式：

🌐 每日市場快報
📅 {date_str}  |  {edition_icon}

📊 *總體經濟與聯準會*
整合背景、市場反應與後續影響，寫成一段流暢的中文摘要（3句以內，不分段）。
▸ [來源名稱：繁體中文簡短標題](完整連結)
板塊關注：相關板塊中文名稱　*$代號1* *$代號2* *$代號3*

🇺🇸 *川普與政策*
（同格式：摘要 + 來源連結 + 板塊關注）

📈 *市場行情*
（同格式）

🤖 *AI 與科技*
（同格式）

---
重要規則：
- 超連結只能使用提供的原始連結，不得自行編造網址。
- 板塊關注：先寫1-2個中文板塊名稱，再列2-3個最直接相關的美股代號（加粗）。
- 若某主題無文章，在該區塊寫（暫無相關新聞），板塊關注那行省略。
- 所有內容一律使用繁體中文，股票代號保留英文。
- 只輸出訊息本身，不輸出任何其他內容。
"""

    response = CLIENT.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return escape_mdv2(response.content[0].text.strip())


# ── Telegram ──────────────────────────────────────────────────────────────────

def split_message(text: str, max_len: int = 4096) -> list[str]:
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
