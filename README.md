# La Mia Carta

A daily personal morning newspaper, generated fresh at 6am every day, written entirely in Italian. Real data (markets, weather, surf, news) — written by Claude at A2 level, newspaper tone.

Live at: **[flavr57.github.io/La-Mia-Carta](https://flavr57.github.io/La-Mia-Carta)**

---

## How It Works

Every morning a GitHub Actions workflow:

1. Fetches real data from free APIs — markets (yfinance), weather (Open-Meteo), waves (Open-Meteo Marine), news (RSS)
2. Sends everything to Claude with a prompt that writes each section in A2-level Italian
3. Injects the JSON response into `template.html` and writes `index.html`
4. Commits and pushes — GitHub Pages deploys automatically
5. Sends a Telegram message with the link

---

## File Structure

```
La-Mia-Carta/
  index.html              # live newspaper, regenerated daily by automation
  template.html           # base template with {{PLACEHOLDERS}} — never touched by automation
  generate.py             # content generation script
  requirements.txt        # Python dependencies
  .github/
    workflows/
      daily.yml           # runs at 6am PDT daily
  README.md
```

---

## Setup

### 1. GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional, for daily text) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (optional) |

### 2. GitHub Pages

Go to **Settings → Pages** and set:
- Source: Deploy from a branch
- Branch: `main` / `/ (root)`

### 3. Telegram Setup (for daily text message)

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token
2. Start a chat with your new bot
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat ID
4. Add both as GitHub secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)

### 4. Run Locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python generate.py
```

This writes a fresh `index.html`. Open it in a browser to preview.

---

## Sections

| Section | Source |
|---------|--------|
| Mercati | yfinance (S&P 500, Nasdaq, Bitcoin, EUR/USD) |
| Portogallo | Reuters RSS + Open-Meteo |
| AI e Strumenti | The Verge, Hacker News RSS |
| Cucina | Claude's knowledge of Italian cuisine |
| Mare e Onde | Open-Meteo Marine API (Hermosa Beach) |
| Viaggio | Lonely Planet RSS |
| Design e Architettura | Dezeen RSS |
| Musica e Cultura | Pitchfork RSS |
| Storie | Corriere della Sera RSS |
| Cruciverba | Generated from that day's articles |
| Parola del Giorno | One word buried naturally in an article |

---

## Adjusting the Schedule

Edit `.github/workflows/daily.yml`:

```yaml
- cron: '0 13 * * *'   # 6am PDT (UTC-7)
# change to '0 14 * * *' for 6am PST (UTC-8, winter
```

You can also trigger a manual run anytime from the **Actions** tab → **La Mia Carta — Edizione Quotidiana** → **Run workflow**.
