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
    "ad": {"en": "Advertisement", "es": "Publicidad", "fr": "Publicité"},
    "ad_cta": {"en": "Your brand here — advertise with us", "es": "Tu marca aquí — anúnciate con nosotros",
               "fr": "Votre marque ici — annoncez chez nous"},
    "empty": {"en": "The first edition is on its way.", "es": "La primera edición está en camino.",
              "fr": "La première édition arrive bientôt."},
}

LANGS = ("en", "es", "fr")

# Fixed brand palette for the pixel art, so every illustration looks consistent
PIXEL_W, PIXEL_H = 60, 40
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
    "t": "#2F6F6A",  # teal
    "o": "#C4643F",  # terracotta
    "c": "#9CC3D5",  # sky
    "v": "#7E9A6A",  # sage
    "w": "#E7B9A0",  # peach
}

# One colour per section, used for labels and accents across the site
CATEGORY_COLORS = {
    "Leadership": "#7A1F3D",  # burgundy
    "Boards": "#2E4A62",      # navy
    "Money": "#A87E2E",       # deep gold
    "Policy": "#2F6F6A",      # teal
    "Deals": "#B4532F",       # terracotta
    "Workplace": "#6B4E8C",   # plum
    "Careers": "#3F6B4A",     # forest
}

# ---------------------------------------------------------------- advertising
ADS_ENABLED = True       # show advertising spaces
ADSENSE_CLIENT = ""      # e.g. "ca-pub-1234567890" once Google AdSense approves the site
ADVERTISE_URL = ""       # page or email link for brands that want to advertise (e.g. "mailto:ads@...")
AD_EVERY_N_CARDS = 6     # one ad among the homepage cards every N stories


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
    """Claude composes the illustration from simple shapes; we rasterise them into pixel art.
    Working with shapes (instead of typing every pixel) means the drawing always comes out complete."""
    codes = ", ".join(f'"{c}" = {hexv}' for c, hexv in PALETTE.items())
    prompt = f"""You are the illustrator of "The Ascent", an elegant business magazine for women.
Compose a pixel-art illustration for this article on a {PIXEL_W}x{PIXEL_H} pixel canvas
(x from 0 to {PIXEL_W}, y from 0 to {PIXEL_H}, origin top-left):
Headline: {headline}
Theme: {theme}

Style: refined, warm, editorial pixel art. One clear symbolic subject (e.g. a city skyline at dusk,
a staircase going up, a briefcase on a desk, a boardroom table, a rising chart, a woman's silhouette
in a suit seen from behind, a podium, an open door, a key). Fill the WHOLE canvas: a coloured
background (sky, wall or floor), a ground line, the subject, and a few details (windows, sun, plants,
shadows, highlights). Use 5-7 colours: soft background, rich accents (burgundy, navy, teal,
terracotta, sage) and a touch of gold. No text, letters, logos or recognisable real people.

Colour codes (use only these): {codes}

Describe the picture as shapes, drawn in order (later shapes go on top). Use 20-60 shapes.
Shape types:
 {{"t":"rect","x":0,"y":0,"w":10,"h":5,"c":"n"}}
 {{"t":"circle","x":30,"y":10,"r":4,"c":"y"}}
 {{"t":"poly","p":[[0,40],[20,25],[40,40]],"c":"v"}}
 {{"t":"line","x1":0,"y1":30,"x2":60,"y2":30,"w":1,"c":"k"}}

Reply ONLY with JSON inside <shapes></shapes> tags:
<shapes>{{"bg":"c","shapes":[ ... ]}}</shapes>"""
    for attempt in range(1, 4):  # up to 3 tries
        try:
            return _draw(client, prompt, theme or headline)
        except Exception as e:
            print(f"      Illustration attempt {attempt} failed: {e}")
    return None


def _inside_poly(px: float, py: float, pts: list) -> bool:
    inside, j = False, len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def rasterise(spec: dict) -> list[list[str]]:
    def col(c):
        return c if c in PALETTE else None

    grid = [[col(spec.get("bg")) or "." for _ in range(PIXEL_W)] for _ in range(PIXEL_H)]
    for s in spec.get("shapes", []):
        c = col(s.get("c"))
        if not c:
            continue
        t = s.get("t")
        try:
            if t == "rect":
                x0, y0 = round(float(s["x"])), round(float(s["y"]))
                x1, y1 = x0 + round(float(s["w"])), y0 + round(float(s["h"]))
                for y in range(max(0, y0), min(PIXEL_H, y1)):
                    for x in range(max(0, x0), min(PIXEL_W, x1)):
                        grid[y][x] = c
            elif t == "circle":
                cx, cy, r = float(s["x"]), float(s["y"]), float(s["r"])
                for y in range(PIXEL_H):
                    for x in range(PIXEL_W):
                        if (x + .5 - cx) ** 2 + (y + .5 - cy) ** 2 <= r * r:
                            grid[y][x] = c
            elif t == "poly":
                pts = [(float(a), float(b)) for a, b in s["p"]]
                if len(pts) < 3:
                    continue
                for y in range(PIXEL_H):
                    for x in range(PIXEL_W):
                        if _inside_poly(x + .5, y + .5, pts):
                            grid[y][x] = c
            elif t == "line":
                x1, y1, x2, y2 = (float(s[k]) for k in ("x1", "y1", "x2", "y2"))
                w = max(1, round(float(s.get("w", 1))))
                steps = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
                for i in range(steps + 1):
                    px = x1 + (x2 - x1) * i / steps
                    py = y1 + (y2 - y1) * i / steps
                    for dy in range(w):
                        for dx in range(w):
                            gx, gy = int(px) + dx - w // 2, int(py) + dy - w // 2
                            if 0 <= gx < PIXEL_W and 0 <= gy < PIXEL_H:
                                grid[gy][gx] = c
        except (KeyError, TypeError, ValueError):
            continue  # skip a malformed shape, keep the rest
    return grid


def grid_to_svg(grid: list[list[str]]) -> str:
    rects = []
    for y, row in enumerate(grid):
        x = 0
        while x < PIXEL_W:  # merge runs of the same colour into one rectangle
            c, run = row[x], 1
            while x + run < PIXEL_W and row[x + run] == c:
                run += 1
            rects.append(f'<rect x="{x}" y="{y}" width="{run}" height="1" fill="{PALETTE[c]}"/>')
            x += run
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PIXEL_W} {PIXEL_H}" '
            f'shape-rendering="crispEdges">{"".join(rects)}</svg>')


def _draw(client: Anthropic, prompt: str, alt: str) -> dict:
    text = ask(client, WRITER_MODEL, prompt, max_tokens=6000)
    spec = extract_json(text, "shapes")
    if len(spec.get("shapes", [])) < 6:
        raise ValueError("too few shapes in the drawing")
    grid = rasterise(spec)
    if len({c for row in grid for c in row}) < 3:
        raise ValueError("the drawing came out almost empty")
    return {"svg": grid_to_svg(grid), "alt": alt}


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
        "image_query": data.get("image_query", ""),
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
    return (f'<div class="{cls} ph" style="--cat:{cat_color(a)}" aria-hidden="true">'
            f'{tri(CATEGORY_LABELS[a["category"]])}</div>')


def cat_color(a: dict) -> str:
    return CATEGORY_COLORS.get(a["category"], "#7A1F3D")


def meta(a: dict) -> str:
    return (f'<p class="kicker"><span class="pill" style="background:{cat_color(a)}">'
            f'{tri(CATEGORY_LABELS[a["category"]])}</span>'
            f'<span class="muted">{a["minutes"]} {tri(UI["min"])}</span></p>')


def ad_slot(kind: str) -> str:
    """kind: 'leader' (wide banner), 'card' (in the news grid), 'rail' (article sidebar), 'inline'."""
    if not ADS_ENABLED:
        return ""
    if ADSENSE_CLIENT:
        inner = (f'<ins class="adsbygoogle" style="display:block" data-ad-client="{esc(ADSENSE_CLIENT)}" '
                 f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
                 f'<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>')
    else:
        link = (f'<a href="{esc(ADVERTISE_URL)}">{tri(UI["ad_cta"])}</a>' if ADVERTISE_URL
                else f'<span>{tri(UI["ad_cta"])}</span>')
        inner = f'<div class="ad-house"><span class="ad-logo">{SITE_NAME}.</span>{link}</div>'
    return (f'<aside class="ad ad-{kind}" aria-label="Advertisement">'
            f'<span class="ad-label">{tri(UI["ad"])}</span><div class="ad-box">{inner}</div></aside>')


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


def side_rails() -> str:
    """Two tall ads in the empty side margins (only visible on wide screens)."""
    if not ADS_ENABLED:
        return ""
    return (f'<div class="side-rail left">{ad_slot("sky")}</div>'
            f'<div class="side-rail right">{ad_slot("sky")}</div>')


def adsense_head() -> str:
    if not (ADS_ENABLED and ADSENSE_CLIENT):
        return ""
    return (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client={esc(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>')


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
{adsense_head()}
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
{side_rails()}
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
  --ink:#16171B; --paper:#F4E4E2; --muted:#5C5A60; --line:#E2C9C6; --granate:#6E1630;
  --accent:#7A1F3D; --accent-dark:#5A1229; --blush:#FBF1EF; --stone:#EBD5D2;
  --navy:#2E4A62; --gold:#C9A45C; --sky:#E6F0F5; --peach:#FBEDE4;
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

/* top bar */
.topbar { background:var(--accent); color:#fff; }
.topbar .wrap { display:flex; justify-content:space-between; align-items:center; gap:16px; min-height:56px; }
.home-link { font-family:var(--serif); font-weight:600; font-size:24px; color:#fff; text-decoration:none; }
.home-link:hover { color:#F5D7DF; }
.home-link span { color:var(--gold); }
.langs { display:flex; gap:4px; }
.langs button { font:inherit; min-width:44px; min-height:40px; border:0; border-radius:999px; background:none; cursor:pointer;
  font-size:12px; font-weight:600; letter-spacing:.08em; color:#F5D7DF; }
.langs button[aria-pressed="true"] { background:#fff; color:var(--accent); }

/* masthead */
.masthead { text-align:center; padding:52px 24px 36px; }
.logo { font-family:var(--serif); font-weight:600; font-size:clamp(52px, 9vw, 104px); line-height:1; letter-spacing:-.02em; margin:0; }
.logo { color:var(--granate); }
.logo span { color:var(--gold); }
.tagline { margin:14px 0 0; font-family:var(--serif); font-style:italic; font-size:clamp(18px, 2.4vw, 22px); color:var(--muted); }
.edition-date { display:inline-block; margin:18px 0 0; padding:6px 14px; border-radius:999px; background:#fff;
  font-size:12px; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--accent); }
.rule { height:6px; background:linear-gradient(90deg, #7A1F3D 0 25%, #2E4A62 25% 50%, #C9A45C 50% 75%, #2F6F6A 75% 100%); }

/* lead story */
.lead-band { background:var(--granate); color:#fff; }
.lead-band .dek { color:#F1D3DA; }
.lead-band .muted { color:#E9C3CC; }
.lead-band .cta { background:var(--gold); color:var(--ink); }
.lead-band .cta:hover { background:#fff; color:var(--granate); }
.lead-band .lead-title a:hover { color:#F5D7DF; }
.lead-band .pill { background:#fff !important; color:var(--granate); }
.lead { display:grid; grid-template-columns:minmax(0, 1.35fr) minmax(0, 1fr); gap:48px; align-items:center; padding-top:52px; padding-bottom:52px; }
.lead a.img-link { display:block; }
.lead-img { width:100%; aspect-ratio:4/3; object-fit:cover; display:block; border-radius:4px; box-shadow:12px 12px 0 var(--gold); }
.lead-title { font-family:var(--serif); font-weight:600; font-size:clamp(34px, 4.4vw, 56px); line-height:1.05;
  letter-spacing:-.01em; margin:14px 0 16px; }
.lead-title a, .card h3 a { color:inherit; text-decoration:none; }
.lead-title a:hover, .card h3 a:hover { color:var(--cat, var(--accent)); }
.dek { font-size:18px; color:var(--muted); margin:0 0 24px; }
.cta { display:inline-flex; gap:8px; align-items:center; min-height:48px; padding:0 24px; border-radius:999px;
  background:var(--accent); color:#fff; font-weight:600; font-size:15px; text-decoration:none; }
.cta:hover { background:var(--ink); color:#fff; }

/* labels */
.kicker { margin:0; display:flex; flex-wrap:wrap; align-items:center; gap:10px; font-size:11px; font-weight:600;
  letter-spacing:.12em; text-transform:uppercase; }
.pill { display:inline-block; padding:5px 11px; border-radius:999px; color:#fff; }

/* news grid */
.section-title { display:flex; align-items:center; gap:16px; margin:56px 0 28px; font-family:var(--serif); font-weight:600; font-size:34px; color:var(--granate); }
.section-title::after { content:""; flex:1; height:2px; background:linear-gradient(90deg, var(--granate), transparent); }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:44px 32px; padding-bottom:72px; }
.card { display:flex; flex-direction:column; gap:12px; border-top:4px solid var(--cat); padding-top:16px; }
.card-img { width:100%; aspect-ratio:3/2; object-fit:cover; display:block; border-radius:4px; transition:transform .25s; }
.card a.img-link { display:block; overflow:hidden; border-radius:4px; }
.card a.img-link:hover .card-img { transform:scale(1.03); }
.card h3 { font-family:var(--serif); font-weight:600; font-size:26px; line-height:1.15; margin:0; }
.card-dek { margin:0; color:var(--muted); font-size:15px; }
.pixel { image-rendering:pixelated; background:var(--stone); }
.ph { display:flex; align-items:center; justify-content:center; background:var(--cat, var(--stone)); font-family:var(--serif);
  font-style:italic; font-size:28px; color:#fff; }
.empty { text-align:center; padding:96px 0; font-family:var(--serif); font-size:28px; color:var(--muted); }

/* advertising */
.ad { display:flex; flex-direction:column; gap:6px; }
.ad-label { font-size:10px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }
.ad-box { display:flex; align-items:center; justify-content:center; background:var(--blush); border:1px dashed #C99AA5;
  border-radius:4px; text-align:center; padding:16px; }
.ad-house { display:flex; flex-direction:column; gap:6px; align-items:center; font-size:14px; color:var(--granate); }
.ad-house a { color:var(--granate); font-weight:600; }
.ad-logo { font-family:var(--serif); font-weight:600; font-size:22px; color:var(--granate); }
.ad-leader { margin:40px auto 0; max-width:970px; }
.ad-leader .ad-box { min-height:110px; }
.ad-card .ad-box { aspect-ratio:3/2; height:auto; }
.ad-card { border-top:4px solid #C99AA5; padding-top:16px; }
.ad-inline { margin:12px 0 8px; }
.ad-inline .ad-box { min-height:250px; }
.ad-rail .ad-box { min-height:600px; }
.side-rail { display:none; position:fixed; top:150px; width:160px; z-index:1; }
.side-rail .ad-box { min-height:600px; padding:12px; }
.side-rail.left { left:calc(50% - 590px - 196px); }
.side-rail.right { right:calc(50% - 590px - 196px); }
body:has(.story-layout) .side-rail.right { display:none !important; }

/* article page */
.story-layout { max-width:1180px; margin:0 auto; display:flex; gap:56px; padding:0 24px; justify-content:center; }
.story { flex:0 1 780px; min-width:0; padding:40px 0 72px; }
.rail { display:none; flex:0 0 300px; padding-top:96px; }
.rail .ad { position:sticky; top:24px; }
.back { display:inline-block; margin-bottom:24px; font-size:14px; font-weight:600; text-decoration:none; }
.story h1 { color:var(--granate); font-family:var(--serif); font-weight:600; font-size:clamp(36px, 5.4vw, 60px); line-height:1.05; margin:14px 0 16px; }
.story .dek { font-size:20px; }
.byline { font-size:13px; color:var(--muted); margin:0 0 28px; padding-bottom:20px; border-bottom:2px solid var(--granate); }
.story-img { width:100%; aspect-ratio:16/9; object-fit:cover; display:block; border-radius:4px; }
.credit { margin:8px 0 32px; font-size:12px; color:var(--muted); }
.credit a { color:var(--muted); }
.body p { font-size:19px; line-height:1.75; margin:0 0 22px; }
.body div > p:first-child::first-letter { float:left; font-family:var(--serif); font-weight:600; font-size:68px;
  line-height:.85; padding:6px 10px 0 0; color:var(--cat); }
.box { padding:24px 28px; margin-top:28px; border-radius:4px; }
.box.keys { background:#fff; }
.box.accent { background:var(--granate); color:#fff; }
.box.accent h2 { color:var(--gold) !important; }
.box.move { background:var(--blush); }
.box h2, .src-title { margin:0 0 10px; font-size:12px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); }
.box.keys h2 { color:var(--navy); }
.box.move h2 { color:#9A4A26; }
.box p, .box li { font-size:17px; margin:0 0 8px; }
.box ul { margin:0; padding-left:20px; }
.src-title { margin-top:40px; }
.sources { margin:0; padding-left:20px; font-size:14px; }
.sources li { margin-bottom:6px; word-break:break-word; }

/* newsletter + footer */
.subscribe { background:#4A0E20; color:#fff; }
.sub-inner { display:flex; flex-wrap:wrap; gap:24px; align-items:center; justify-content:space-between; padding-top:52px; padding-bottom:52px; }
.sub-kicker { margin:0 0 6px; font-family:var(--serif); font-weight:600; font-size:36px; }
.sub-text { margin:0; color:#EBC9D2; max-width:560px; }
.cta.light { background:var(--gold); color:var(--ink); }
.cta.light:hover { background:#fff; color:var(--ink); }
footer { background:var(--ink); color:#B8BAC1; padding:40px 24px 52px; text-align:center; font-size:13px; max-width:none !important; }
footer p { margin:4px 0; }
footer .logo-sm { font-family:var(--serif); font-weight:600; font-size:30px; color:#fff; display:block; margin-bottom:6px; }
.ai-note { max-width:560px; margin:14px auto 0 !important; font-size:12px; color:#8E9199; }

@media (min-width: 1600px) {
  .side-rail { display:block; }
}
@media (min-width: 1200px) {
  .rail { display:block; }
  .ad-inline { display:none; }
}
@media (max-width: 820px) {
  .lead { grid-template-columns:1fr; gap:28px; padding-top:32px; padding-bottom:40px; }
  .lead-img { box-shadow:8px 8px 0 var(--gold); }
  .grid { grid-template-columns:1fr; gap:40px; }
  .wrap { padding:0 16px; }
  .story-layout { padding:0 16px; }
  .story { padding:28px 0 56px; }
  .body p { font-size:18px; }
  .box { padding:20px; }
  .ad-leader { margin-top:28px; }
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
<div class="story-layout" style="--cat:{cat_color(a)}">
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
    {ad_slot("inline")}
    <aside class="box keys"><h2>{tri(UI["key"])}</h2>{keys}</aside>
    <aside class="box accent"><h2>{tri(UI["why"])}</h2><p>{tri(field(a, "why_it_matters"))}</p></aside>
    <aside class="box move"><h2>{tri(UI["move"])}</h2><p>{tri(field(a, "your_move"))}</p></aside>
    <h2 class="src-title">{tri(UI["sources"])}</h2>
    <ul class="sources">{srcs}</ul>
  </article>
</main>
{('<div class="rail">' + ad_slot("rail") + '</div>') if ADS_ENABLED else ""}
</div>"""
    en = a["content"]["en"]
    return page(f'{en["headline"]} — {SITE_NAME}', html_body, "../", en.get("dek", ""))


def build_home(articles: list[dict]) -> str:
    masthead = f"""
<header class="wrap masthead">
  <h1 class="logo">{SITE_NAME}<span>.</span></h1>
  <p class="tagline">{tri(UI["tagline"])}</p>
  {f'<p class="edition-date">{tri(date_labels(articles[0]["published_at"]))}</p>' if articles else ""}
</header>
<div class="rule"></div>"""
    if not articles:
        return page(SITE_NAME, masthead + f'<main class="wrap"><p class="empty">{tri(UI["empty"])}</p></main>', "")

    lead, rest = articles[0], articles[1:HOME_ARTICLES]
    url = f'article/{lead["id"]}.html'
    lead_html = f"""
<section class="lead-band" style="--cat:{cat_color(lead)}"><div class="wrap lead">
  <a class="img-link" href="{url}" tabindex="-1" aria-hidden="true">{image_html(lead, "lead-img", "")}</a>
  <div>
    {meta(lead)}
    <h2 class="lead-title"><a href="{url}">{tri(field(lead, "headline"))}</a></h2>
    <p class="dek">{tri(field(lead, "dek"))}</p>
    <a class="cta" href="{url}">{tri(UI["read"])} <span aria-hidden="true">→</span></a>
  </div>
</div></section>"""
    parts = []
    for n, a in enumerate(rest, 1):
        parts.append(f"""
<article class="card" style="--cat:{cat_color(a)}">
  <a class="img-link" href="article/{a["id"]}.html" tabindex="-1" aria-hidden="true">{image_html(a, "card-img", "")}</a>
  {meta(a)}
  <h3><a href="article/{a["id"]}.html">{tri(field(a, "headline"))}</a></h3>
  <p class="card-dek">{tri(field(a, "dek"))}</p>
</article>""")
        if n % AD_EVERY_N_CARDS == 0 and n < len(rest):
            parts.append(ad_slot("card"))
    grid = f'<h2 class="section-title">{tri(UI["latest"])}</h2><div class="grid">{"".join(parts)}</div>' if rest else ""
    leader = f'<div class="wrap">{ad_slot("leader")}</div>' if ADS_ENABLED else ""
    return page(f"{SITE_NAME} — {UI['tagline']['en']}",
                masthead + lead_html + leader + f'<main class="wrap">{grid}</main>', "")


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

    if "--redraw" in sys.argv or "--redraw-all" in sys.argv:  # illustrations only, no new news
        redraw_all = "--redraw-all" in sys.argv
        missing = [a for a in published if IMAGE_MODE == "pixel" and (redraw_all or not a.get("art"))]
        print(f"Redrawing {len(missing)} missing illustrations...")
        for a in missing:
            a["art"] = pixel_art(client, a["content"]["en"]["headline"], a.get("image_query", ""))
            print("   ok" if a["art"] else "   still failed", "-", a["content"]["en"]["headline"][:60])
        save_articles(published)
        build_site(published)
        return

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
