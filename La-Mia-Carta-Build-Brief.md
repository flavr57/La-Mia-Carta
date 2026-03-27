# La Mia Carta -- Build Brief for Claude Code

## What This Is
A daily personalized morning newspaper hosted on GitHub Pages. It generates fresh content every morning at 6am PT, written entirely in A2-level Italian. It's not a language lesson -- it's a real newspaper I happen to read in Italian. Delivery is a text message with a link each morning.

## Repo
- GitHub username: flavr57
- Repo: La-Mia-Carta (already exists at github.com/flavr57/La-Mia-Carta)
- GitHub Pages: enabled, deploys from main branch
- Live URL: flavr57.github.io/La-Mia-Carta
- Local path: /Users/flavr_24/Documents/GitHub/La-Mia-Carta
- There is already an index.html template in the repo with the full design. DO NOT change the visual design, fonts, colors, or layout. Use it as the template and inject content into it.

## Daily Generation Flow
Every morning a GitHub Actions workflow runs at 6am PT that does this:

1. Pull real data from free sources (no paid APIs):
   - Market data (S&P 500, Nasdaq, Bitcoin, EUR/USD) -- use a free finance API or scrape Yahoo Finance
   - Surf forecast for Hermosa Beach / South Bay LA -- use Surfline RSS or free surf API
   - Weather for Hermosa Beach -- use Open-Meteo (free, no key needed)
   - Weather for Lisbon, Portugal (for the Portugal section)
   - News via RSS feeds (see sources below)

2. Send all that raw data to the Anthropic Claude API with a prompt that:
   - Writes every section in A2-level Italian (simple vocabulary, short sentences, present tense preferred, no subjunctive)
   - Maintains a newspaper editorial tone, not a textbook tone
   - Picks ONE daily word and buries it naturally in one of the articles (not at the top, not labeled as "word of the day"). The word gets a dotted underline and a hover tooltip with the English translation
   - Generates a small crossword puzzle (5x7 grid or similar) where the words come from that day's articles
   - Writes crossword clues in Italian
   - Returns structured JSON with all sections filled

3. Inject the JSON content into the index.html template
4. Commit and push to main branch
5. GitHub Pages auto-deploys
6. Send me a text message with the link

## Sections and Content Sources

### Mercati (Markets)
- S&P 500, Nasdaq, Bitcoin, EUR/USD
- Current value, percent change, one-line context in Italian
- Source: Yahoo Finance API, Alpha Vantage free tier, or similar

### Portogallo (Portugal Watch)
- News relevant to Portugal, especially Lisbon area
- My son Kai lives there, so this matters to me
- If nothing significant: show the green checkmark with "Niente di importante oggi. Tutto tranquillo."
- If something fires: headline and brief summary
- Also include Lisbon weather
- Source: Reuters RSS, Portugal news RSS, Open-Meteo for weather

### AI e Strumenti (AI & Tools)
- New AI tools, workflow automation, anything relevant to a solo creative operator
- Prioritize practical tools over research papers
- Source: Hacker News RSS, The Verge AI RSS, TechCrunch AI RSS

### Cucina (Cooking)
- One Italian recipe or cooking story per day
- Written as a short narrative, not a recipe card with measurements
- The feel should be like a nonna telling you how to make something
- Source: Italian cooking blogs RSS, or have Claude generate from its knowledge of Italian cuisine

### Mare e Onde (Surf & Ocean)
- Hermosa Beach / El Porto / South Bay surf forecast
- Swell direction, wave height, wind, best time to go out
- Can include one global surf story if interesting
- Source: Surfline RSS, NOAA buoy data, free surf APIs

### Viaggio (Travel)
- Italy-focused travel content, off-the-beaten-path preferred
- Source: travel RSS feeds, Lonely Planet Italy RSS

### Design e Architettura (Design & Architecture)
- Architecture, interior design, creative spaces, brand design
- Source: Dezeen RSS, ArchDaily RSS, Designboom RSS

### Musica e Cultura (Music & Culture)
- Italian music, culture, festivals, art
- Source: Italian culture RSS, music blogs

### Storie (Human Interest)
- This should be the longest, most engaging section
- One compelling human story, preferably Italian or Mediterranean
- The Antonio the boatbuilder story in the template is the vibe
- Source: Corriere della Sera RSS, La Repubblica RSS, or Claude-generated in that style based on real stories from RSS

### Cruciverba del Giorno (Daily Crossword)
- Small grid (5x7 or similar, keep it doable in 5-10 minutes)
- Words pulled from that day's articles
- Clues written in Italian
- Interactive: typing in one cell advances to the next
- The crossword HTML structure is already in the template

### Parola del Giorno (Daily Word)
- NOT a separate section. Pick one interesting Italian word from the day's content and mark it with the "parola" class in whichever article it naturally appears in
- Hover/tap shows English translation
- Template already has the CSS for this

## Weather Bar
- Hermosa Beach temp, conditions, wave height, water temp
- Source: Open-Meteo, free surf data

## Text Message Delivery
- Use email-to-SMS via carrier gateway (e.g., 5551234567@vtext.com for Verizon)
- Or use a free Telegram bot if that's simpler to set up in GitHub Actions
- Message content: "La Mia Carta -- [today's date in Italian]" with the link
- I'll provide my phone number and carrier separately

## GitHub Actions Secrets Needed
- ANTHROPIC_API_KEY (for Claude API to generate content)
- Delivery method credentials (phone number, carrier gateway, or Telegram bot token)
- Any API keys for market data if needed

## Technical Notes
- Use Claude's API (model: claude-sonnet-4-20250514) for content generation to keep costs low
- The template uses Google Fonts loaded from CDN -- keep those
- The index.html in the repo IS the template. The generation script should read it, inject content, and write the updated version back
- Keep the footer quote -- rotate through famous Italian quotes daily
- All dates should be in Italian (Lunedi, Martedi, Mercoledi, etc.)
- The generation script can be Python or Node, whatever works cleanest with GitHub Actions

## What NOT To Do
- Don't change the visual design, CSS, fonts, or layout of the existing template
- Don't make this feel like a language learning app. It's a newspaper
- Don't put the daily word at the top or label it prominently
- Don't use complex Italian. A2 level means: present tense, common vocabulary, short sentences, passato prossimo for past events
- Don't require any paid APIs other than the Anthropic API

## File Structure Expected
```
La-Mia-Carta/
  index.html          (the live newspaper, regenerated daily)
  template.html       (the base template, never modified by automation)
  generate.py         (or generate.js -- the content generation script)
  .github/
    workflows/
      daily.yml       (GitHub Actions workflow, runs at 6am PT)
  README.md
```

## First Step
Move the current index.html to template.html (this preserves the design). Then build the generate script that reads the template, fills it with content, and outputs a new index.html. Test it once manually before setting up the cron schedule.
