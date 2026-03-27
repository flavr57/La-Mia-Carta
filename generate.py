#!/usr/bin/env python3
"""
La Mia Carta — daily Italian newspaper generator.

Fetches real data from free sources, sends to Claude API for Italian content,
injects into template.html, writes index.html.

Usage:
    ANTHROPIC_API_KEY=... python generate.py

Requires: anthropic feedparser requests yfinance
"""

import os
import sys
import json
import re
import datetime

import requests
import feedparser
import anthropic

# ─── Constants ────────────────────────────────────────────────────────────────

HERMOSA_LAT = 33.8622
HERMOSA_LON = -118.3995
LISBON_LAT = 38.7169
LISBON_LON = -9.1395

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ITALIAN_DAYS = [
    "Lunedi", "Martedi", "Mercoledi", "Giovedi",
    "Venerdi", "Sabato", "Domenica",
]
ITALIAN_MONTHS = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

WMO_DESCRIPTIONS = {
    0: "soleggiato",
    1: "prevalentemente soleggiato",
    2: "parzialmente nuvoloso",
    3: "nuvoloso",
    45: "nebbia",
    48: "nebbia ghiacciata",
    51: "pioggerella leggera",
    53: "pioggerella",
    55: "pioggerella intensa",
    61: "pioggia leggera",
    63: "pioggia moderata",
    65: "pioggia intensa",
    71: "neve leggera",
    73: "neve moderata",
    75: "neve intensa",
    80: "rovesci",
    81: "rovesci moderati",
    82: "rovesci intensi",
    95: "temporale",
    96: "temporale con grandine",
    99: "temporale forte",
}

RSS_SOURCES = {
    "portugal": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://rss.dw.com/xml/rss-en-world",
    ],
    "ai_tools": [
        "https://www.theverge.com/rss/index.xml",
        "https://hnrss.org/frontpage",
        "https://feeds.feedburner.com/TechCrunch",
    ],
    "travel": [
        "https://www.lonelyplanet.com/news/feed",
    ],
    "design": [
        "https://www.dezeen.com/feed/",
        "https://feeds.feedburner.com/archdaily",
    ],
    "culture": [
        "https://pitchfork.com/rss/news/feed.xml",
    ],
    "stories": [
        "https://www.corriere.it/rss/homepage.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ],
}

MOTIVATIONAL_QUOTES = [
    "Ogni giorno è una nuova opportunità per cambiare la tua vita.",
    "La fortuna aiuta gli audaci.",
    "Il successo è la somma di piccoli sforzi ripetuti ogni giorno.",
    "Non smettere mai di sognare.",
    "Chi vuole, può.",
    "Ogni grande viaggio inizia con un piccolo passo.",
    "Credi in te stesso e tutto sarà possibile.",
    "Il coraggio non è l'assenza di paura, ma la forza di andare avanti.",
    "La vita è bella, bisogna solo saperla vivere.",
    "I sogni non hanno scadenza.",
    "Ogni mattina hai due scelte: continuare a dormire o alzarti e inseguire i tuoi sogni.",
    "Il meglio deve ancora venire.",
    "La perseveranza è la chiave del successo.",
    "Non importa quanto vai lento, l'importante è non fermarsi.",
    "Sii il cambiamento che vuoi vedere nel mondo.",
    "Il futuro appartiene a chi crede nella bellezza dei propri sogni.",
    "Ogni ostacolo è un'opportunità mascherata.",
    "La strada verso il successo è sempre in costruzione.",
    "Agisci come se quello che fai facesse la differenza. Lo fa.",
    "Il successo non è definitivo, il fallimento non è fatale: è il coraggio di continuare che conta.",
    "Ognuno è il proprio architetto del destino.",
    "Non aspettare il momento giusto, crea il momento giusto.",
    "Fai oggi quello che gli altri non vogliono fare.",
    "L'unico modo per fare un ottimo lavoro è amare quello che fai.",
    "Un grande viaggio inizia sempre con un singolo passo.",
    "La mente è tutto. Sei quello che pensi.",
    "Non esistono sogni impossibili, esistono solo uomini che non credono abbastanza.",
    "Alzati, brillante e non aver paura.",
    "Il tuo tempo è limitato, non sprecarlo vivendo la vita di qualcun altro.",
    "Ogni giorno porta con sé nuove possibilità.",
]


# ─── Utilities ────────────────────────────────────────────────────────────────

def italian_date(dt: datetime.date) -> str:
    day = ITALIAN_DAYS[dt.weekday()]
    month = ITALIAN_MONTHS[dt.month - 1]
    return f"{day} {dt.day} {month} {dt.year}"


def _deg_to_direction(deg: float) -> str:
    dirs = ["nord", "nord-est", "est", "sud-est", "sud", "sud-ovest", "ovest", "nord-ovest"]
    return dirs[round(deg / 45) % 8]


# ─── Data fetching ────────────────────────────────────────────────────────────

def fetch_weather(lat: float, lon: float) -> dict:
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weathercode,wind_speed_10m"
            f"&temperature_unit=celsius&wind_speed_unit=kmh&timezone=auto"
        )
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        cur = r.json()["current"]
        code = int(cur.get("weathercode", 0))
        return {
            "temp_c": round(float(cur["temperature_2m"])),
            "description": WMO_DESCRIPTIONS.get(code, "variabile"),
            "wind_kmh": round(float(cur.get("wind_speed_10m", 0))),
        }
    except Exception as e:
        print(f"  [warn] weather fetch failed: {e}", file=sys.stderr)
        return {"temp_c": 18, "description": "soleggiato", "wind_kmh": 10}


def fetch_waves(lat: float, lon: float) -> dict:
    try:
        url = (
            f"https://marine-api.open-meteo.com/v1/marine"
            f"?latitude={lat}&longitude={lon}"
            f"&current=wave_height,wave_direction,wave_period,sea_surface_temperature"
            f"&timezone=auto"
        )
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        cur = r.json()["current"]
        return {
            "height_m": round(float(cur.get("wave_height", 1.0)), 1),
            "direction": _deg_to_direction(float(cur.get("wave_direction", 270))),
            "period_s": round(float(cur.get("wave_period", 10))),
            "water_temp_c": round(float(cur.get("sea_surface_temperature", 15))),
        }
    except Exception as e:
        print(f"  [warn] waves fetch failed: {e}", file=sys.stderr)
        return {"height_m": 1.0, "direction": "ovest", "period_s": 10, "water_temp_c": 15}


def fetch_market_data() -> dict:
    try:
        import yfinance as yf
    except ImportError:
        print("  [warn] yfinance not installed; skipping live market data", file=sys.stderr)
        return {}

    symbols = {
        "^GSPC": "sp500",
        "^IXIC": "nasdaq",
        "BTC-USD": "bitcoin",
        "EURUSD=X": "eurusd",
    }
    result = {}
    for symbol, key in symbols.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist.empty:
                continue
            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
            change_pct = ((current - prev) / prev * 100) if prev else 0.0
            result[key] = {"value": current, "change_pct": round(change_pct, 2)}
        except Exception as e:
            print(f"  [warn] market {symbol} failed: {e}", file=sys.stderr)
    return result


def format_market_value(key: str, value: float) -> str:
    if key == "bitcoin":
        return f"${value:,.0f}"
    elif key == "eurusd":
        return f"{value:.4f}"
    else:
        return f"{value:,.0f}"


def fetch_rss_items(url: str, max_items: int = 5) -> list:
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", ""))[:400]
            items.append({
                "title": getattr(entry, "title", "")[:200],
                "summary": summary.strip(),
                "link": getattr(entry, "link", ""),
            })
        return items
    except Exception as e:
        print(f"  [warn] RSS {url} failed: {e}", file=sys.stderr)
        return []


def fetch_all_news() -> dict:
    news = {}
    for section, urls in RSS_SOURCES.items():
        items = []
        for url in urls:
            items.extend(fetch_rss_items(url))
        news[section] = items[:8]
    return news


# ─── Claude prompt ────────────────────────────────────────────────────────────

def build_prompt(date_str, today_date, weather_hermosa, weather_lisbon, waves, markets, news) -> str:
    # Market data block
    mkt_lines = []
    for key, label in [("sp500", "S&P 500"), ("nasdaq", "Nasdaq"),
                        ("bitcoin", "Bitcoin"), ("eurusd", "EUR/USD")]:
        if key in markets:
            m = markets[key]
            sign = "+" if m["change_pct"] > 0 else ""
            val = format_market_value(key, m["value"])
            mkt_lines.append(f"  {label}: {val} ({sign}{m['change_pct']}%)")
        else:
            mkt_lines.append(f"  {label}: dati non disponibili")
    markets_block = "\n".join(mkt_lines)

    # News blocks — include source URLs so Claude can return them
    def fmt_news(items):
        if not items:
            return "  (nessuna notizia disponibile)"
        lines = []
        for i, it in enumerate(items, 1):
            if it["title"]:
                link = it.get("link", "")
                link_part = f"\n    URL: {link}" if link else ""
                lines.append(f"  {i}. {it['title']}: {it['summary'][:150]}{link_part}")
        return "\n".join(lines) if lines else "  (nessuna notizia disponibile)"

    h = waves["height_m"]
    h_hi = round(h + 0.5, 1)

    data_section = f"""\
You are generating content for "La Mia Carta", a daily personal Italian newspaper.
Write ALL content in A2-level Italian: simple vocabulary, short sentences, present \
tense preferred, passato prossimo for past events. No subjunctive. Newspaper editorial \
tone — NOT a language-learning app. Do not mention that this is A2 level anywhere.

TODAY: {date_str} (Month: {today_date.month}, Day: {today_date.day}, Year: {today_date.year})

RAW DATA — use this to write accurate content:

HERMOSA BEACH WEATHER:
  Temperature: {weather_hermosa['temp_c']}°C
  Conditions: {weather_hermosa['description']}
  Wind: {weather_hermosa['wind_kmh']} km/h

LISBON WEATHER:
  Temperature: {weather_lisbon['temp_c']}°C
  Conditions: {weather_lisbon['description']}

SURF — HERMOSA BEACH / EL PORTO:
  Wave height: {h}-{h_hi}m
  Direction: {waves['direction']}
  Period: {waves['period_s']}s
  Water temperature: {waves['water_temp_c']}°C

MARKETS (current prices):
{markets_block}

NEWS — PORTUGAL / LISBON:
{fmt_news(news.get('portugal', []))}

NEWS — AI & TOOLS:
{fmt_news(news.get('ai_tools', []))}

NEWS — TRAVEL:
{fmt_news(news.get('travel', []))}

NEWS — DESIGN & ARCHITECTURE:
{fmt_news(news.get('design', []))}

NEWS — MUSIC & CULTURE:
{fmt_news(news.get('culture', []))}

NEWS — HUMAN INTEREST STORIES:
{fmt_news(news.get('stories', []))}
"""

    schema_section = """\
─────────────────────────────────────────────────
OUTPUT: Return ONLY valid JSON (no markdown fences, no explanation) with this structure.

CRITICAL: All HTML inside JSON string values must use SINGLE QUOTES for attributes,
e.g. class='parola' not class="parola". Double quotes inside JSON strings break parsing.

{
  "accadde_oggi": "<p>One or two sentences about something that happened on this exact calendar date (month + day) in Italian or European history or culture. Use simple Italian. Be specific — name the year and event.</p>",

  "mercati_intro": "<p>One sentence about today's markets incorporating actual numbers above.</p>",
  "sp500_context": "Short Italian phrase (max 5 words) about S&P 500 direction",
  "nasdaq_context": "Short Italian phrase about Nasdaq",
  "bitcoin_context": "Short Italian phrase about Bitcoin",
  "eurusd_context": "Short Italian phrase about EUR/USD",

  "portogallo_quiet": true,
  "portogallo_headline": "",
  "portogallo_body": "<p>1-2 sentences about Portugal/Lisbon. Mention the weather. If real Portugal news exists in the RSS, mention it. Otherwise something calm about life there.</p>",

  "ai_headline": "Italian headline about first AI/tech news item (6-10 words)",
  "ai_body": "<p>3-4 sentences about the first AI/tech story from the RSS.</p><p>2-3 more sentences. Embed ONE Italian word as the parola using single-quote HTML: <span class='parola'>word<span class='parola-tooltip'>word = English translation</span></span></p>",
  "ai_source": "Publication name only, e.g. The Verge",
  "ai_source_url": "The exact URL from the RSS data for this article, or empty string",
  "ai_headline_2": "Italian headline about second AI/tech news item (6-10 words)",
  "ai_body_2": "<p>3-4 sentences about a different AI/tech story from the RSS.</p>",
  "ai_source_2": "Publication name only",
  "ai_source_url_2": "The exact URL from the RSS data for this second article, or empty string",

  "cucina_title": "Italian dish name",
  "cucina_body": "3-4 sentences narrated like a nonna telling you how to cook it. Warm, simple, no measurements, no recipe card format.",

  "surf_headline": "Italian headline about today's surf conditions (6-8 words)",
  "surf_body": "<p>2-3 sentences based on the actual surf data above. Include wave height, direction, best time to surf.</p>",

  "viaggio_headline": "Italian headline about Italy travel (6-8 words)",
  "viaggio_body": "<p>2-3 sentences about off-the-beaten-path Italy travel.</p>",
  "viaggio_source": "Publication name only",
  "viaggio_source_url": "The exact URL from the RSS travel data, or empty string",
  "viaggio_headline_2": "Second Italian travel headline (6-8 words)",
  "viaggio_body_2": "<p>2-3 sentences about a different travel destination or tip.</p>",
  "viaggio_source_2": "Publication name only",
  "viaggio_source_url_2": "URL from RSS for second travel article, or empty string",

  "design_headline": "Italian headline about design or architecture (6-8 words)",
  "design_body": "<p>2-3 sentences about design or architecture.</p>",
  "design_source": "Publication name only",
  "design_source_url": "The exact URL from the RSS design data, or empty string",
  "design_headline_2": "Second design/architecture headline (6-8 words)",
  "design_body_2": "<p>2-3 sentences about a different design or architecture story.</p>",
  "design_source_2": "Publication name only",
  "design_source_url_2": "URL from RSS for second design article, or empty string",

  "musica_headline": "Italian headline about music or Italian culture (6-8 words)",
  "musica_body": "<p>2-3 sentences about Italian music or culture.</p>",
  "musica_source": "Publication name only",
  "musica_source_url": "The exact URL from the RSS culture data, or empty string",
  "musica_headline_2": "Second music/culture headline (6-8 words)",
  "musica_body_2": "<p>2-3 sentences about a different music or culture story.</p>",
  "musica_source_2": "Publication name only",
  "musica_source_url_2": "URL from RSS for second culture article, or empty string",

  "storie_headline": "Compelling human-interest headline in Italian (8-12 words)",
  "storie_body": "<p>3-4 sentences: a vivid story about an Italian or Mediterranean person. Specific details, sensory language, present tense.</p><p>2-3 sentences continuing the story.</p>",
  "storie_source": "Publication name only",
  "storie_source_url": "The exact URL from the RSS stories data, or empty string",
  "storie_headline_2": "Second human-interest headline (8-12 words)",
  "storie_body_2": "<p>3-4 sentences: another vivid human-interest story.</p>",
  "storie_source_2": "Publication name only",
  "storie_source_url_2": "URL from RSS for second story, or empty string",

  "crossword": {
    "rows": 5,
    "cols": 5,
    "cells": [
      {"row": 0, "col": 0, "black": false, "number": 1},
      {"row": 0, "col": 1, "black": false, "number": null}
    ],
    "across_clues": [
      {"number": 1, "clue": "Simple Italian clue (beginner level)", "letters": 4}
    ],
    "down_clues": [
      {"number": 1, "clue": "Simple Italian clue (beginner level)", "letters": 3}
    ]
  },

  "anagram": [
    {"scrambled": "ACAS", "answer": "CASA"},
    {"scrambled": "EARM", "answer": "MARE"},
    {"scrambled": "LEOS", "answer": "SOLE"}
  ],

  "footer_quote": "A famous motivational Italian quote. Inspiring, uplifting tone. In Italian only."
}

RULES:
1. HTML attributes inside JSON strings: ALWAYS use single quotes (class='x' not class="x").
2. The parola span: embed naturally in one section body — not forced, not labeled.
3. portogallo_quiet: false ONLY if there is genuinely important Portugal news in the RSS. Default true.
4. CROSSWORD — BEGINNER LEVEL ONLY:
   - Use ONLY very common A1-A2 Italian words: CASA, MARE, SOLE, PANE, GATTO, CANE,
     VINO, LUCE, ARIA, VITA, ROSA, LUNA, MANO, NASO, DITO, etc.
   - Words must be exactly 3, 4, or 5 letters. Never longer.
   - Clues must be extremely simple and obvious. Example: "Dove abitiamo" for CASA,
     "Il contrario di notte" for GIORNO, "La bevanda italiana preferita" for VINO.
   - Grid is 5x5 (25 cells total, rows 0-4, cols 0-4).
   - Pick 3-4 short words with at least one intersection point.
   - List ALL 25 cells. Every cell needs row, col, black (true/false), number (int or null).
   - Black cells should be symmetric and tasteful — not random.
5. ANAGRAM — use 3 or 4 simple Italian words (3-5 letters) drawn from the articles above.
   Scramble each word's letters randomly. Answers must be real Italian A1-A2 words.
6. Numbers (prices, temperatures, wave heights) must match the raw data above exactly.
7. Source URLs: copy them EXACTLY from the RSS data above. Do not invent or modify URLs.
   If no URL is available for a section, use an empty string "".
8. Return ONLY the JSON object. Nothing before or after it.
"""

    return data_section + schema_section


# ─── Crossword renderer ───────────────────────────────────────────────────────

def render_crossword_html(crossword: dict) -> str:
    rows = crossword.get("rows", 5)
    cols = crossword.get("cols", 5)
    cells_data = crossword.get("cells", [])

    # Build 2D grid (default all black)
    grid = [[{"black": True} for _ in range(cols)] for _ in range(rows)]
    for cell in cells_data:
        r, c = cell.get("row", 0), cell.get("col", 0)
        if 0 <= r < rows and 0 <= c < cols:
            grid[r][c] = cell

    lines = [f'<div class="crossword-grid" style="grid-template-columns: repeat({cols}, 36px);">']
    for r in range(rows):
        lines.append(f"  <!-- Row {r + 1} -->")
        for c in range(cols):
            cell = grid[r][c]
            if cell.get("black", True):
                lines.append('  <div class="crossword-cell black"></div>')
            else:
                number = cell.get("number")
                num_html = f'<span class="cell-number">{number}</span>' if number else ""
                lines.append(
                    f'  <div class="crossword-cell">'
                    f'{num_html}'
                    f'<input maxlength="1" data-row="{r}" data-col="{c}">'
                    f"</div>"
                )
    lines.append("</div>")

    across = crossword.get("across_clues", [])
    down_clues = crossword.get("down_clues", [])

    lines.append('<div class="crossword-clues">')
    lines.append("  <div>")
    lines.append('    <div class="clue-group-title">Orizzontali</div>')
    for clue in across:
        num = clue.get("number", "")
        txt = clue.get("clue", "")
        let = clue.get("letters", "")
        suffix = f" ({let} lettere)" if let else ""
        lines.append(f'    <div class="clue"><strong>{num}.</strong> {txt}{suffix}</div>')
    lines.append("  </div>")
    lines.append("  <div>")
    lines.append('    <div class="clue-group-title">Verticali</div>')
    for clue in down_clues:
        num = clue.get("number", "")
        txt = clue.get("clue", "")
        let = clue.get("letters", "")
        suffix = f" ({let} lettere)" if let else ""
        lines.append(f'    <div class="clue"><strong>{num}.</strong> {txt}{suffix}</div>')
    lines.append("  </div>")
    lines.append("</div>")

    return "\n".join(lines)


# ─── Anagram renderer ─────────────────────────────────────────────────────────

def render_anagram_html(anagrams: list) -> str:
    if not anagrams:
        return ""
    lines = ['<div class="anagram-puzzle">']
    for item in anagrams:
        scrambled = item.get("scrambled", "").upper()
        answer = item.get("answer", "").upper()
        if scrambled and answer:
            lines.append('  <div class="anagram-item">')
            lines.append(f'    <span class="anagram-scrambled">{scrambled}</span>')
            lines.append(
                f'    <input type="text" class="anagram-input" maxlength="{len(answer)}"'
                f' data-answer="{answer}" placeholder="Scrivi qui..." autocomplete="off" autocorrect="off" spellcheck="false">'
            )
            lines.append('    <span class="anagram-result"></span>')
            lines.append('  </div>')
    lines.append('  <button class="anagram-check-btn" onclick="checkAnagrams()">Controlla le risposte</button>')
    lines.append('  <button class="anagram-reveal-btn" onclick="revealAnagrams()">Mostra soluzioni</button>')
    lines.append('</div>')
    return "\n".join(lines)


# ─── Source link builder ──────────────────────────────────────────────────────

def make_source_html(source_text: str, source_url: str) -> str:
    """Build a section-source div with optional clickable link."""
    text = (source_text or "").strip()
    url = (source_url or "").strip()
    if not text and not url:
        return ""
    if url and url.startswith("http"):
        display = text if text else url
        return (
            f'<div class="section-source">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">{display} ↗</a>'
            f'</div>'
        )
    return f'<div class="section-source">{text}</div>'


# ─── Template injection ───────────────────────────────────────────────────────

def inject_template(template: str, tokens: dict) -> str:
    result = template
    for key, value in tokens.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


# ─── JSON repair ─────────────────────────────────────────────────────────────

def _repair_json_html_attrs(json_str: str) -> str:
    """
    Fix unescaped double quotes inside HTML attribute values within JSON strings.
    """
    result = []
    in_string = False
    escaped = False
    i = 0
    while i < len(json_str):
        ch = json_str[i]
        if escaped:
            result.append(ch)
            escaped = False
            i += 1
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escaped = True
            i += 1
            continue
        if ch == '"':
            if not in_string:
                in_string = True
                result.append(ch)
            else:
                rest = json_str[i+1:].lstrip()
                if rest and rest[0] in (':', ',', '}', ']', '\n', '\r'):
                    in_string = False
                    result.append(ch)
                else:
                    result.append("'")
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    template_path = os.path.join(SCRIPT_DIR, "template.html")
    output_path = os.path.join(SCRIPT_DIR, "index.html")

    if not os.path.exists(template_path):
        print(f"ERROR: template.html not found at {template_path}", file=sys.stderr)
        sys.exit(1)

    with open(template_path) as f:
        template = f.read()

    today = datetime.date.today()
    date_str = italian_date(today)

    print(f"Generating La Mia Carta — {date_str}")

    print("  Fetching weather (Hermosa Beach + Lisbon)...")
    weather_hermosa = fetch_weather(HERMOSA_LAT, HERMOSA_LON)
    weather_lisbon = fetch_weather(LISBON_LAT, LISBON_LON)

    print("  Fetching wave data...")
    waves = fetch_waves(HERMOSA_LAT, HERMOSA_LON)

    print("  Fetching market data...")
    markets = fetch_market_data()

    print("  Fetching RSS news...")
    news = fetch_all_news()

    print("  Calling Claude API...")
    client = anthropic.Anthropic()

    prompt = build_prompt(date_str, today, weather_hermosa, weather_lisbon, waves, markets, news)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude added them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Extract the JSON object
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        print("ERROR: No JSON found in Claude response:", file=sys.stderr)
        print(raw[:2000], file=sys.stderr)
        sys.exit(1)

    json_str = json_match.group()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        repaired = _repair_json_html_attrs(json_str)
        try:
            data = json.loads(repaired)
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON parse failed even after repair: {e}", file=sys.stderr)
            print(json_str[:3000], file=sys.stderr)
            sys.exit(1)

    print("  Building page...")

    # Market display values
    def mkt(key):
        if key not in markets:
            return "—", "—", "flat", data.get(f"{key}_context", "")
        m = markets[key]
        val = format_market_value(key, m["value"])
        pct = m["change_pct"]
        cls = "up" if pct > 0 else ("down" if pct < 0 else "flat")
        sign = "+" if pct > 0 else ""
        return val, f"{sign}{pct}%", cls, data.get(f"{key}_context", "")

    sp500_val, sp500_chg, sp500_cls, sp500_ctx = mkt("sp500")
    nasdaq_val, nasdaq_chg, nasdaq_cls, nasdaq_ctx = mkt("nasdaq")
    btc_val, btc_chg, btc_cls, btc_ctx = mkt("bitcoin")
    eur_val, eur_chg, eur_cls, eur_ctx = mkt("eurusd")

    # Portugal status block
    if data.get("portogallo_quiet", True):
        portugal_status_html = (
            '<div class="portugal-status">\n'
            '      <span class="portugal-check">&#10003;</span>\n'
            '      Niente di importante oggi. Tutto tranquillo.\n'
            '    </div>'
        )
    else:
        headline = data.get("portogallo_headline", "")
        portugal_status_html = f'<div class="section-headline">{headline}</div>'

    # Crossword HTML
    crossword_html = render_crossword_html(data.get("crossword", {}))

    # Anagram HTML
    anagram_html = render_anagram_html(data.get("anagram", []))

    # Wave display
    h = waves["height_m"]
    h_hi = round(h + 0.5, 1)
    wave_display = f"Onde: {h}\u2013{h_hi}m da {waves['direction']}"

    # Daily motivational quote — rotate by day of year
    quote_fallback = MOTIVATIONAL_QUOTES[today.timetuple().tm_yday % len(MOTIVATIONAL_QUOTES)]
    footer_quote = data.get("footer_quote") or quote_fallback

    # Source HTML builders for each section
    ai_source_html   = make_source_html(data.get("ai_source", ""),     data.get("ai_source_url", ""))
    ai_source_html_2 = make_source_html(data.get("ai_source_2", ""),   data.get("ai_source_url_2", ""))

    viaggio_source_html   = make_source_html(data.get("viaggio_source", ""),   data.get("viaggio_source_url", ""))
    viaggio_source_html_2 = make_source_html(data.get("viaggio_source_2", ""), data.get("viaggio_source_url_2", ""))

    design_source_html   = make_source_html(data.get("design_source", ""),   data.get("design_source_url", ""))
    design_source_html_2 = make_source_html(data.get("design_source_2", ""), data.get("design_source_url_2", ""))

    musica_source_html   = make_source_html(data.get("musica_source", ""),   data.get("musica_source_url", ""))
    musica_source_html_2 = make_source_html(data.get("musica_source_2", ""), data.get("musica_source_url_2", ""))

    storie_source_html   = make_source_html(data.get("storie_source", ""),   data.get("storie_source_url", ""))
    storie_source_html_2 = make_source_html(data.get("storie_source_2", ""), data.get("storie_source_url_2", ""))

    tokens = {
        "DATE_ITALIAN": date_str,
        "WEATHER_HERMOSA_FULL": f"Hermosa Beach {weather_hermosa['temp_c']}°C, {weather_hermosa['description']}",
        "WEATHER_WAVES_FULL": wave_display,
        "WEATHER_WATER": f"{waves['water_temp_c']}°C",
        "ACCADDE_OGGI": data.get("accadde_oggi", ""),
        "MERCATI_INTRO": data.get("mercati_intro", ""),
        "SP500_VALUE": sp500_val,
        "SP500_CHANGE": sp500_chg,
        "SP500_CLASS": sp500_cls,
        "SP500_CONTEXT": sp500_ctx,
        "NASDAQ_VALUE": nasdaq_val,
        "NASDAQ_CHANGE": nasdaq_chg,
        "NASDAQ_CLASS": nasdaq_cls,
        "NASDAQ_CONTEXT": nasdaq_ctx,
        "BTC_VALUE": btc_val,
        "BTC_CHANGE": btc_chg,
        "BTC_CLASS": btc_cls,
        "BTC_CONTEXT": btc_ctx,
        "EURUSD_VALUE": eur_val,
        "EURUSD_CHANGE": eur_chg,
        "EURUSD_CLASS": eur_cls,
        "EURUSD_CONTEXT": eur_ctx,
        "PORTOGALLO_STATUS_HTML": portugal_status_html,
        "PORTOGALLO_BODY": data.get("portogallo_body", ""),
        "AI_HEADLINE": data.get("ai_headline", ""),
        "AI_BODY": data.get("ai_body", ""),
        "AI_SOURCE_HTML": ai_source_html,
        "AI_HEADLINE_2": data.get("ai_headline_2", ""),
        "AI_BODY_2": data.get("ai_body_2", ""),
        "AI_SOURCE_HTML_2": ai_source_html_2,
        "CUCINA_TITLE": data.get("cucina_title", ""),
        "CUCINA_BODY": data.get("cucina_body", ""),
        "SURF_HEADLINE": data.get("surf_headline", ""),
        "SURF_BODY": data.get("surf_body", ""),
        "VIAGGIO_HEADLINE": data.get("viaggio_headline", ""),
        "VIAGGIO_BODY": data.get("viaggio_body", ""),
        "VIAGGIO_SOURCE_HTML": viaggio_source_html,
        "VIAGGIO_HEADLINE_2": data.get("viaggio_headline_2", ""),
        "VIAGGIO_BODY_2": data.get("viaggio_body_2", ""),
        "VIAGGIO_SOURCE_HTML_2": viaggio_source_html_2,
        "DESIGN_HEADLINE": data.get("design_headline", ""),
        "DESIGN_BODY": data.get("design_body", ""),
        "DESIGN_SOURCE_HTML": design_source_html,
        "DESIGN_HEADLINE_2": data.get("design_headline_2", ""),
        "DESIGN_BODY_2": data.get("design_body_2", ""),
        "DESIGN_SOURCE_HTML_2": design_source_html_2,
        "MUSICA_HEADLINE": data.get("musica_headline", ""),
        "MUSICA_BODY": data.get("musica_body", ""),
        "MUSICA_SOURCE_HTML": musica_source_html,
        "MUSICA_HEADLINE_2": data.get("musica_headline_2", ""),
        "MUSICA_BODY_2": data.get("musica_body_2", ""),
        "MUSICA_SOURCE_HTML_2": musica_source_html_2,
        "STORIE_HEADLINE": data.get("storie_headline", ""),
        "STORIE_BODY": data.get("storie_body", ""),
        "STORIE_SOURCE_HTML": storie_source_html,
        "STORIE_HEADLINE_2": data.get("storie_headline_2", ""),
        "STORIE_BODY_2": data.get("storie_body_2", ""),
        "STORIE_SOURCE_HTML_2": storie_source_html_2,
        "CROSSWORD_HTML": crossword_html,
        "ANAGRAM_HTML": anagram_html,
        "FOOTER_QUOTE": footer_quote,
        "FOOTER_DATE": f"{today.day} {ITALIAN_MONTHS[today.month - 1]} {today.year}",
    }

    output = inject_template(template, tokens)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"  Done — index.html written ({len(output):,} bytes)")


if __name__ == "__main__":
    main()
