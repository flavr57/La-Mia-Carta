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
import time

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

# ─── Fallback crossword ───────────────────────────────────────────────────────
# Used when build_crossword_grid() fails after all attempts.
# Layout: PANE across row 1, LANA down col 1, EURO down col 3.
# Intersections: A@(1,1), E@(1,3).
FALLBACK_CROSSWORD = {
    "words": [
        {"word": "PANE", "clue": "Il cibo di base",         "row": 1, "col": 0, "direction": "across"},
        {"word": "LANA", "clue": "Il pelo delle pecore",    "row": 0, "col": 1, "direction": "down"},
        {"word": "EURO", "clue": "La moneta dell'Italia",   "row": 1, "col": 3, "direction": "down"},
    ],
    "rows": 5,
    "cols": 5,
    "cells": [
        {"row": 0, "col": 0, "black": True,  "number": None, "letter": ""},
        {"row": 0, "col": 1, "black": False, "number": 1,    "letter": "L"},
        {"row": 0, "col": 2, "black": True,  "number": None, "letter": ""},
        {"row": 0, "col": 3, "black": True,  "number": None, "letter": ""},
        {"row": 0, "col": 4, "black": True,  "number": None, "letter": ""},
        {"row": 1, "col": 0, "black": False, "number": 2,    "letter": "P"},
        {"row": 1, "col": 1, "black": False, "number": None, "letter": "A"},
        {"row": 1, "col": 2, "black": False, "number": None, "letter": "N"},
        {"row": 1, "col": 3, "black": False, "number": 3,    "letter": "E"},
        {"row": 1, "col": 4, "black": True,  "number": None, "letter": ""},
        {"row": 2, "col": 0, "black": True,  "number": None, "letter": ""},
        {"row": 2, "col": 1, "black": False, "number": None, "letter": "N"},
        {"row": 2, "col": 2, "black": True,  "number": None, "letter": ""},
        {"row": 2, "col": 3, "black": False, "number": None, "letter": "U"},
        {"row": 2, "col": 4, "black": True,  "number": None, "letter": ""},
        {"row": 3, "col": 0, "black": True,  "number": None, "letter": ""},
        {"row": 3, "col": 1, "black": False, "number": None, "letter": "A"},
        {"row": 3, "col": 2, "black": True,  "number": None, "letter": ""},
        {"row": 3, "col": 3, "black": False, "number": None, "letter": "R"},
        {"row": 3, "col": 4, "black": True,  "number": None, "letter": ""},
        {"row": 4, "col": 0, "black": True,  "number": None, "letter": ""},
        {"row": 4, "col": 1, "black": True,  "number": None, "letter": ""},
        {"row": 4, "col": 2, "black": True,  "number": None, "letter": ""},
        {"row": 4, "col": 3, "black": False, "number": None, "letter": "O"},
        {"row": 4, "col": 4, "black": True,  "number": None, "letter": ""},
    ],
    "across_clues": [
        {"number": 2, "clue": "Il cibo di base, fatto con farina e acqua", "letters": 4},
    ],
    "down_clues": [
        {"number": 1, "clue": "Il pelo delle pecore, usato per i maglioni", "letters": 4},
        {"number": 3, "clue": "La moneta ufficiale dell'Italia", "letters": 4},
    ],
}


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

═══════════════════════════════════════════════════════
TODAY'S DATE: {date_str} ({today_date.year}-{today_date.month:02d}-{today_date.day:02d})
THIS IS A UNIQUE DAILY EDITION.
DO NOT reuse headlines, story angles, topics, or article ideas from any previous day.
Treat this edition as completely new and independent.
═══════════════════════════════════════════════════════

CONTENT QUALITY RULES — write like a real journalist:
- Use specific names: real cities, real people, real companies from the RSS data below.
- Cite actual facts and details from the RSS summaries (numbers, locations, events).
- Avoid generic filler phrases like "gli esperti dicono", "negli ultimi anni", "è importante".
- Base every article closely on actual RSS content — do NOT invent generic stories.
- Every paragraph must contain at least one specific, verifiable detail from the RSS.

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

  "crossword_words": [
    {"word": "CASA",  "clue": "Dove abitiamo"},
    {"word": "SOLE",  "clue": "La stella che scalda la Terra"},
    {"word": "MARE",  "clue": "Grande acqua salata"},
    {"word": "PANE",  "clue": "Il cibo fatto con farina"},
    {"word": "VINO",  "clue": "Bevanda italiana famosa nel mondo"},
    {"word": "CANE",  "clue": "Animale domestico fedele"},
    {"word": "ARIA",  "clue": "Quello che respiriamo"},
    {"word": "MANO",  "clue": "Parte del corpo per toccare"},
    {"word": "LUNA",  "clue": "Il satellite naturale della Terra"},
    {"word": "ROSA",  "clue": "Fiore romantico, spesso rosso"},
    {"word": "BENE",  "clue": "Come stai? Sto ..."},
    {"word": "SALE",  "clue": "Condimento bianco per il cibo"}
  ],

  "anagram": [
    {"scrambled": "ACAS", "answer": "CASA"},
    {"scrambled": "EARM", "answer": "MARE"},
    {"scrambled": "LEOS", "answer": "SOLE"},
    {"scrambled": "ENAP", "answer": "PANE"},
    {"scrambled": "URAI", "answer": "ARIA"}
  ],

  "footer_quote": "A famous motivational Italian quote. Inspiring, uplifting tone. In Italian only."
}

RULES:
1. HTML attributes inside JSON strings: ALWAYS use single quotes (class='x' not class="x").
2. The parola span: embed naturally in one section body — not forced, not labeled.
3. portogallo_quiet: false ONLY if there is genuinely important Portugal news in the RSS. Default true.
4. CROSSWORD — provide AT LEAST 12 Italian words in "crossword_words". Rules:
   - Words: A1-A2 level, 3-6 letters, ALL CAPS, ASCII only (no accents, no spaces).
   - Choose words with common vowels (A, E, O, I) so they can intersect.
   - Good pool: CASA, MARE, SOLE, PANE, VINO, GATTO, CANE, LUCE, ARIA, VITA, ROSA,
     LUNA, MANO, NASO, DITO, LANA, EURO, BENE, MESE, LAGO, SALE, SERA, BARCA,
     FIORE, VERDE, ROSSO, BUONO, DOLCE, FORTE, NUOVO, PORTA, LIBRO, TRENO, ORSO.
   - Clues: simple Italian, 4-8 words, obvious meaning. No subjunctive.
   - DO NOT include a grid — Python builds the grid automatically from the words.
5. ANAGRAM — provide EXACTLY 5 words. Rules:
   - Words MUST come from today's articles content above (city names, topic words,
     action words, things mentioned in the news). NOT hardcoded words.
   - 3-6 letters, A1-A2 Italian words only, no accents.
   - Scramble so letter order is DIFFERENT from original (scrambled ≠ answer).
   - Never use the same words as previous editions — pick fresh words from today.
6. Numbers (prices, temperatures, wave heights) must match the raw data above exactly.
7. Source URLs: copy them EXACTLY from the RSS data above. Do not invent or modify URLs.
   If no URL is available for a section, use an empty string "".
8. Return ONLY the JSON object. Nothing before or after it.
"""

    return data_section + schema_section


# ─── Crossword renderer ───────────────────────────────────────────────────────

def render_crossword_html(crossword: dict) -> str:
    rows = crossword.get("rows", 8)
    cols = crossword.get("cols", 8)
    cells_data = crossword.get("cells", [])

    # Build 2D grid (default all black)
    grid = [[{"black": True} for _ in range(cols)] for _ in range(rows)]
    for cell in cells_data:
        r, c = cell.get("row", 0), cell.get("col", 0)
        if 0 <= r < rows and 0 <= c < cols:
            grid[r][c] = cell

    # Cell pixel size: shrink slightly for wider grids
    cell_px = 34 if cols <= 10 else 30

    lines = [f'<div class="crossword-grid" style="grid-template-columns: repeat({cols}, {cell_px}px);">']
    for r in range(rows):
        for c in range(cols):
            cell = grid[r][c]
            if cell.get("black", True):
                lines.append(f'  <div class="crossword-cell black" style="width:{cell_px}px;height:{cell_px}px;"></div>')
            else:
                number = cell.get("number")
                letter = cell.get("letter", "")
                num_html = f'<span class="cell-number">{number}</span>' if number else ""
                lines.append(
                    f'  <div class="crossword-cell" data-answer="{letter}"'
                    f' style="width:{cell_px}px;height:{cell_px}px;">'
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
        suffix = f" ({let})" if let else ""
        lines.append(f'    <div class="clue"><strong>{num}.</strong> {txt}{suffix}</div>')
    lines.append("  </div>")
    lines.append("  <div>")
    lines.append('    <div class="clue-group-title">Verticali</div>')
    for clue in down_clues:
        num = clue.get("number", "")
        txt = clue.get("clue", "")
        let = clue.get("letters", "")
        suffix = f" ({let})" if let else ""
        lines.append(f'    <div class="clue"><strong>{num}.</strong> {txt}{suffix}</div>')
    lines.append("  </div>")
    lines.append("</div>")

    lines.append('<div class="crossword-btn-row">')
    lines.append('  <button class="crossword-check-btn" onclick="checkCrossword()">Controlla</button>')
    lines.append('  <button class="crossword-reveal-btn" onclick="revealCrossword()">Mostra soluzioni</button>')
    lines.append('</div>')

    return "\n".join(lines)


# ─── Crossword validator ──────────────────────────────────────────────────────

def validate_crossword(crossword: dict) -> tuple[bool, str]:
    """
    Check that every clue's (number, letters, direction) is consistent with the grid.
    Returns (True, "") on success or (False, reason) on first failure.

    A clue with number N and letters L is valid when:
      - A cell with number=N exists in the cells list.
      - There are exactly L consecutive non-black cells going in the clue's direction
        starting from that cell.
    """
    rows = crossword.get("rows", 5)
    cols = crossword.get("cols", 5)
    cells_data = crossword.get("cells", [])

    if not cells_data:
        return False, "no cells in crossword"

    # Build lookup: (row, col) -> cell dict
    cell_map: dict = {}
    for cell in cells_data:
        r = cell.get("row")
        c = cell.get("col")
        if r is not None and c is not None:
            cell_map[(r, c)] = cell

    # Build lookup: number -> (row, col)
    number_pos: dict = {}
    for (r, c), cell in cell_map.items():
        num = cell.get("number")
        if num is not None:
            number_pos[int(num)] = (r, c)

    def run_length(r: int, c: int, dr: int, dc: int) -> int:
        """Count consecutive non-black cells from (r,c) in direction (dr,dc)."""
        length = 0
        while 0 <= r < rows and 0 <= c < cols:
            cell = cell_map.get((r, c), {"black": True})
            if cell.get("black", True):
                break
            length += 1
            r += dr
            c += dc
        return length

    for clue in crossword.get("across_clues", []):
        num = int(clue.get("number", 0))
        expected = int(clue.get("letters", 0))
        if num not in number_pos:
            return False, f"across clue {num}: no cell has this number"
        r, c = number_pos[num]
        actual = run_length(r, c, 0, 1)
        if actual != expected:
            return False, (
                f"across clue {num}: grid has {actual} white cells going right "
                f"from ({r},{c}), but clue says {expected} letters"
            )

    for clue in crossword.get("down_clues", []):
        num = int(clue.get("number", 0))
        expected = int(clue.get("letters", 0))
        if num not in number_pos:
            return False, f"down clue {num}: no cell has this number"
        r, c = number_pos[num]
        actual = run_length(r, c, 1, 0)
        if actual != expected:
            return False, (
                f"down clue {num}: grid has {actual} white cells going down "
                f"from ({r},{c}), but clue says {expected} letters"
            )

    # Must have at least one across and one down clue
    if not crossword.get("across_clues"):
        return False, "no across clues"
    if not crossword.get("down_clues"):
        return False, "no down clues"

    return True, ""


# ─── Crossword grid builder ──────────────────────────────────────────────────

def build_crossword_grid(word_clue_pairs: list, attempts: int = 8) -> dict | None:
    """
    Place word+clue pairs into a crossword grid using letter intersections.
    Returns a crossword dict (rows, cols, cells, words, across_clues, down_clues)
    or None if placement fails after all attempts.
    """
    import random as _rnd

    # Filter: uppercase ASCII only, 3-6 letters
    clean = []
    for pair in word_clue_pairs:
        w = pair.get("word", "").strip().upper()
        clue = pair.get("clue", "").strip()
        if 3 <= len(w) <= 6 and w.isalpha() and all(ord(c) < 128 for c in w):
            clean.append((w, clue))
    if len(clean) < 6:
        return None

    # Sort by length descending; longer words anchor better
    clean.sort(key=lambda x: len(x[0]), reverse=True)

    G = 18  # internal grid size

    for _attempt in range(attempts):
        grid: dict = {}      # (r, c) -> letter
        placed: list = []    # dicts: word, clue, row, col, direction

        def can_place(word, row, col, direction):
            dr, dc = (1, 0) if direction == "down" else (0, 1)
            end_r = row + dr * (len(word) - 1)
            end_c = col + dc * (len(word) - 1)
            if end_r >= G or end_c >= G or row < 0 or col < 0:
                return False
            # Cell immediately before start must be empty
            if 0 <= row - dr < G and 0 <= col - dc < G:
                if (row - dr, col - dc) in grid:
                    return False
            # Cell immediately after end must be empty
            if 0 <= row + dr * len(word) < G and 0 <= col + dc * len(word) < G:
                if (row + dr * len(word), col + dc * len(word)) in grid:
                    return False
            intersections = 0
            for i, letter in enumerate(word):
                r, c = row + dr * i, col + dc * i
                if (r, c) in grid:
                    if grid[(r, c)] != letter:
                        return False
                    intersections += 1
                else:
                    # Perpendicular neighbors of new cells must be empty
                    # (prevents unwanted parallel adjacency)
                    if direction == "across":
                        if (r - 1, c) in grid or (r + 1, c) in grid:
                            return False
                    else:
                        if (r, c - 1) in grid or (r, c + 1) in grid:
                            return False
            return len(placed) == 0 or intersections > 0

        def do_place(word, row, col, direction, clue):
            dr, dc = (1, 0) if direction == "down" else (0, 1)
            for i, letter in enumerate(word):
                grid[(row + dr * i, col + dc * i)] = letter
            placed.append({"word": word, "clue": clue,
                            "row": row, "col": col, "direction": direction})

        # Place first word horizontally in centre
        fw, fc = clean[0]
        do_place(fw, G // 2, (G - len(fw)) // 2, "across", fc)

        # Shuffle remaining words for variety across attempts
        remaining = list(clean[1:])
        _rnd.shuffle(remaining)

        for word, clue in remaining:
            options = []
            for p in placed:
                new_dir = "down" if p["direction"] == "across" else "across"
                for i, nl in enumerate(word):
                    for j, pl in enumerate(p["word"]):
                        if nl == pl:
                            if p["direction"] == "across":
                                row = p["row"] - i
                                col = p["col"] + j
                            else:
                                row = p["row"] + j
                                col = p["col"] - i
                            if can_place(word, row, col, new_dir):
                                options.append((row, col, new_dir))
            if options:
                row, col, direction = _rnd.choice(options)
                do_place(word, row, col, direction, clue)

        if len(placed) < min(10, len(clean)):
            continue  # try again

        # Compute tight bounding box
        all_r = [p["row"] for p in placed] + \
                [p["row"] + len(p["word"]) - 1 for p in placed if p["direction"] == "down"]
        all_c = [p["col"] for p in placed] + \
                [p["col"] + len(p["word"]) - 1 for p in placed if p["direction"] == "across"]
        min_r, max_r = min(all_r), max(all_r)
        min_c, max_c = min(all_c), max(all_c)

        # Remap coordinates to (0,0) origin
        new_grid = {(r - min_r, c - min_c): letter for (r, c), letter in grid.items()}
        for p in placed:
            p["row"] -= min_r
            p["col"] -= min_c
        grid = new_grid
        rows = max_r - min_r + 1
        cols = max_c - min_c + 1

        # Assign numbers left-to-right, top-to-bottom
        number_map: dict = {}
        num = 1
        for r in range(rows):
            for c in range(cols):
                if (r, c) not in grid:
                    continue
                starts_across = ((c == 0 or (r, c - 1) not in grid)
                                 and (r, c + 1) in grid)
                starts_down = ((r == 0 or (r - 1, c) not in grid)
                               and (r + 1, c) in grid)
                if starts_across or starts_down:
                    number_map[(r, c)] = num
                    num += 1

        # Build cells list (includes letter for data-answer)
        cells = []
        for r in range(rows):
            for c in range(cols):
                is_black = (r, c) not in grid
                cells.append({
                    "row": r, "col": c,
                    "black": is_black,
                    "number": number_map.get((r, c)) if not is_black else None,
                    "letter": grid.get((r, c), ""),
                })

        # Build clue lists
        across_clues, down_clues = [], []
        for p in placed:
            num_val = number_map.get((p["row"], p["col"]))
            if num_val is None:
                continue
            entry = {"number": num_val, "clue": p["clue"], "letters": len(p["word"])}
            (across_clues if p["direction"] == "across" else down_clues).append(entry)
        across_clues.sort(key=lambda x: x["number"])
        down_clues.sort(key=lambda x: x["number"])

        if across_clues and down_clues:
            return {
                "words": placed,
                "rows": rows,
                "cols": cols,
                "cells": cells,
                "across_clues": across_clues,
                "down_clues": down_clues,
            }

    return None  # all attempts failed


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

    response = None
    for attempt in range(1, 4):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 3:
                print(f"  API overloaded (attempt {attempt}/3), retrying in 30s...")
                time.sleep(30)
            else:
                raise

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

    # Crossword HTML — build grid from Claude's word list; fall back if placement fails
    crossword_words = data.get("crossword_words", [])
    crossword_data = None
    if crossword_words:
        print(f"  Building crossword grid from {len(crossword_words)} words...")
        crossword_data = build_crossword_grid(crossword_words)
        if crossword_data is None:
            print("  [warn] Crossword placement failed after all attempts. Using fallback.", file=sys.stderr)
    else:
        print("  [warn] No crossword_words in Claude response. Using fallback.", file=sys.stderr)
    if crossword_data is None:
        crossword_data = FALLBACK_CROSSWORD
    else:
        print(f"  Crossword: {len(crossword_data['words'])} words placed on "
              f"{crossword_data['rows']}x{crossword_data['cols']} grid.")
    crossword_html = render_crossword_html(crossword_data)

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
