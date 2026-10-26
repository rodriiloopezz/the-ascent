"""
The Ascent – automatic news site
--------------------------------
Each run:
1. Collects news from RSS feeds (Google News searches + business feeds)
2. Claude Haiku scores the headlines, skipping stories already published
3. Claude Sonnet researches the best new stories on the web and writes full
   articles in English, Spanish and French, listing its sources
4. Claude draws a pixel-art illustration for each article (or Pexels photo)
5. New articles are added to data/articles.json (the site's memory)
6. The whole website is rebuilt in the folder site/

Run locally:  python ascent_news.py
Needs:        ANTHROPIC_API_KEY (in .env locally, or a GitHub secret online)
Optional:     PEXELS_API_KEY if IMAGE_MODE = "pexels"
"""

import base64
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import feedparser
from anthropic import Anthropic
from dotenv import load_dotenv

# ---------------------------------------------------------------- settings
SITE_NAME = "The Ascent"
FILTER_MODEL = "claude-haiku-5-5"   # cheap and fast: scoring many headlines
WRITER_MODEL = "claude-sonnet-5-5"  # researches and writes the full articles
MIN_SCORE = 7                       # 0-10, preferred minimum relevance
MAX_STORIES = 10                    # new stories per run (maximum)
MAX_PER_FEED = 15                   # items read from each feed
SEARCHES_PER_STORY = 6              # web searches Claude may run per story
PARALLEL_WRITERS = 2                # stories written at the same time
IMAGE_MODE = "pixel"                # "pixel", "pexels" or "none"
SUBSCRIBE_URL = ""                  # your newsletter signup page (Beehiiv, Ghost...). Empty = hidden
HOME_ARTICLES = 31                  # articles shown on the homepage
KEEP_ARTICLES = 400                 # articles kept in the archive

DATA_FILE = os.path.join("data", "articles.json")
SITE_DIR = "site"

SEARCHES = [
    "women CEO appointed",
    "female executives",
    "women leadership corporate",
    "gender pay gap",
    "board diversity women",
    "female founders funding",
    "women in finance",
    "parental leave policy companies",
]

EXTRA_FEEDS = [
    "https://feeds.bbci.co.uk/news/business/rss.xml",
]

AUDIENCE = (
    "Ambitious professional women (25-45) who want to grow into senior roles "
    "in the corporate world: managers, directors, executives, founders. "
    "They care about women in leadership, appointments, pay and equity, "
    "workplace policy, careers, funding for women-led companies, and big "
    "business moves that affect their careers."
)

CATEGORIES = ["Leadership", "Boards", "Money", "Policy", "Deals", "Workplace", "Careers"]

CATEGORY_LABELS = {
    "Leadership": {"en": "Leadership", "es": "Liderazgo", "fr": "Leadership"},
    "Boards": {"en": "Boards", "es": "Consejos", "fr": "Conseils"},
    "Money": {"en": "Money", "es": "Dinero", "fr": "Argent"},
    "Policy": {"en": "Policy", "es": "Políticas", "fr": "Politiques"},
    "Deals": {"en": "Deals", "es": "Operaciones", "fr": "Opérations"},
    "Workplace": {"en": "Workplace", "es": "Trabajo", "fr": "Travail"},
    "Careers": {"en": "Careers", "es": "Carrera", "fr": "Carrière"},
}

UI = {
    "tagline": {"en": "Corporate news for women who plan to run the room",
                "es": "Actualidad corporativa para mujeres que van a dirigir",
                "fr": "L'actualité corporate pour les femmes qui visent le sommet"},
    "latest": {"en": "Latest news", "es": "Últimas noticias", "fr": "Dernières actualités"},
    "read": {"en": "Read the full story", "es": "Leer la noticia completa", "fr": "Lire l'article complet"},
    "min": {"en": "min read", "es": "min de lectura", "fr": "min de lecture"},
    "key": {"en": "Key points", "es": "Claves", "fr": "Points clés"},
    "why": {"en": "Why it matters", "es": "Por qué importa", "fr": "Pourquoi c'est important"},
    "move": {"en": "Your move", "es": "Qué puedes hacer", "fr": "À vous de jouer"},
    "sources": {"en": "Sources", "es": "Fuentes", "fr": "Sources"},
    "back": {"en": "All news", "es": "Todas las noticias", "fr": "Toutes les actualités"},
    "photo": {"en": "Photo", "es": "Foto", "fr": "Photo"},
    "illustrative": {"en": "Illustrative image", "es": "Imagen ilustrativa", "fr": "Image d'illustration"},
    "ai_art": {"en": "Illustration created with AI", "es": "Ilustración creada con IA",
               "fr": "Illustration créée avec l'IA"},
    "ai_note": {"en": "Articles on The Ascent are researched and written with the help of AI, "
                      "based on the sources listed in each story.",
                "es": "Los artículos de The Ascent se investigan y redactan con ayuda de IA, "
                      "a partir de las fuentes citadas en cada noticia.",
                "fr": "Les articles de The Ascent sont recherchés et rédigés avec l'aide de l'IA, "
                      "à partir des sources citées dans chaque article."},
    "sub_title": {"en": "The Weekly Brief", "es": "The Weekly Brief", "fr": "The Weekly Brief"},
    "sub_text": {"en": "The week's essential corporate news for ambitious women, every Monday in your inbox.",
                 "es": "Lo esencial de la semana en el mundo corporativo, cada lunes en tu correo.",
                 "fr": "L'essentiel de la semaine corporate, chaque lundi dans votre boîte mail."},
    "sub_btn": {"en": "Subscribe", "es": "Suscríbete", "fr": "S'abonner"},
    "empty": {"en": "The first edition is on its way.", "es": "La primera edición está en camino.",
              "fr": "La première édition arrive bientôt."},
}

LANGS = ("en", "es", "fr")

# Fixed brand palette for the pixel art, so every illustration looks consistent
PIXEL_W, PIXEL_H = 48, 32
PALETTE = {
    ".": "#FBFAF7",  # paper (background)
    "s": "#EFEBE6",  # stone
    "l": "#D9D3CC",  # light grey
    "g": "#5F626B",  # grey
    "k": "#16171B",  # ink
    "r": "#7A1F3D",  # burgundy
    "p": "#C98A9B",  # rose
    "b": "#F2E3E7",  # blush
    "y": "#C9A45C",  # gold
    "n": "#2E4A62",  # navy
}


# ---------------------------------------------------------------- helpers
def google_news_url(query: str) -> str:
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def title_key(title: str) -> str:
    """Normalised headline used to spot stories we already published."""
    title = re.sub(r"\s+-\s+[^-]+$", "", title)  # drop " - Outlet" suffix
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:90]


def make_id(item: dict) -> str:
    return hashlib.sha1((item["link"] + item["title"]).encode()).hexdigest()[:10]


def extract_json(text: str, tag: str | None = None):
    if tag:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.S)
        if m:
            text = m.group(1)
    match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
    if not match:
        raise ValueError("No JSON found in model reply")
    return json.loads(match.group(1))


def ask(client: Anthropic, model: str, prompt: str, max_tokens: int = 4000) -> str:
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def ask_with_web(client: Anthropic, prompt: str) -> tuple[str, list[dict]]:
    """Ask Claude with web search enabled. Returns (text, sources)."""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": SEARCHES_PER_STORY}]
    text_parts, sources, seen = [], [], set()
    for _ in range(4):  # the API may pause long searches; continue up to 4 times
        resp = client.messages.create(
            model=WRITER_MODEL, max_tokens=8000, messages=messages, tools=tools
        )
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url and url not in seen:
                        seen.add(url)
                        sources.append({"url": url, "title": getattr(c, "title", "") or url})
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    return "".join(text_parts), sources


def pexels_photo(query: str) -> dict | None:
    key = os.getenv("PEXELS_API_KEY")
    if not key or not query:
        return None
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": 1, "orientation": "landscape"}
    )
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "TheAscent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        p = data["photos"][0]
        return {
            "src": p["src"].get("landscape") or p["src"]["large"],
            "alt": p.get("alt") or query,
            "photographer": p.get("photographer", ""),
            "page": p.get("url", "https://www.pexels.com"),
        }
    except Exception:
        return None


def pixel_art(client: Anthropic, headline: str, theme: str) -> dict | None:
    """Claude draws a small pixel-art illustration as a grid of colour codes; we turn it into SVG."""
    codes = ", ".join(f'"{c}" = {hexv}' for c, hexv in PALETTE.items())
    prompt = f"""You are the illustrator of "The Ascent", an elegant business magazine for women.
Draw a {PIXEL_W}x{PIXEL_H} pixel-art illustration for this article:
Headline: {headline}
Theme: {theme}

Style: refined, minimal, editorial pixel art. One clear, symbolic central subject
(e.g. a city skyline, a staircase going up, a briefcase, a boardroom table, a rising chart,
a woman's silhouette in a suit seen from behind). Generous empty background.
Use 3-5 colours, mostly paper/stone with burgundy or navy accents and a touch of gold.
No text, no letters, no logos, no recognisable real people, no faces with detail.

Colour codes you may use (and nothing else): {codes}

Output EXACTLY {PIXEL_H} rows, each EXACTLY {PIXEL_W} characters, only those codes,
inside <pixels></pixels> tags, and nothing else."""
    try:
        text = ask(client, WRITER_MODEL, prompt, max_tokens=3000)
        m = re.search(r"<pixels>(.*?)</pixels>", text, re.S)
        rows = [r.strip() for r in (m.group(1) if m else text).splitlines() if r.strip()]
        rows = [(r + "." * PIXEL_W)[:PIXEL_W] for r in rows][:PIXEL_H]
        rows += ["." * PIXEL_W] * (PIXEL_H - len(rows))
        rects = []
        for y, row in enumerate(rows):
            x = 0
            while x < PIXEL_W:  # merge runs of the same colour into one rectangle
                c = row[x] if row[x] in PALETTE else "."
                run = 1
                while x + run < PIXEL_W and (row[x + run] if row[x + run] in PALETTE else ".") == c:
                    run += 1
                if c != ".":
                    rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{PALETTE[c]}"/>')
                x += run
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PIXEL_W} {PIXEL_H}" '
               f'shape-rendering="crispEdges"><rect width="{PIXEL_W}" height="{PIXEL_H}" '
               f'fill="{PALETTE["."]}"/>{"".join(rects)}</svg>')
        return {"svg": svg, "alt": theme or headline}
    except Exception:
        return None


# ---------------------------------------------------------------- memory
def load_articles() -> list[dict]:
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_articles(articles: list[dict]) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(articles[:KEEP_ARTICLES], f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- step 1
def collect(published: list[dict]) -> list[dict]:
    known = {a["key"] for a in published} | {a["link"] for a in published}
    feeds = [google_news_url(q) for q in SEARCHES] + EXTRA_FEEDS
    seen, items = set(), []
    for url in feeds:
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:MAX_PER_FEED]:
            title = clean(entry.get("title", ""))
            link = entry.get("link", "")
            key = title_key(title)
            if not title or key in seen or key in known or link in known:
                continue
            seen.add(key)
            source = entry.get("source", {}).get("title", "") if entry.get("source") else ""
            items.append({
                "n": len(items),
                "title": title,
                "key": key,
                "source": source or parsed.feed.get("title", ""),
                "link": link,
                "published": entry.get("published", ""),
                "snippet": clean(entry.get("summary", ""))[:400],
            })
    print(f"[1/6] Collected {len(items)} new candidate stories")
    return items


# ---------------------------------------------------------------- step 2
def score(client: Anthropic, items: list[dict], published: list[dict]) -> list[dict]:
    recent = "\n".join(f"- {a['content']['en']['headline']}" for a in published[:60]) or "(none yet)"
    scored = []
    for start in range(0, len(items), 40):
        batch = items[start:start + 40]
        listing = "\n".join(f'{i["n"]}. {i["title"]} ({i["source"]})' for i in batch)
        prompt = f"""You are the news editor of "The Ascent", a news site for this audience:
{AUDIENCE}

Score each new headline from 0 to 10 for how much this audience would want it today.
10 = must-read for them; 0 = irrelevant. Penalise gossip and opinion pieces without news.
Score 0 any headline about the SAME event as one we already published (list below),
and for duplicates within the new list keep only the best one.
Pick one category from: {", ".join(CATEGORIES)}.

Already published recently:
{recent}

New headlines:
{listing}

Reply ONLY with a JSON array like:
[{{"id": 3, "score": 8, "category": "Leadership"}}]"""
        results = extract_json(ask(client, FILTER_MODEL, prompt))
        by_n = {i["n"]: i for i in batch}
        for r in results:
            item = by_n.get(r.get("id"))
            if item:
                item["score"] = r.get("score", 0)
                cat = r.get("category", "Leadership")
                item["category"] = cat if cat in CATEGORIES else "Leadership"
                scored.append(item)
    ranked = sorted(scored, key=lambda i: -i["score"])
    kept = [i for i in ranked if i["score"] >= MIN_SCORE]
    if len(kept) < MAX_STORIES:  # thin news day: allow slightly lower scores
        kept += [i for i in ranked if MIN_SCORE - 1 <= i["score"] < MIN_SCORE]
    kept = kept[:MAX_STORIES]
    print(f"[2/6] Selected {len(kept)} stories")
    return kept


# ---------------------------------------------------------------- step 3 + 4
def write_up(client: Anthropic, item: dict) -> dict:
    prompt = f"""You are a senior reporter at "The Ascent", a news site for this audience:
{AUDIENCE}

Story lead from our news feed:
Headline: {item["title"]}
Outlet: {item["source"]}
Snippet: {item["snippet"] or "(none)"}

1. Research this story with web search (up to {SEARCHES_PER_STORY} searches). Prefer reliable,
   original reporting (major newspapers, wire services, company press releases).
2. Write a complete, well-structured news article about it.

Editorial rules:
- Use ONLY facts you confirmed in your research. Never invent names, figures, dates or quotes.
  If something is unclear, leave it out.
- Write entirely in your own words and your own structure. Do not mirror any source's
  sentences or paragraph order. At most ONE short direct quote (under 15 words) per article,
  attributed to the person who said it.
- Tone: smart, warm, confident, like a top business magazine. No clichés, no hype.
- Spanish must be natural Spain Spanish and French natural France French, written as
  native articles, not literal translations. Use correct gendered job titles
  (e.g. "consejera delegada", "directrice générale").

After researching, output ONLY this JSON, wrapped in <article_json></article_json> tags:
{{
 "image_query": "2-4 English words describing a generic, symbolic image for the theme (no person names, no brands)",
 "en": {{
   "headline": "max 12 words",
   "dek": "one-sentence standfirst",
   "body": ["paragraph 1", "paragraph 2", "paragraph 3", "paragraph 4"],
   "key_points": ["point", "point", "point"],
   "why_it_matters": "2-3 sentences on what this means for an ambitious woman's career",
   "your_move": "one concrete, practical action the reader can take"
 }},
 "es": {{ same fields }},
 "fr": {{ same fields }}
}}
The body should have 4-6 paragraphs (about 300-400 words) when the research supports it."""
    text, sources = ask_with_web(client, prompt)
    data = extract_json(text, "article_json")
    for lang in LANGS:
        if lang not in data or not data[lang].get("headline"):
            raise ValueError(f"missing {lang} version")
    photo, art = None, None
    if IMAGE_MODE == "pexels":
        photo = pexels_photo(data.get("image_query", ""))
    elif IMAGE_MODE == "pixel":
        art = pixel_art(client, data["en"]["headline"], data.get("image_query", ""))
    words = sum(len(p.split()) for p in data["en"].get("body", []))
    return {
        "id": make_id(item),
        "key": item["key"],
        "link": item["link"],
        "source": item["source"],
        "category": item["category"],
        "score": item["score"],
        "published_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "minutes": max(2, round(words / 220)),
        "content": {l: data[l] for l in LANGS},
        "sources": sources[:8],
        "photo": photo,
        "art": art,
    }


# ---------------------------------------------------------------- step 6: website
def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def tri(values: dict, tag: str = "span", cls: str = "") -> str:
    """Render the same element in EN/ES/FR; CSS shows the selected language."""
    c = f' class="{cls}"' if cls else ""
    return "".join(f'<{tag}{c} data-l="{l}" lang="{l}">{esc(values.get(l, ""))}</{tag}>' for l in LANGS)


def field(a: dict, name: str) -> dict:
    return {l: a["content"][l].get(name, "") for l in LANGS}


def date_labels(iso: str) -> dict:
    try:
        d = datetime.fromisoformat(iso)
    except Exception:
        return {l: "" for l in LANGS}
    months = {
        "en": ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"],
        "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"],
        "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
               "septembre", "octobre", "novembre", "décembre"],
    }
    return {
        "en": f"{d.day} {months['en'][d.month - 1]} {d.year}",
        "es": f"{d.day} de {months['es'][d.month - 1]} de {d.year}",
        "fr": f"{d.day} {months['fr'][d.month - 1]} {d.year}",
    }


def image_html(a: dict, cls: str, prefix: str) -> str:
    if a.get("art"):
        return f'<img class="{cls} pixel" src="{prefix}img/{a["id"]}.svg" alt="{esc(a["art"]["alt"])}">'
    p = a.get("photo")
    if p:
        return f'<img class="{cls}" src="{esc(p["src"])}" alt="{esc(p["alt"])}" loading="lazy">'
    return f'<div class="{cls} ph" aria-hidden="true">{tri(CATEGORY_LABELS[a["category"]])}</div>'


def meta(a: dict) -> str:
    return (f'<p class="kicker">{tri(CATEGORY_LABELS[a["category"]])}'
            f'<span class="dot">·</span><span class="muted">{a["minutes"]} {tri(UI["min"])}</span></p>')


def subscribe_band() -> str:
    if not SUBSCRIBE_URL:
        return ""
    return f"""
<section class="subscribe"><div class="wrap sub-inner">
  <div>
    <p class="sub-kicker">{tri(UI["sub_title"])}</p>
    <p class="sub-text">{tri(UI["sub_text"])}</p>
  </div>
  <a class="cta light" href="{esc(SUBSCRIBE_URL)}" target="_blank" rel="noopener">{tri(UI["sub_btn"])} <span aria-hidden="true">→</span></a>
</div></section>"""


def page(title: str, body: str, prefix: str, desc: str = "") -> str:
    return f"""<!doctype html>
<html lang="en" translate="no">
<head>
<meta charset="utf-8">
<meta name="google" content="notranslate">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or UI['tagline']['en'])}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc or UI['tagline']['en'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}style.css">
</head>
<body data-lang="en">
<div class="topbar"><div class="wrap">
  <a class="home-link" href="{prefix}index.html">{SITE_NAME}<span>.</span></a>
  <div class="langs" role="group" aria-label="Language">
    <button type="button" data-set="en" aria-pressed="true">EN</button>
    <button type="button" data-set="es" aria-pressed="false">ES</button>
    <button type="button" data-set="fr" aria-pressed="false">FR</button>
  </div>
</div></div>
{body}
{subscribe_band()}
<footer class="wrap">
  <span class="logo-sm">{SITE_NAME}.</span>
  <p>{tri(UI["tagline"])}</p>
  <p class="ai-note">{tri(UI["ai_note"])}</p>
</footer>
<script src="{prefix}app.js"></script>
</body>
</html>"""


CSS = """
:root {
  --ink:#16171B; --paper:#FBFAF7; --muted:#5F626B; --line:#E6E1DC;
  --accent:#7A1F3D; --blush:#F5ECEE; --stone:#EFEBE6;
  --serif:'Cormorant Garamond', Georgia, 'Times New Roman', serif;
  --sans:Inter, system-ui, -apple-system, 'Segoe UI', sans-serif;
}
* { box-sizing:border-box; }
html { -webkit-text-size-adjust:100%; }
body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans); line-height:1.6; }
body:not([data-lang="en"]) [data-l="en"],
body:not([data-lang="es"]) [data-l="es"],
body:not([data-lang="fr"]) [data-l="fr"] { display:none !important; }
a { color:var(--accent); } a:hover { color:var(--ink); }
.wrap { max-width:1180px; margin:0 auto; padding:0 24px; }
.muted { color:var(--muted); }

.topbar { border-bottom:1px solid var(--line); }
.topbar .wrap { display:flex; justify-content:space-between; align-items:center; gap:16px; min-height:56px; }
.home-link { font-family:var(--serif); font-weight:600; font-size:24px; color:var(--ink); text-decoration:none; }
.home-link span, .logo span { color:var(--accent); }
.langs { display:flex; gap:4px; }
.langs button { font:inherit; min-width:44px; min-height:40px; border:0; border-radius:999px; background:none; cursor:pointer;
  font-size:12px; font-weight:600; letter-spacing:.08em; color:var(--muted); }
.langs button[aria-pressed="true"] { background:var(--ink); color:#fff; }

.masthead { text-align:center; padding:48px 0 32px; border-bottom:1px solid var(--ink); }
.logo { font-family:var(--serif); font-weight:600; font-size:clamp(52px, 9vw, 104px); line-height:1; letter-spacing:-.02em; margin:0; }
.tagline { margin:14px 0 0; font-family:var(--serif); font-style:italic; font-size:clamp(18px, 2.4vw, 22px); color:var(--muted); }
.edition-date { margin:10px 0 0; font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }

.lead { display:grid; grid-template-columns:minmax(0, 1.35fr) minmax(0, 1fr); gap:48px; align-items:center;
  padding:48px 0; border-bottom:1px solid var(--line); }
.lead a.img-link { display:block; }
.lead-img { width:100%; aspect-ratio:4/3; object-fit:cover; display:block; border-radius:2px; }
.lead-title { font-family:var(--serif); font-weight:600; font-size:clamp(34px, 4.4vw, 56px); line-height:1.05;
  letter-spacing:-.01em; margin:10px 0 16px; }
.lead-title a, .card h3 a { color:inherit; text-decoration:none; }
.lead-title a:hover, .card h3 a:hover { color:var(--accent); }
.dek { font-size:18px; color:var(--muted); margin:0 0 24px; }
.cta { display:inline-flex; gap:8px; align-items:center; min-height:48px; padding:0 24px; border-radius:999px;
  background:var(--accent); color:#fff; font-weight:600; font-size:15px; text-decoration:none; }
.cta:hover { background:var(--ink); color:#fff; }
.kicker { margin:0; font-size:12px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); }
.kicker .dot { margin:0 8px; color:var(--muted); }

.section-title { display:flex; align-items:center; gap:16px; margin:48px 0 28px; font-family:var(--serif); font-weight:600; font-size:32px; }
.section-title::after { content:""; flex:1; height:1px; background:var(--line); }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:44px 32px; padding-bottom:72px; }
.card { display:flex; flex-direction:column; gap:12px; }
.card-img { width:100%; aspect-ratio:3/2; object-fit:cover; display:block; border-radius:2px; transition:opacity .2s; }
.card a.img-link:hover .card-img { opacity:.88; }
.card h3 { font-family:var(--serif); font-weight:600; font-size:26px; line-height:1.15; margin:0; }
.card-dek { margin:0; color:var(--muted); font-size:15px; }
.pixel { image-rendering:pixelated; background:#FBFAF7; }
.ph { display:flex; align-items:center; justify-content:center; background:var(--stone); font-family:var(--serif);
  font-style:italic; font-size:28px; color:var(--muted); }
.empty { text-align:center; padding:96px 0; font-family:var(--serif); font-size:28px; color:var(--muted); }

.story { max-width:780px; margin:0 auto; padding:40px 24px 72px; }
.back { display:inline-block; margin-bottom:24px; font-size:14px; font-weight:600; text-decoration:none; }
.story h1 { font-family:var(--serif); font-weight:600; font-size:clamp(36px, 5.4vw, 60px); line-height:1.05; margin:12px 0 16px; }
.story .dek { font-size:20px; }
.byline { font-size:13px; color:var(--muted); margin:0 0 28px; padding-bottom:20px; border-bottom:1px solid var(--line); }
.story-img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; border-radius:2px; }
.credit { margin:8px 0 32px; font-size:12px; color:var(--muted); }
.credit a { color:var(--muted); }
.body p { font-size:19px; line-height:1.75; margin:0 0 22px; }
.body div > p:first-child::first-letter { float:left; font-family:var(--serif); font-weight:600; font-size:68px;
  line-height:.85; padding:6px 10px 0 0; color:var(--accent); }
.box { border-top:1px solid var(--ink); padding:20px 0 4px; margin-top:32px; }
.box.accent { background:var(--blush); border-top:0; padding:24px 28px; border-radius:2px; }
.box h2, .src-title { margin:0 0 10px; font-size:12px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); }
.box p, .box li { font-size:17px; margin:0 0 8px; }
.box ul { margin:0; padding-left:20px; }
.src-title { margin-top:40px; }
.sources { margin:0; padding-left:20px; font-size:14px; }
.sources li { margin-bottom:6px; word-break:break-word; }

.subscribe { background:var(--ink); color:#fff; }
.sub-inner { display:flex; flex-wrap:wrap; gap:24px; align-items:center; justify-content:space-between; padding-top:48px; padding-bottom:48px; }
.sub-kicker { margin:0 0 6px; font-family:var(--serif); font-weight:600; font-size:34px; }
.sub-text { margin:0; color:#C9CBD1; max-width:560px; }
.cta.light { background:#fff; color:var(--ink); }
.cta.light:hover { background:var(--blush); color:var(--ink); }

footer { border-top:1px solid var(--ink); padding:32px 24px 48px; text-align:center; color:var(--muted); font-size:13px; }
footer p { margin:4px 0; }
footer .logo-sm { font-family:var(--serif); font-weight:600; font-size:28px; color:var(--ink); display:block; margin-bottom:6px; }
.ai-note { max-width:560px; margin:12px auto 0 !important; font-size:12px; }

@media (max-width: 820px) {
  .lead { grid-template-columns:1fr; gap:24px; padding:32px 0; }
  .grid { grid-template-columns:1fr; gap:40px; }
  .wrap { padding:0 16px; }
  .story { padding:28px 16px 56px; }
  .body p { font-size:18px; }
}
"""

JS = """
function setLang(l) {
  document.body.dataset.lang = l;
  document.documentElement.lang = l;
  document.querySelectorAll('.langs button').forEach(function (b) {
    b.setAttribute('aria-pressed', b.dataset.set === l);
  });
  try { localStorage.setItem('ascent-lang', l); } catch (e) {}
}
document.querySelectorAll('.langs button').forEach(function (b) {
  b.addEventListener('click', function () { setLang(b.dataset.set); });
});
try {
  var saved = localStorage.getItem('ascent-lang');
  if (saved) setLang(saved);
} catch (e) {}
"""


def build_article_page(a: dict) -> str:
    body = "".join(
        f'<div data-l="{l}" lang="{l}">' + "".join(f"<p>{esc(p)}</p>" for p in a["content"][l].get("body", [])) + "</div>"
        for l in LANGS
    )
    keys = "".join(
        f'<ul data-l="{l}" lang="{l}">' + "".join(f"<li>{esc(k)}</li>" for k in a["content"][l].get("key_points", [])) + "</ul>"
        for l in LANGS
    )
    srcs = "".join(f'<li><a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["title"])}</a></li>'
                   for x in a.get("sources", []))
    if not srcs:
        srcs = f'<li><a href="{esc(a["link"])}" target="_blank" rel="noopener">{esc(a["source"])}</a></li>'
    credit = ""
    if a.get("art"):
        credit = f'<p class="credit">{tri(UI["ai_art"])}</p>'
    elif a.get("photo"):
        p = a["photo"]
        credit = (f'<p class="credit">{tri(UI["illustrative"])} · {tri(UI["photo"])}: '
                  f'<a href="{esc(p["page"])}" target="_blank" rel="noopener">{esc(p["photographer"])} / Pexels</a></p>')
    html_body = f"""
<main class="story">
  <a class="back" href="../index.html">← {tri(UI["back"])}</a>
  <article>
    {meta(a)}
    <h1>{tri(field(a, "headline"))}</h1>
    <p class="dek">{tri(field(a, "dek"))}</p>
    <p class="byline">{tri(date_labels(a["published_at"]))}</p>
    {image_html(a, "story-img", "../")}
    {credit or '<div style="height:32px"></div>'}
    <div class="body">{body}</div>
    <aside class="box"><h2>{tri(UI["key"])}</h2>{keys}</aside>
    <aside class="box accent"><h2>{tri(UI["why"])}</h2><p>{tri(field(a, "why_it_matters"))}</p></aside>
    <aside class="box"><h2>{tri(UI["move"])}</h2><p>{tri(field(a, "your_move"))}</p></aside>
    <h2 class="src-title">{tri(UI["sources"])}</h2>
    <ul class="sources">{srcs}</ul>
  </article>
</main>"""
    en = a["content"]["en"]
    return page(f'{en["headline"]} — {SITE_NAME}', html_body, "../", en.get("dek", ""))


def build_home(articles: list[dict]) -> str:
    masthead = f"""
<header class="wrap masthead">
  <h1 class="logo">{SITE_NAME}<span>.</span></h1>
  <p class="tagline">{tri(UI["tagline"])}</p>
  {f'<p class="edition-date">{tri(date_labels(articles[0]["published_at"]))}</p>' if articles else ""}
</header>"""
    if not articles:
        return page(SITE_NAME, masthead + f'<main class="wrap"><p class="empty">{tri(UI["empty"])}</p></main>', "")

    lead, rest = articles[0], articles[1:HOME_ARTICLES]
    url = f'article/{lead["id"]}.html'
    lead_html = f"""
<section class="lead">
  <a class="img-link" href="{url}" tabindex="-1" aria-hidden="true">{image_html(lead, "lead-img", "")}</a>
  <div>
    {meta(lead)}
    <h2 class="lead-title"><a href="{url}">{tri(field(lead, "headline"))}</a></h2>
    <p class="dek">{tri(field(lead, "dek"))}</p>
    <a class="cta" href="{url}">{tri(UI["read"])} <span aria-hidden="true">→</span></a>
  </div>
</section>"""
    cards = "".join(f"""
<article class="card">
  <a class="img-link" href="article/{a["id"]}.html" tabindex="-1" aria-hidden="true">{image_html(a, "card-img", "")}</a>
  {meta(a)}
  <h3><a href="article/{a["id"]}.html">{tri(field(a, "headline"))}</a></h3>
  <p class="card-dek">{tri(field(a, "dek"))}</p>
</article>""" for a in rest)
    grid = f'<h2 class="section-title">{tri(UI["latest"])}</h2><div class="grid">{cards}</div>' if rest else ""
    return page(f"{SITE_NAME} — {UI['tagline']['en']}", masthead + f'<main class="wrap">{lead_html}{grid}</main>', "")


def build_site(articles: list[dict]) -> None:
    if os.path.isdir(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(os.path.join(SITE_DIR, "article"))
    os.makedirs(os.path.join(SITE_DIR, "img"))
    with open(os.path.join(SITE_DIR, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    with open(os.path.join(SITE_DIR, "app.js"), "w", encoding="utf-8") as f:
        f.write(JS)
    with open(os.path.join(SITE_DIR, ".nojekyll"), "w") as f:
        f.write("")
    for a in articles:
        if a.get("art"):
            with open(os.path.join(SITE_DIR, "img", f'{a["id"]}.svg'), "w", encoding="utf-8") as f:
                f.write(a["art"]["svg"])
        with open(os.path.join(SITE_DIR, "article", f'{a["id"]}.html'), "w", encoding="utf-8") as f:
            f.write(build_article_page(a))
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_home(articles))
    print(f"[6/6] Website built in '{SITE_DIR}/' with {len(articles)} articles")


# ---------------------------------------------------------------- main
def main() -> None:
    load_dotenv()
    published = load_articles()

    if "--build-only" in sys.argv:  # rebuild the site without fetching news
        build_site(published)
        return

    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY. Put it in a .env file next to this script.")
    client = Anthropic(max_retries=5)

    items = collect(published)
    new_articles = []
    if items:
        selected = score(client, items, published)

        def work(pair):
            n, item = pair
            try:
                art = write_up(client, item)
                print(f"[3-4/6] Wrote {n}/{len(selected)}: {item['title'][:70]}")
                return art
            except Exception as e:  # one bad story shouldn't stop the run
                print(f"      Skipped one story ({e})")
                return None

        with ThreadPoolExecutor(max_workers=PARALLEL_WRITERS) as pool:
            new_articles = [a for a in pool.map(work, enumerate(selected, 1)) if a]

    articles = new_articles + published  # newest first
    save_articles(articles)
    print(f"[5/6] Added {len(new_articles)} new articles (total {len(articles)})")
    build_site(articles[:KEEP_ARTICLES])


if __name__ == "__main__":
    main()
