"""
Madam CEO – automatic news site
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

import community
import game
import legal
import social

# ---------------------------------------------------------------- settings
SITE_NAME = "Madam CEO"
SITE_URL = "https://themadamceo.com"
FILTER_MODEL = "claude-haiku-5-5"   # cheap and fast: scoring many headlines
WRITER_MODEL = "claude-sonnet-5-5"  # researches and writes the full articles
MIN_SCORE = 7                       # 0-10, preferred minimum relevance
MAX_STORIES = 10                    # new stories per run (maximum)
MAX_PER_FEED = 15                   # items read from each feed
SEARCHES_PER_STORY = 6              # web searches Claude may run per story
PARALLEL_WRITERS = 2                # stories written at the same time
IMAGE_MODE = "pixel"                # "pixel", "pexels" or "none"
# News about specific people or companies keeps pixel art (a symbolic image never suggests a real person).
# General topics use a real stock photo, labelled as illustrative. Falls back to pixel art if no photo.
# Every category now uses a photo of the story's TOPIC (never of the person named in it).
PHOTO_CATEGORIES = {"Leadership", "Boards", "Deals", "Money", "Workplace", "Careers", "Policy", "Style"}
USED_PHOTOS: set = set()   # avoid repeating the same photo across stories
SUBSCRIBE_URL = ""                  # your newsletter signup page (Beehiiv, Ghost...). Empty = hidden
HOME_ARTICLES = 31                  # articles shown on the homepage
KEEP_ARTICLES = 400                 # articles kept in the archive

DATA_FILE = os.path.join("data", "articles.json")
STYLE_FILE = os.path.join("data", "style.json")
STYLE_EVERY_DAYS = 7                # a new Style guide every N days
STYLE_MIN_GUIDES = 3                # the Style section always has at least this many guides
STYLE_IMAGE_MODE = "photos"         # "photos" = real fashion photos from Unsplash (UNSPLASH_ACCESS_KEY) or Pexels
                                    # (PEXELS_API_KEY); "vector" = Claude illustration. With "photos", an illustration
                                    # is drawn automatically when no key is set or no photo is found.

# Evergreen office-style topics; Claude writes one guide per topic, in order, then starts over
STYLE_TOPICS = [
    "The capsule work wardrobe: 10 pieces that make 30 outfits",
    "What to wear to a job interview, from corporate to creative",
    "Dressing for your first board or executive meeting",
    "Business casual decoded: what it really means",
    "The perfect blazer: fit, fabric and how to style it",
    "Power colours: what to wear when you need to be heard",
    "Hybrid work: looking polished on camera and in the office",
    "Comfortable shoes that still look executive",
    "The work bag: what to look for and what to carry",
    "Dressing for a conference where you are speaking",
    "Client dinner: from desk to evening with one swap",
    "Summer in the office: staying cool and professional",
    "Winter layering for the commute and the boardroom",
    "Business travel: packing a week of outfits in a carry-on",
    "Accessories that add authority: watches, jewellery and scarves",
    "Building a professional wardrobe on a tight budget",
    "Dressing for a promotion: dress for the role you want",
    "Maternity workwear that stays sharp",
    "Smart casual Fridays without looking underdressed",
    "Investment pieces worth saving for",
    "Caring for your work clothes so they last for years",
    "Tailoring: small alterations that transform an outfit",
    "Personal style at work: standing out while fitting in",
    "Dressing for a networking event",
]
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
    "tagline": {"en": "News for the next woman in charge",
                "es": "Noticias para la próxima mujer al mando",
                "fr": "L'actualité de la prochaine femme aux commandes"},
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
    "ai_note": {"en": "Articles on Madam CEO are researched and written with the help of AI, "
                      "based on the sources listed in each story.",
                "es": "Los artículos de Madam CEO se investigan y redactan con ayuda de IA, "
                      "a partir de las fuentes citadas en cada noticia.",
                "fr": "Les articles de Madam CEO sont recherchés et rédigés avec l'aide de l'IA, "
                      "à partir des sources citées dans chaque article."},
    "sub_title": {"en": "The Weekly Brief", "es": "The Weekly Brief", "fr": "The Weekly Brief"},
    "sub_text": {"en": "The week's essential corporate news for ambitious women, every Monday in your inbox.",
                 "es": "Lo esencial de la semana en el mundo corporativo, cada lunes en tu correo.",
                 "fr": "L'essentiel de la semaine corporate, chaque lundi dans votre boîte mail."},
    "sub_btn": {"en": "Subscribe", "es": "Suscríbete", "fr": "S'abonner"},
    "ad": {"en": "Advertisement", "es": "Publicidad", "fr": "Publicité"},
    "privacy_settings": {"en": "Privacy settings", "es": "Configuración de privacidad", "fr": "Paramètres de confidentialité"},
    "ad_cta": {"en": "Your brand here — advertise with us", "es": "Tu marca aquí — anúnciate con nosotros",
               "fr": "Votre marque ici — annoncez chez nous"},
    "nav_news": {"en": "News", "es": "Noticias", "fr": "Actualités"},
    "nav_style": {"en": "Style", "es": "Estilo", "fr": "Style"},
    "nav_game": {"en": "Power Word", "es": "Power Word", "fr": "Power Word"},
    "style_title": {"en": "Office Style", "es": "Estilo de oficina", "fr": "Style au bureau"},
    "style_sub": {"en": "A weekly guide to dressing for the job you want",
                  "es": "Una guía semanal para vestir para el puesto que quieres",
                  "fr": "Un guide hebdomadaire pour s'habiller pour le poste que vous visez"},
    "essentials": {"en": "The essentials", "es": "Imprescindibles", "fr": "Les essentiels"},
    "do": {"en": "Do", "es": "Sí", "fr": "À faire"},
    "dont": {"en": "Don't", "es": "No", "fr": "À éviter"},
    "tip": {"en": "Smart tip", "es": "Consejo", "fr": "Astuce"},
    "lookbook": {"en": "The lookbook", "es": "Inspiración", "fr": "Le lookbook"},
    "trends": {"en": "On the radar: what's next", "es": "En el radar: lo que viene", "fr": "Dans le viseur : ce qui arrive"},
    "shops": {"en": "Where to shop", "es": "Dónde comprar", "fr": "Où acheter"},
    "tier_affordable": {"en": "Affordable", "es": "Asequible", "fr": "Abordable"},
    "tier_mid": {"en": "Mid-range", "es": "Gama media", "fr": "Milieu de gamme"},
    "tier_premium": {"en": "Premium", "es": "Premium", "fr": "Premium"},
    "shops_note": {"en": "Shops selected independently by our editors from current research. Availability varies by country.",
                   "es": "Tiendas seleccionadas de forma independiente a partir de nuestra investigación. La disponibilidad varía según el país.",
                   "fr": "Boutiques sélectionnées en toute indépendance à partir de nos recherches. La disponibilité varie selon le pays."},
    "all_style": {"en": "All style guides", "es": "Todas las guías de estilo", "fr": "Tous les guides de style"},
    "game_sub": {"en": "Guess today's business word in six tries",
                 "es": "Adivina la palabra empresarial del día en seis intentos",
                 "fr": "Devinez le mot business du jour en six essais"},
    "game_num": {"en": "Puzzle", "es": "Reto", "fr": "Défi"},
    "game_teaser": {"en": "A new five-letter business word every day. How fast can you crack it?",
                    "es": "Una palabra empresarial de cinco letras cada día. ¿Cuánto tardarás en descubrirla?",
                    "fr": "Un nouveau mot business de cinq lettres chaque jour. Saurez-vous le trouver ?"},
    "play": {"en": "Play today's word", "es": "Jugar al reto de hoy", "fr": "Jouer au défi du jour"},
    "enter": {"en": "Enter", "es": "Enviar", "fr": "Valider"},
    "how_title": {"en": "How to play", "es": "Cómo se juega", "fr": "Comment jouer"},
    "how_text": {"en": "Type any five-letter word and press Enter. The tiles change colour to show how close you are.",
                 "es": "Escribe una palabra de cinco letras en inglés y pulsa Enviar. Las casillas cambian de color para indicarte lo cerca que estás.",
                 "fr": "Tapez un mot anglais de cinq lettres et validez. Les cases changent de couleur pour indiquer si vous êtes proche."},
    "hit": {"en": "Right letter, right spot", "es": "Letra correcta en su sitio", "fr": "Bonne lettre, bonne place"},
    "near": {"en": "In the word, wrong spot", "es": "Está en la palabra, en otro sitio", "fr": "Dans le mot, mauvaise place"},
    "miss": {"en": "Not in the word", "es": "No está en la palabra", "fr": "Absente du mot"},
    "word_means": {"en": "What it means", "es": "Qué significa", "fr": "Ce que ça veut dire"},
    "played": {"en": "Played", "es": "Jugadas", "fr": "Parties"},
    "wins": {"en": "Win rate", "es": "Aciertos", "fr": "Réussite"},
    "streak": {"en": "Streak", "es": "Racha", "fr": "Série"},
    "best": {"en": "Best", "es": "Mejor", "fr": "Record"},
    "share": {"en": "Share result", "es": "Compartir resultado", "fr": "Partager"},
    "comeback": {"en": "A new word arrives tomorrow.", "es": "Mañana habrá una palabra nueva.", "fr": "Un nouveau mot arrive demain."},
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
ADSENSE_CLIENT = "ca-pub-9142746258845789"
ADSENSE_APPROVED = False  # set to True once Google approves the site; until then the spaces show house ads
# Optional: ad unit IDs created in AdSense (Ads → By ad unit), one per space; empty = keep the house ad there
AD_SLOT_IDS = {"leader": "", "card": "", "inline": "", "rail": "", "sky": ""}
ADVERTISE_URL = "/advertise.html"  # page for brands that want to advertise
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


def ask_with_web(client: Anthropic, prompt: str, max_tokens: int = 8000) -> tuple[str, list[dict]]:
    """Ask Claude with web search enabled. Returns (text, sources)."""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": SEARCHES_PER_STORY}]
    text_parts, sources, seen = [], [], set()
    for _ in range(4):  # the API may pause long searches; continue up to 4 times
        resp = client.messages.create(
            model=WRITER_MODEL, max_tokens=max_tokens, messages=messages, tools=tools
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
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "MadamCEO/1.0"})
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


def pexels_photos(query: str, n: int = 3, orientation: str = "landscape", skip: set | None = None) -> list[dict]:
    """Several licensed Pexels photos for one search (free for commercial use)."""
    key = os.getenv("PEXELS_API_KEY")
    if not key or not query:
        return []
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": max(n * 3, 10), "orientation": orientation})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "MadamCEO/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            photos = json.load(r).get("photos", [])
    except Exception as e:
        print(f"      Pexels search failed ({e})")
        return []
    out = []
    if skip is None:
        skip = set()
    for p in photos:
        if p["id"] in skip:
            continue
        skip.add(p["id"])
        src = p["src"].get(orientation) or p["src"]["large"]
        out.append({"id": p["id"], "src": src, "alt": p.get("alt") or query,
                    "photographer": p.get("photographer", ""), "page": p.get("url", "https://www.pexels.com"),
                    "provider": "Pexels", "provider_url": "https://www.pexels.com"})
        if len(out) == n:
            break
    return out


UNSPLASH_LEFT: int | None = None  # requests left this hour (from Unsplash headers)


def unsplash_photos(query: str, n: int = 1, orientation: str = "landscape", skip: set | None = None) -> list[dict]:
    """Licensed Unsplash photos. Follows the API guidelines: hotlinked URLs, photographer + Unsplash
    credit with referral links, and a 'download' ping for each photo we use."""
    key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not key or not query:
        return []
    headers = {"Authorization": f"Client-ID {key}", "Accept-Version": "v1", "User-Agent": "MadamCEO/1.0"}
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
        {"query": query, "per_page": max(n * 3, 10), "orientation": "portrait" if orientation == "portrait" else "landscape",
         "content_filter": "high"})
    global UNSPLASH_LEFT
    if UNSPLASH_LEFT is not None and UNSPLASH_LEFT < 3:
        return []  # hourly limit almost reached: stop and try again next run
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
            left = r.headers.get("X-Ratelimit-Remaining")
            UNSPLASH_LEFT = int(left) if left and left.isdigit() else UNSPLASH_LEFT
            results = json.load(r).get("results", [])
    except Exception as e:
        print(f"      Unsplash search failed ({e})")
        return []
    utm = "utm_source=madam_ceo&utm_medium=referral"
    out = []
    if skip is None:
        skip = set()
    for p in results:
        if p["id"] in skip:
            continue
        skip.add(p["id"])
        try:  # tell Unsplash the photo is being used (required by their guidelines)
            urllib.request.urlopen(urllib.request.Request(p["links"]["download_location"], headers=headers), timeout=10).read()
        except Exception:
            pass
        user = p.get("user", {})
        out.append({
            "id": p["id"],
            "src": p["urls"]["regular"],
            "alt": p.get("alt_description") or query,
            "photographer": user.get("name", ""),
            "page": f'{user.get("links", {}).get("html", "https://unsplash.com")}?{utm}',
            "provider": "Unsplash",
            "provider_url": f"https://unsplash.com/?{utm}",
        })
        if len(out) == n:
            break
    return out


def stock_photos(query: str, n: int = 1, orientation: str = "landscape", skip: set | None = None) -> list[dict]:
    """Unsplash first, then Pexels, depending on which key is configured."""
    return unsplash_photos(query, n, orientation, skip) or pexels_photos(query, n, orientation, skip)


SVG_ALLOWED = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
               "defs", "linearGradient", "radialGradient", "stop", "clipPath", "title", "desc"}


def sanitise_svg(svg: str) -> str:
    """Keep only plain drawing elements and attributes (no scripts, links, external files or text)."""
    import xml.etree.ElementTree as ET
    ns = "{http://www.w3.org/2000/svg}"
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.fromstring(svg)

    def walk(el):
        for child in list(el):
            tag = child.tag.replace(ns, "")
            if tag not in SVG_ALLOWED:
                el.remove(child)
                continue
            for attr in list(child.attrib):
                low = attr.lower()
                val = child.attrib[attr].lower()
                if low.startswith("on") or "href" in low or "javascript:" in val or "url(http" in val:
                    del child.attrib[attr]
            walk(child)

    if root.tag.replace(ns, "") != "svg":
        raise ValueError("not an svg")
    for attr in list(root.attrib):
        if attr.lower().startswith("on") or "href" in attr.lower():
            del root.attrib[attr]
    walk(root)
    return ET.tostring(root, encoding="unicode")


def vector_art(client: Anthropic, headline: str, theme: str) -> dict | None:
    """Claude draws an elegant flat fashion illustration as SVG."""
    palette = "burgundy #7A1F3D, deep burgundy #4A0E20, blush #F2E3E7, rose #C98A9B, gold #C9A45C, " \
              "navy #2E4A62, camel #C8A27A, cream #FBF6F1, ink #16171B, sage #7E9A6A"
    prompt = f"""You are the fashion illustrator of "{SITE_NAME}", an elegant magazine for professional women.
Draw an editorial fashion illustration for this style guide:
Headline: {headline}
Theme: {theme}

Style: modern flat vector fashion illustration, like a high-end magazine. Elegant, slender stylised figures
or flat-lay arrangements of clothes and accessories, simple faceless or minimal faces, clean shapes,
soft shadows made with darker shades, a softly coloured background with a few decorative shapes.
Use this palette: {palette}. No text, no letters, no logos, no brands, no real people.

Technical: a single <svg> with viewBox="0 0 600 400" and xmlns="http://www.w3.org/2000/svg".
Only use path, rect, circle, ellipse, line, polyline, polygon, g, linearGradient, radialGradient, stop.
No text, image, script, style, filter or external references. Make it rich: 40-150 elements.
Reply with ONLY the svg inside <svg_art></svg_art> tags."""
    for attempt in range(1, 4):
        try:
            text = ask(client, WRITER_MODEL, prompt, max_tokens=16000)
            m = re.search(r"<svg_art>\s*(<svg.*?</svg>)\s*</svg_art>", text, re.S) or re.search(r"(<svg.*?</svg>)", text, re.S)
            if not m:
                raise ValueError("no svg in the reply")
            svg = sanitise_svg(m.group(1))
            if svg.count("<") < 25:
                raise ValueError("illustration too simple")
            return {"svg": svg, "alt": theme or headline, "kind": "vector"}
        except Exception as e:
            print(f"      Fashion illustration attempt {attempt} failed: {e}")
    return None


def style_images(client: Anthropic, data: dict) -> dict:
    """Cover photo, lookbook gallery and one photo per essential piece (or an illustration as fallback)."""
    if STYLE_IMAGE_MODE == "photos" and (os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("PEXELS_API_KEY")):
        queries = data.get("photo_queries") or [data.get("image_query", "")]
        seen: set = set()
        hero = stock_photos(queries[0], 1, "landscape", seen)
        if hero:
            gallery = stock_photos(queries[1] if len(queries) > 1 else queries[0], 4, "portrait", seen)
            essential_photos = []
            for q in (data.get("essential_queries") or [])[:5]:
                found = stock_photos(q, 1, "portrait", seen)
                essential_photos.append(found[0] if found else None)
            return {"photo": hero[0], "gallery": gallery, "essential_photos": essential_photos, "art": None}
        print("      No photo found; drawing an illustration instead")
    return {"photo": None, "gallery": [], "essential_photos": [],
            "art": vector_art(client, data["en"]["headline"], data.get("image_query", ""))}


def pixel_art(client: Anthropic, headline: str, theme: str) -> dict | None:
    """Claude composes the illustration from simple shapes; we rasterise them into pixel art.
    Working with shapes (instead of typing every pixel) means the drawing always comes out complete."""
    codes = ", ".join(f'"{c}" = {hexv}' for c, hexv in PALETTE.items())
    prompt = f"""You are the illustrator of "Madam CEO", an elegant business magazine for women.
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
        prompt = f"""You are the news editor of "Madam CEO", a news site for this audience:
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
def news_image(client: Anthropic, category: str, headline: str, image_query: str, photo_query: str):
    """Returns (photo, pixel_art) following the rule above."""
    if category in PHOTO_CATEGORIES and (os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("PEXELS_API_KEY")):
        for q in [x for x in (photo_query, image_query) if x]:
            found = stock_photos(q, 1, "landscape", USED_PHOTOS)
            if found:
                return found[0], None
    if IMAGE_MODE == "pixel":
        return None, pixel_art(client, headline, image_query)
    return None, None


def topic_query(client: Anthropic, headline: str, dek: str) -> str:
    """For older articles: a person-free stock-photo search about the story's topic."""
    try:
        r = client.messages.create(model=FILTER_MODEL, max_tokens=60, messages=[{"role": "user", "content":
            f"News headline: {headline}\nStandfirst: {dek}\n\nReply with ONLY 3-6 English words to search a stock "
            "photo of this story's topic, sector or setting (objects, buildings, places). Never a person's name, "
            "a brand or a face. Example: 'bank headquarters glass building'."}])
        return r.content[0].text.strip().strip('"').strip("'")[:80]
    except Exception:
        return ""


def write_up(client: Anthropic, item: dict) -> dict:
    prompt = f"""You are a senior reporter at "Madam CEO", a news site for this audience:
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
 "photo_query": "3-6 English words for a stock photo of the story's TOPIC, SECTOR or SETTING, never of a person named in it. Think of objects and places: a CEO appointment at a bank -> 'bank headquarters glass building'; an airline board -> 'airplane wing sunrise'; a pay-gap law -> 'parliament chamber'; a merger -> 'city skyline financial district'. No names, no brands, no faces as the subject.",
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
    photo, art = news_image(client, item["category"], data["en"]["headline"],
                            data.get("image_query", ""), data.get("photo_query", ""))
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
        "photo_query": data.get("photo_query", ""),
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
        px = "" if a["art"].get("kind") == "vector" else " pixel"
        return f'<img class="{cls}{px}" src="{prefix}img/{a["id"]}.svg" alt="{esc(a["art"]["alt"])}">'
    p = a.get("photo")
    if p:
        return f'<img class="{cls}" src="{esc(p["src"])}" alt="{esc(p["alt"])}" loading="lazy">'
    if str(a.get("id", "")).startswith("s"):
        return f'<div class="{cls} ph" style="--cat:var(--gold)" aria-hidden="true">{tri(UI["nav_style"])}</div>'
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
    slot = AD_SLOT_IDS.get(kind, "") if ADSENSE_APPROVED else ""
    if ADSENSE_CLIENT and slot:
        inner = (f'<ins class="adsbygoogle" style="display:block" data-ad-client="{esc(ADSENSE_CLIENT)}" '
                 f'data-ad-slot="{esc(slot)}" '
                 f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
                 f'<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>')
    else:
        link = (f'<a href="{esc(ADVERTISE_URL)}">{tri(UI["ad_cta"])}</a>' if ADVERTISE_URL
                else f'<span>{tri(UI["ad_cta"])}</span>')
        inner = f'<div class="sp-house"><span class="sp-logo">{SITE_NAME}.</span>{link}</div>'
    return (f'<aside class="sp sp-{kind}" aria-label="Sponsored space">'
            f'<span class="sp-tag">{tri(UI["ad"])}</span><div class="sp-box">{inner}</div></aside>')


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
    return (f'<div class="side-col left">{ad_slot("sky")}</div>'
            f'<div class="side-col right">{ad_slot("sky")}</div>')


def adsense_head() -> str:
    if not ADSENSE_CLIENT:
        return ""
    verify = f'<meta name="google-adsense-account" content="{esc(ADSENSE_CLIENT)}">'
    if not ADS_ENABLED:
        return verify
    return verify + (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            f'?client={esc(ADSENSE_CLIENT)}" crossorigin="anonymous"></script>')


def page(title: str, body: str, prefix: str, desc: str = "", extra_head: str = "", extra_js: str = "") -> str:
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
<meta property="og:image" content="{SITE_URL}/og-image.png">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#7A1F3D">
<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
<link rel="icon" href="{prefix}favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}style.css">
{extra_head}
{adsense_head()}
</head>
<body data-lang="en">
<div class="topbar"><div class="wrap">
  <a class="home-link" href="{prefix}index.html"><img class="brand-mark" src="{prefix}logo-light.svg" alt="" width="34" height="34"><span>{SITE_NAME}<span class="dot-gold">.</span></span></a>
  <nav class="nav" aria-label="Sections">
    <a href="{prefix}index.html">{tri(UI["nav_news"])}</a>
    <a href="{prefix}style/index.html">{tri(UI["nav_style"])}</a>
    <a href="{prefix}game/index.html">{tri(UI["nav_game"])}</a>
    <a href="{prefix}voices/index.html">{tri(community.UI["nav"])}</a>
  </nav>
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
  <span class="logo-sm"><img src="{prefix}logo-light.svg" alt="" width="40" height="40"><span>{SITE_NAME}.</span></span>
  <p>{tri(UI["tagline"])}</p>
  <p class="ai-note">{tri(UI["ai_note"])}</p>
  <nav class="foot-links" aria-label="Information">
    {"".join(f'<a href="{prefix}{slug}.html">{tri(legal.PAGES[slug]["title"])}</a>' for slug in legal.FOOTER_ORDER)}
    {f'<button type="button" class="privacy-btn">{tri(UI["privacy_settings"])}</button>' if ADSENSE_CLIENT else ""}
  </nav>
</footer>
<script src="{prefix}app.js"></script>
{extra_js}
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
.home-link .dot-gold { color:var(--gold); }
.langs { display:flex; gap:4px; }
.langs button { font:inherit; min-width:44px; min-height:40px; border:0; border-radius:999px; background:none; cursor:pointer;
  font-size:12px; font-weight:600; letter-spacing:.08em; color:#F5D7DF; }
.langs button[aria-pressed="true"] { background:#fff; color:var(--accent); }

/* section navigation */
.topbar .wrap { flex-wrap:wrap; }
.nav { display:flex; gap:4px; margin-right:auto; margin-left:24px; }
.nav a { color:#F5D7DF; text-decoration:none; font-size:14px; font-weight:600; padding:10px 12px; border-radius:999px; }
.nav a:hover { background:rgba(255,255,255,.12); color:#fff; }
@media (max-width: 640px) {
  .nav { order:3; width:100%; margin:0 0 8px; justify-content:space-between; }
  .nav a { padding:8px 10px; font-size:13px; }
}

/* home: style + game strip */
.extras { display:grid; grid-template-columns:minmax(0, 2fr) minmax(0, 1fr); gap:32px; margin:56px 0 0; }
.extras-style { background:#fff; border-radius:6px; padding:28px; }
.extras-style h2, .page-head h1 { font-family:var(--serif); font-weight:600; color:var(--granate); margin:0; }
.extras-style h2 { font-size:32px; }
.mini-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:20px; margin-top:20px; }
.mini { display:flex; flex-direction:column; gap:8px; text-decoration:none; color:var(--ink); }
.mini img { width:100%; aspect-ratio:3/2; object-fit:cover; border-radius:4px; }
.mini span { font-family:var(--serif); font-weight:600; font-size:19px; line-height:1.2; }
.mini:hover span { color:var(--granate); }
.extras-game { background:var(--granate); color:#fff; border-radius:6px; padding:28px; display:flex; flex-direction:column; gap:14px; justify-content:center; }
.extras-game h2 { margin:0; font-family:var(--serif); font-weight:600; font-size:34px; }
.extras-game p { margin:0; color:#F1D3DA; }
.mini-tiles { display:flex; gap:6px; }
.mini-tiles i { width:34px; height:34px; border-radius:4px; display:flex; align-items:center; justify-content:center; font-style:normal; font-weight:700; color:#fff; }
.extras-game .cta { background:var(--gold); color:var(--ink); align-self:flex-start; }
.extras-game .cta:hover { background:#fff; }
@media (max-width: 900px) { .extras { grid-template-columns:1fr; } .mini-grid { grid-template-columns:1fr; } }

/* style pages */
.page-head { text-align:center; padding:48px 16px 8px; }
.page-head h1 { font-size:clamp(42px, 7vw, 68px); }
.page-head p { margin:8px 0 0; font-family:var(--serif); font-style:italic; font-size:20px; color:var(--muted); }
.style-sections h2 { font-family:var(--serif); font-weight:600; font-size:30px; color:var(--granate); margin:36px 0 10px; }
.essentials { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:14px; margin:0; padding:0; list-style:none; }
.essentials li { background:#fff; border-radius:6px; padding:18px; border-top:3px solid var(--gold); }
.essentials b { display:block; font-family:var(--serif); font-size:20px; color:var(--granate); margin-bottom:4px; }
.dodont { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:28px; }
.dodont div { border-radius:6px; padding:20px 22px; }
.dodont .yes { background:#fff; border-left:4px solid var(--granate); }
.dodont .no { background:var(--blush); border-left:4px solid #8C8A90; }
.dodont h3 { margin:0 0 8px; font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--granate); }
.dodont ul { margin:0; padding-left:18px; }
@media (max-width: 640px) { .dodont { grid-template-columns:1fr; } }

.gallery { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; margin:8px 0 28px; }
.gallery figure { margin:0; }
.gallery img { width:100%; aspect-ratio:3/4; object-fit:cover; border-radius:4px; display:block; }
.gallery figcaption { font-size:11px; margin-top:4px; }
.gallery figcaption a { color:var(--muted); }
@media (max-width: 640px) { .gallery { grid-template-columns:1fr 1fr; } }

.style-h { font-family:var(--serif); font-weight:600; font-size:32px; color:var(--granate); margin:44px 0 16px; }
.gallery { grid-template-columns:repeat(4, minmax(0, 1fr)) !important; }
.essentials li img { width:100%; aspect-ratio:4/5; object-fit:cover; border-radius:4px; display:block; margin-bottom:10px; }
.essentials li small { display:block; font-size:10px; margin:-6px 0 8px; }
.essentials li small a { color:var(--muted); }
.trends { list-style:none; counter-reset:t; margin:0; padding:0; display:grid; gap:12px; }
.trends li { counter-increment:t; display:grid; grid-template-columns:56px 1fr; gap:4px 16px; background:#fff; border-radius:6px; padding:18px 20px; }
.trends li::before { content:counter(t, decimal-leading-zero); grid-row:span 2; font-family:var(--serif); font-size:40px; line-height:1; color:var(--gold); }
.trends b { font-family:var(--serif); font-size:22px; color:var(--granate); }
.shop-tier h3 { margin:18px 0 10px; font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.shops { display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:12px; }
.shop { position:relative; display:flex; flex-direction:column; gap:4px; background:#fff; border-radius:6px; padding:16px 36px 16px 16px;
  text-decoration:none; color:var(--ink); font-size:14px; border:1px solid transparent; }
.shop b { font-family:var(--serif); font-size:20px; color:var(--granate); }
.shop:hover { border-color:var(--granate); }
.shop-go { position:absolute; top:14px; right:14px; color:var(--granate); }
.shop-note { font-size:12px; margin-top:12px; }
@media (max-width: 640px) { .gallery { grid-template-columns:1fr 1fr !important; } }

.foot-links { display:flex; flex-wrap:wrap; justify-content:center; gap:6px 18px; margin-top:18px; }
.foot-links a, .privacy-btn { color:#B8BAC1; font-size:12px; text-decoration:none; background:none; border:0; padding:6px 0; font:inherit; font-size:12px; cursor:pointer; }
.foot-links a:hover, .privacy-btn:hover { color:#fff; text-decoration:underline; }
.info { max-width:760px; margin:0 auto; padding:40px 16px 72px; }
.info h1 { font-family:var(--serif); font-weight:600; font-size:clamp(38px, 6vw, 56px); color:var(--granate); margin:0 0 20px; }
.info h2 { font-family:var(--serif); font-weight:600; font-size:26px; color:var(--granate); margin:32px 0 8px; }
.info p { font-size:17px; line-height:1.75; margin:0 0 16px; }

.home-link { display:inline-flex; align-items:center; gap:10px; }
.brand-mark { width:34px; height:34px; display:block; }
.masthead-mark { width:84px; height:84px; display:block; margin:0 auto 14px; }
footer .logo-sm { display:inline-flex !important; align-items:center; gap:10px; }
footer .logo-sm img { width:40px; height:40px; }
@media (max-width: 640px) { .masthead-mark { width:64px; height:64px; } .brand-mark { width:28px; height:28px; } }

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
.sp { display:flex; flex-direction:column; gap:6px; }
.sp-tag { font-size:10px; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); }
.sp-box { display:flex; align-items:center; justify-content:center; background:var(--blush); border:1px dashed #C99AA5;
  border-radius:4px; text-align:center; padding:16px; }
.sp-house { display:flex; flex-direction:column; gap:6px; align-items:center; font-size:14px; color:var(--granate); }
.sp-house a { color:var(--granate); font-weight:600; }
.sp-logo { font-family:var(--serif); font-weight:600; font-size:22px; color:var(--granate); }
.sp-leader { margin:40px auto 0; max-width:970px; }
.sp-leader .sp-box { min-height:110px; }
.sp-card .sp-box { aspect-ratio:3/2; height:auto; }
.sp-card { border-top:4px solid #C99AA5; padding-top:16px; }
.sp-inline { margin:12px 0 8px; }
.sp-inline .sp-box { min-height:250px; }
.sp-rail .sp-box { min-height:600px; }
.side-col { display:none; position:fixed; top:150px; width:120px; z-index:1; }
.side-col .sp-box { min-height:600px; padding:10px; font-size:13px; }
.side-col .sp-logo { font-size:18px; }
.side-col.left { left:calc(50% - 590px - 144px); }
.side-col.right { right:calc(50% - 590px - 144px); }
body:has(.story-layout) .side-col.right { display:none !important; }

/* article page */
.story-layout { max-width:1180px; margin:0 auto; display:flex; gap:56px; padding:0 24px; justify-content:center; }
.story { flex:0 1 780px; min-width:0; padding:40px 0 72px; }
.rail { display:none; flex:0 0 300px; padding-top:96px; }
.rail .sp { position:sticky; top:24px; }
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

@media (min-width: 1460px) {
  .side-col { display:block; }
}
@media (min-width: 1640px) {
  .side-col { width:160px; }
  .side-col.left { left:calc(50% - 590px - 196px); }
  .side-col.right { right:calc(50% - 590px - 196px); }
}
@media (min-width: 1200px) {
  .rail { display:block; }
  .sp-inline { display:none; }
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
  .sp-leader { margin-top:28px; }
}
"""

JS = """
document.querySelectorAll('.privacy-btn').forEach(function (b) {
  b.addEventListener('click', function () {
    window.googlefc = window.googlefc || {};
    window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
    window.googlefc.callbackQueue.push(function () {
      if (window.googlefc.showRevocationMessage) window.googlefc.showRevocationMessage();
    });
  });
});
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
        credit = f'<p class="credit">{tri(UI["illustrative"])} · {tri(UI["photo"])}: {photo_credit(p)}</p>'
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


def build_home(articles: list[dict], styles: list[dict] | None = None) -> str:
    styles = styles or []
    masthead = f"""
<header class="wrap masthead">
  <img class="masthead-mark" src="logo.svg" alt="" width="84" height="84">
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
                masthead + lead_html + leader + f'<main class="wrap">{extras_strip(styles)}{grid}</main>' + community.home_band(tri, community.load()), "")


# ---------------------------------------------------------------- style section
def load_styles() -> list[dict]:
    try:
        with open(STYLE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_styles(styles: list[dict]) -> None:
    os.makedirs(os.path.dirname(STYLE_FILE), exist_ok=True)
    with open(STYLE_FILE, "w", encoding="utf-8") as f:
        json.dump(styles, f, ensure_ascii=False, indent=1)


def style_due(styles: list[dict]) -> bool:
    if not styles:
        return True
    last = datetime.fromisoformat(styles[0]["published_at"])
    return (datetime.now(timezone.utc) - last).days >= STYLE_EVERY_DAYS


def write_style(client: Anthropic, styles: list[dict]) -> dict:
    topic = STYLE_TOPICS[len(styles) % len(STYLE_TOPICS)]
    season = datetime.now().strftime("%B %Y")
    prompt = f"""You are the style editor of "{SITE_NAME}", a publication for this audience:
{AUDIENCE}

Write this week's office-style guide on the topic: "{topic}". Today is {season}.

First, research with web search (up to {SEARCHES_PER_STORY} searches):
- current and upcoming workwear trends for this season from reliable fashion sources
  (Vogue, Harper's Bazaar, Elle, The Cut, WWD, Business of Fashion, major newspapers);
- real retailers that sell this kind of workwear internationally or in Europe, the US and the UK,
  across price levels (affordable high-street, mid-range, premium).

Rules:
- Practical, confident, warm and inclusive: different budgets, body types, dress codes and climates.
- Only name trends and shops you confirmed in your research. Never invent products, prices,
  statistics or quotes. Do not mention specific prices.
- For each shop give its official website homepage.
- Spanish must be natural Spain Spanish and French natural France French, written natively.

After researching, output ONLY JSON inside <style_json></style_json> tags:
{{
 "image_query": "3-6 English words describing an illustration for the guide",
 "photo_queries": ["5 English stock-photo searches: first a wide cover photo, then 4 outfit photos, e.g. 'professional woman tailored suit office', 'woman blazer street style'"],
 "essential_queries": ["one English stock-photo search per essential piece, same order, e.g. 'camel wool coat'"],
 "shops": [{{"name": "Shop", "url": "https://...", "tier": "affordable | mid | premium",
            "known_for": {{"en": "what to buy there, one line", "es": "...", "fr": "..."}}}}],
 "en": {{
   "headline": "max 10 words",
   "dek": "one-sentence standfirst",
   "intro": "a short opening paragraph",
   "sections": [{{"title": "...", "text": "one paragraph"}}, {{"title": "...", "text": "..."}}, {{"title": "...", "text": "..."}}],
   "essentials": [{{"item": "piece", "how": "how to wear it, one sentence"}}],
   "trends": [{{"name": "trend name", "text": "what it is and how to wear it at work, 1-2 sentences"}}],
   "do": ["...", "...", "..."],
   "dont": ["...", "...", "..."],
   "tip": "one smart, specific tip"
 }},
 "es": {{ same fields }},
 "fr": {{ same fields }}
}}
Use 4-5 essentials, 3 trends and 6-9 shops (2-3 per price level)."""
    text, sources = ask_with_web(client, prompt, max_tokens=16000)
    data = extract_json(text, "style_json")
    for lang in LANGS:
        if not data.get(lang, {}).get("headline"):
            raise ValueError(f"missing {lang} version")
    shops = []
    for sh in data.get("shops", []):
        u = urllib.parse.urlparse(str(sh.get("url", "")))
        if not sh.get("name") or u.scheme != "https" or not u.netloc:
            continue
        tier = sh.get("tier", "mid") if sh.get("tier") in ("affordable", "mid", "premium") else "mid"
        shops.append({"name": sh["name"], "url": f"https://{u.netloc}", "tier": tier,
                      "known_for": {l: sh.get("known_for", {}).get(l, "") for l in LANGS}})
    images = style_images(client, data)
    words = len(" ".join([data["en"].get("intro", "")] + [x.get("text", "") for x in data["en"].get("sections", [])]).split())
    return {
        "id": "s" + hashlib.sha1(topic.encode()).hexdigest()[:8] + datetime.now(timezone.utc).strftime("%y%m%d"),
        "topic": topic,
        "category": "Careers",
        "published_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "minutes": max(3, round(words / 220)),
        "content": {l: data[l] for l in LANGS},
        "image_query": data.get("image_query", ""),
        "photo_queries": data.get("photo_queries", []),
        "essential_queries": data.get("essential_queries", []),
        "shops": shops,
        "sources": sources[:10],
        **images,
    }


def needs_new_images(s: dict) -> bool:
    """A style guide needs new images if it has no photo (pixel art or illustration only)."""
    return not s.get("photo")


def without_pixel_art(s: dict) -> dict:
    """Never show pixel art in the Style section."""
    if s.get("art") and s["art"].get("kind") != "vector":
        return {**s, "art": None}
    return s


def heal_style_images(client: Anthropic, styles: list[dict], limit: int = 2) -> None:
    """Give photos to older guides that only have pixel art or an illustration (a few per run)."""
    have_keys = os.getenv("UNSPLASH_ACCESS_KEY") or os.getenv("PEXELS_API_KEY")
    fixed = 0
    for st in styles:
        if fixed >= limit:
            break
        pixel = st.get("art") and st["art"].get("kind") != "vector"
        if not needs_new_images(st) or (not have_keys and not pixel):
            continue
        imgs = style_images(client, {**st["content"], "image_query": st.get("image_query", ""),
                                     "photo_queries": st.get("photo_queries", []),
                                     "essential_queries": st.get("essential_queries", [])})
        if imgs.get("photo") or (pixel and imgs.get("art")):
            st.update(imgs)
            fixed += 1
            print(f"   [Style] New images for: {st['content']['en']['headline'][:60]}")


def style_meta(s: dict) -> str:
    return (f'<p class="kicker"><span class="pill" style="background:var(--gold);color:var(--ink)">'
            f'{tri(UI["nav_style"])}</span><span class="muted">{s["minutes"]} {tri(UI["min"])}</span></p>')


def photo_credit(p: dict) -> str:
    prov = p.get("provider", "Pexels")
    return (f'<a href="{esc(p["page"])}" target="_blank" rel="noopener">{esc(p["photographer"])}</a> / '
            f'<a href="{esc(p.get("provider_url", "https://www.pexels.com"))}" target="_blank" rel="noopener">{esc(prov)}</a>')


def style_credit(s: dict) -> str:
    if s.get("art"):
        return f'<p class="credit">{tri(UI["ai_art"])}</p>'
    p = s.get("photo")
    if p:
        return f'<p class="credit">{tri(UI["photo"])}: {photo_credit(p)}</p>'
    return '<div style="height:32px"></div>'


def style_gallery(s: dict) -> str:
    g = s.get("gallery") or []
    if not g:
        return ""
    items = "".join(
        f'<figure><img src="{esc(p["src"])}" alt="{esc(p["alt"])}" loading="lazy">'
        f'<figcaption>{photo_credit(p)}</figcaption></figure>' for p in g)
    return f'<h2 class="style-h">{tri(UI["lookbook"])}</h2><div class="gallery">{items}</div>'


def build_style_page(s: dict) -> str:
    c = s["content"]

    def per_lang(fn):
        return "".join(f'<div data-l="{l}" lang="{l}">{fn(c[l])}</div>' for l in LANGS)

    sections = per_lang(lambda x: f'<p>{esc(x.get("intro", ""))}</p>' + "".join(
        f'<h2>{esc(sec.get("title", ""))}</h2><p>{esc(sec.get("text", ""))}</p>' for sec in x.get("sections", [])))
    ephotos = s.get("essential_photos") or []

    def essential_cards(x):
        out = []
        for i, e in enumerate(x.get("essentials", [])):
            ph = ephotos[i] if i < len(ephotos) and ephotos[i] else None
            img = (f'<img src="{esc(ph["src"])}" alt="{esc(ph["alt"])}" loading="lazy">'
                   f'<small>{photo_credit(ph)}</small>') if ph else ""
            out.append(f'<li>{img}<b>{esc(e.get("item", ""))}</b>{esc(e.get("how", ""))}</li>')
        return '<ul class="essentials">' + "".join(out) + "</ul>"

    essentials = per_lang(essential_cards)
    trends = per_lang(lambda x: '<ol class="trends">' + "".join(
        f'<li><b>{esc(t.get("name", ""))}</b><span>{esc(t.get("text", ""))}</span></li>' for t in x.get("trends", [])) + "</ol>")
    has_trends = any(c[l].get("trends") for l in LANGS)
    dos = per_lang(lambda x: "<ul>" + "".join(f"<li>{esc(d)}</li>" for d in x.get("do", [])) + "</ul>")
    donts = per_lang(lambda x: "<ul>" + "".join(f"<li>{esc(d)}</li>" for d in x.get("dont", [])) + "</ul>")

    shops_html = ""
    if s.get("shops"):
        groups = ""
        for tier in ("affordable", "mid", "premium"):
            items = [sh for sh in s["shops"] if sh["tier"] == tier]
            if not items:
                continue
            cards = "".join(
                f'<a class="shop" href="{esc(sh["url"])}" target="_blank" rel="noopener sponsored">'
                f'<b>{esc(sh["name"])}</b>{tri(sh["known_for"])}<span class="shop-go">↗</span></a>' for sh in items)
            groups += f'<div class="shop-tier"><h3>{tri(UI["tier_" + tier])}</h3><div class="shops">{cards}</div></div>'
        shops_html = (f'<h2 class="style-h">{tri(UI["shops"])}</h2>{groups}'
                      f'<p class="muted shop-note">{tri(UI["shops_note"])}</p>')

    srcs = "".join(f'<li><a href="{esc(x["url"])}" target="_blank" rel="noopener">{esc(x["title"])}</a></li>'
                   for x in s.get("sources", []))
    sources_html = f'<h2 class="src-title">{tri(UI["sources"])}</h2><ul class="sources">{srcs}</ul>' if srcs else ""

    body = f"""
<div class="story-layout">
<main class="story">
  <a class="back" href="index.html">← {tri(UI["all_style"])}</a>
  <article>
    {style_meta(s)}
    <h1>{tri(field(s, "headline"))}</h1>
    <p class="dek">{tri(field(s, "dek"))}</p>
    <p class="byline">{tri(date_labels(s["published_at"]))}</p>
    {image_html(s, "story-img", "../")}
    {style_credit(s)}
    <div class="body style-sections">{sections}</div>
    {style_gallery(s)}
    <h2 class="style-h">{tri(UI["essentials"])}</h2>
    {essentials}
    {f'<h2 class="style-h">{tri(UI["trends"])}</h2>{trends}' if has_trends else ""}
    {ad_slot("inline")}
    {shops_html}
    <div class="dodont">
      <div class="yes"><h3>{tri(UI["do"])}</h3>{dos}</div>
      <div class="no"><h3>{tri(UI["dont"])}</h3>{donts}</div>
    </div>
    <aside class="box accent"><h2>{tri(UI["tip"])}</h2><p>{tri(field(s, "tip"))}</p></aside>
    {sources_html}
  </article>
</main>
{('<div class="rail">' + ad_slot("rail") + '</div>') if ADS_ENABLED else ""}
</div>"""
    en = c["en"]
    return page(f'{en["headline"]} — {SITE_NAME}', body, "../", en.get("dek", ""))


def build_style_index(styles: list[dict]) -> str:
    head = f"""<header class="page-head"><h1>{tri(UI["style_title"])}</h1><p>{tri(UI["style_sub"])}</p></header>"""
    if not styles:
        return page(f'{UI["style_title"]["en"]} — {SITE_NAME}',
                    head + f'<main class="wrap"><p class="empty">{tri(UI["empty"])}</p></main>', "../")
    cards = "".join(f"""
<article class="card" style="--cat:var(--gold)">
  <a class="img-link" href="{s["id"]}.html" tabindex="-1" aria-hidden="true">{image_html(s, "card-img", "../")}</a>
  {style_meta(s)}
  <h3><a href="{s["id"]}.html">{tri(field(s, "headline"))}</a></h3>
  <p class="card-dek">{tri(field(s, "dek"))}</p>
</article>""" for s in styles)
    leader = ad_slot("leader")
    return page(f'{UI["style_title"]["en"]} — {SITE_NAME}',
                head + f'<main class="wrap">{leader}<div class="grid" style="margin-top:40px">{cards}</div></main>', "../")


# ---------------------------------------------------------------- game page
def build_game_page() -> str:
    rows = ["QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]
    keys = ""
    for i, row in enumerate(rows):
        btns = "".join(f'<button type="button" class="key" data-k="{k}">{k}</button>' for k in row)
        if i == 2:
            btns = (f'<button type="button" class="key wide" data-action="ENTER">{tri(UI["enter"])}</button>' + btns +
                    '<button type="button" class="key wide" data-action="BACK" aria-label="Delete">⌫</button>')
        keys += f'<div class="keyrow">{btns}</div>'
    defs = "".join(f'<p id="def-{l}" data-l="{l}" lang="{l}"></p>' for l in LANGS)
    body = f"""
<main class="game">
  <h1>Power Word</h1>
  <p class="game-sub">{tri(UI["game_sub"])}</p>
  <p class="game-num">{tri(UI["game_num"])} #<span class="pw-num"></span></p>
  <p class="game-msg" id="msg" role="status" aria-live="polite"></p>
  <div class="board" id="board" aria-label="Game board"></div>
  <div class="keys">{keys}</div>
  <section class="reveal" id="reveal" aria-live="polite">
    <p class="kicker">{tri(UI["word_means"])}</p>
    <h2 id="answer"></h2>
    {defs}
    <div class="stats">
      <div><b id="st-played">0</b><span>{tri(UI["played"])}</span></div>
      <div><b id="st-wins">0%</b><span>{tri(UI["wins"])}</span></div>
      <div><b id="st-streak">0</b><span>{tri(UI["streak"])}</span></div>
      <div><b id="st-best">0</b><span>{tri(UI["best"])}</span></div>
    </div>
    <button type="button" class="share" id="share">{tri(UI["share"])} <span aria-hidden="true">↗</span></button>
    <p class="muted" style="margin-top:14px">{tri(UI["comeback"])}</p>
  </section>
  <details class="how">
    <summary>{tri(UI["how_title"])}</summary>
    <p>{tri(UI["how_text"])}</p>
    <div class="legend">
      <span><i style="background:var(--granate)"></i>{tri(UI["hit"])}</span>
      <span><i style="background:var(--gold)"></i>{tri(UI["near"])}</span>
      <span><i style="background:#8C8A90"></i>{tri(UI["miss"])}</span>
    </div>
  </details>
</main>"""
    words = json.dumps([list(w) for w in game.WORDS], ensure_ascii=False)
    extra_js = (f'<script>window.POWER_WORDS = {words}; window.SITE_URL = {json.dumps(SITE_URL)};</script>'
                f'<script src="game.js"></script>')
    return page(f"Power Word — {SITE_NAME}", body, "../", UI["game_sub"]["en"],
                extra_head='<link rel="stylesheet" href="game.css">', extra_js=extra_js)


def extras_strip(styles: list[dict]) -> str:
    minis = "".join(f'<a class="mini" href="style/{s["id"]}.html">{image_html(s, "", "")}'
                    f'<span>{tri(field(s, "headline"))}</span></a>' for s in styles[:3])
    style_box = (f'<div class="extras-style"><h2>{tri(UI["style_title"])}</h2>'
                 f'<p class="muted" style="margin:6px 0 0">{tri(UI["style_sub"])}</p>'
                 f'<div class="mini-grid">{minis}</div></div>') if styles else ""
    game_box = f"""<div class="extras-game">
  <div class="mini-tiles" aria-hidden="true"><i style="background:var(--gold);color:var(--ink)">P</i><i style="background:#8C8A90">O</i><i style="background:#fff;color:var(--granate)">W</i><i style="background:#fff;color:var(--granate)">E</i><i style="background:var(--gold);color:var(--ink)">R</i></div>
  <h2>Power Word</h2>
  <p>{tri(UI["game_teaser"])}</p>
  <a class="cta" href="game/index.html">{tri(UI["play"])} <span aria-hidden="true">→</span></a>
</div>"""
    cols = "" if styles else ' style="grid-template-columns:1fr"'
    return f'<section class="extras"{cols}>{style_box}{game_box}</section>'


def build_info_page(slug: str) -> str:
    pg = legal.PAGES[slug]
    fill = {"email": legal.CONTACT_EMAIL, "owner": legal.OWNER_NAME, "id": legal.OWNER_ID,
            "address": legal.OWNER_ADDRESS, "site": SITE_URL.replace("https://", ""), "updated": legal.LAST_UPDATED}
    blocks = ""
    for l in LANGS:
        inner = ""
        extra = community.PRIVACY_ADDON[l] if slug == "privacy" else []
        for kind, text in list(pg["body"][l]) + extra:
            t = esc(text.format(**fill))
            t = t.replace(esc(legal.CONTACT_EMAIL), f'<a href="mailto:{esc(legal.CONTACT_EMAIL)}">{esc(legal.CONTACT_EMAIL)}</a>')
            inner += f"<h2>{t}</h2>" if kind == "h" else f"<p>{t}</p>"
        blocks += f'<div data-l="{l}" lang="{l}">{inner}</div>'
    body = f'<main class="info"><h1>{tri(pg["title"])}</h1>{blocks}</main>'
    return page(f'{pg["title"]["en"]} — {SITE_NAME}', body, "")


def logo_svg(name: str = "logo.svg") -> str:
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def make_social_kits(client: Anthropic, news: list[dict], styles_new: list[dict]) -> None:
    queue = social.load_queue()
    done = {q["id"] for q in queue}
    todo = [("news", a) for a in news if a["id"] not in done][: social.PER_RUN]
    todo += [("style", st) for st in styles_new if st["id"] not in done]
    for kind, item in todo:
        kit = social.make_kit(ask, client, FILTER_MODEL, SITE_NAME, SITE_URL, item, kind, logo_svg())
        if kit:
            queue.insert(0, kit)
            print(f"[Social] Kit ready: {kit['headline'][:60]}")
    game_id = f"pw-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    if game_id not in done:  # one Power Word post per day
        kit = social.make_game_kit(SITE_URL, game.WORDS, logo_svg("logo-light.svg"))
        if kit:
            queue.insert(0, kit)
            print(f"[Social] Kit ready: {kit['headline']}")
    social.save_queue(queue)


def build_seo_files(articles: list[dict], styles: list[dict]) -> None:
    urls = [f"{SITE_URL}/", f"{SITE_URL}/style/index.html", f"{SITE_URL}/game/index.html",
            f"{SITE_URL}/voices/index.html", f"{SITE_URL}/voices/share.html"]
    urls += [f"{SITE_URL}/voices/{v['id']}.html" for v in community.load()]
    urls += [f"{SITE_URL}/article/{a['id']}.html" for a in articles]
    urls += [f"{SITE_URL}/style/{st['id']}.html" for st in styles]
    urls += [f"{SITE_URL}/{slug}.html" for slug in legal.PAGES]
    with open(os.path.join(SITE_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        f.write("".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in urls))
        f.write("</urlset>\n")
    with open(os.path.join(SITE_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nDisallow: /social/\n\nSitemap: {SITE_URL}/sitemap.xml\n")


def build_site(articles: list[dict], styles: list[dict] | None = None) -> None:
    styles = load_styles() if styles is None else styles
    if os.path.isdir(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(os.path.join(SITE_DIR, "article"))
    os.makedirs(os.path.join(SITE_DIR, "img"))
    os.makedirs(os.path.join(SITE_DIR, "style"))
    os.makedirs(os.path.join(SITE_DIR, "game"))
    with open(os.path.join(SITE_DIR, "game", "game.css"), "w", encoding="utf-8") as f:
        f.write(game.GAME_CSS)
    with open(os.path.join(SITE_DIR, "game", "game.js"), "w", encoding="utf-8") as f:
        f.write(game.GAME_JS)
    with open(os.path.join(SITE_DIR, "game", "index.html"), "w", encoding="utf-8") as f:
        f.write(build_game_page())
    styles = [without_pixel_art(st) for st in styles]
    for st in styles:
        if st.get("art"):
            with open(os.path.join(SITE_DIR, "img", f'{st["id"]}.svg'), "w", encoding="utf-8") as f:
                f.write(st["art"]["svg"])
        with open(os.path.join(SITE_DIR, "style", f'{st["id"]}.html'), "w", encoding="utf-8") as f:
            f.write(build_style_page(st))
    with open(os.path.join(SITE_DIR, "style", "index.html"), "w", encoding="utf-8") as f:
        f.write(build_style_index(styles))
    with open(os.path.join(SITE_DIR, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS + community.CSS)
    voices = community.load()
    vdir = os.path.join(SITE_DIR, "voices")
    os.makedirs(vdir, exist_ok=True)
    with open(os.path.join(vdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(community.build_index(voices, page, tri, esc, SITE_NAME, ad_slot))
    with open(os.path.join(vdir, "share.html"), "w", encoding="utf-8") as f:
        f.write(community.build_share(page, tri, esc, SITE_NAME, os.getenv("COMMUNITY_URL", "")))
    with open(os.path.join(vdir, "share.js"), "w", encoding="utf-8") as f:
        f.write(community.SHARE_JS)
    for v in voices:
        with open(os.path.join(vdir, f'{v["id"]}.html'), "w", encoding="utf-8") as f:
            f.write(community.build_story(v, [o for o in voices if o is not v], page, tri, esc, SITE_NAME, photo_credit, UI))
    with open(os.path.join(SITE_DIR, "app.js"), "w", encoding="utf-8") as f:
        f.write(JS)
    with open(os.path.join(SITE_DIR, ".nojekyll"), "w") as f:
        f.write("")
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    if os.path.isdir(assets_dir):
        for name in os.listdir(assets_dir):
            shutil.copy(os.path.join(assets_dir, name), os.path.join(SITE_DIR, name))
    for slug in legal.PAGES:
        with open(os.path.join(SITE_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(build_info_page(slug))
    if ADSENSE_CLIENT:  # authorises Google to sell ads on this site
        pub = ADSENSE_CLIENT.replace("ca-", "")
        with open(os.path.join(SITE_DIR, "ads.txt"), "w") as f:
            f.write(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    for a in articles:
        if a.get("art"):
            with open(os.path.join(SITE_DIR, "img", f'{a["id"]}.svg'), "w", encoding="utf-8") as f:
                f.write(a["art"]["svg"])
        with open(os.path.join(SITE_DIR, "article", f'{a["id"]}.html'), "w", encoding="utf-8") as f:
            f.write(build_article_page(a))
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_home(articles, [without_pixel_art(x) for x in styles]))
    # private social media kit + SEO files
    os.makedirs(os.path.join(SITE_DIR, "social"), exist_ok=True)
    queue = social.load_queue()
    for it in queue:
        if it.get("image") and os.path.exists(os.path.join(social.SOCIAL_DIR, it["image"])):
            shutil.copy(os.path.join(social.SOCIAL_DIR, it["image"]), os.path.join(SITE_DIR, "social", it["image"]))
    with open(os.path.join(SITE_DIR, "social", "index.html"), "w", encoding="utf-8") as f:
        f.write(social.build_kit_page(queue))
    build_seo_files(articles, styles)
    print(f"[6/6] Website built in '{SITE_DIR}/' with {len(articles)} articles")


# ---------------------------------------------------------------- main
def main() -> None:
    load_dotenv()
    published = load_articles()
    USED_PHOTOS.update(a["photo"].get("id") for a in published[:60] if a.get("photo"))

    if "--build-only" in sys.argv:  # rebuild the site without fetching news
        build_site(published)
        return

    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Missing ANTHROPIC_API_KEY. Put it in a .env file next to this script.")
    client = Anthropic(max_retries=5)

    if "--redraw" in sys.argv or "--redraw-all" in sys.argv:  # illustrations only, no new news
        redraw_all = "--redraw-all" in sys.argv
        missing = [a for a in published if IMAGE_MODE == "pixel" and not a.get("photo") and (redraw_all or not a.get("art"))]
        print(f"Redrawing {len(missing)} missing illustrations...")
        for a in missing:
            a["art"] = pixel_art(client, a["content"]["en"]["headline"], a.get("image_query", ""))
            print("   ok" if a["art"] else "   still failed", "-", a["content"]["en"]["headline"][:60])
        save_articles(published)
        build_site(published)
        return

    if "--social" in sys.argv:  # make a social kit for the latest article(s), no new news
        make_social_kits(client, published[:3], [])
        build_site(published)
        return

    if "--news-photos" in sys.argv:  # give real photos to existing general-topic articles
        done = 0
        for a in published:
            if a.get("photo"):
                USED_PHOTOS.add(a["photo"].get("id"))
        for a in published:
            if a["category"] in PHOTO_CATEGORIES and not a.get("photo"):
                q = topic_query(client, a["content"]["en"]["headline"], a["content"]["en"].get("dek", ""))
                a["photo_query"] = q or a.get("photo_query", "")
                found = stock_photos(a["photo_query"], 1, "landscape", USED_PHOTOS) if a["photo_query"] else []
                photo = found[0] if found else None
                if photo:
                    a["photo"], a["art"] = photo, None
                    done += 1
                    print("   photo ok -", a["content"]["en"]["headline"][:60])
        print(f"{done} articles now have photos")
        save_articles(published)
        build_site(published)
        return

    if "--style-images" in sys.argv:
        styles = load_styles()  # redo the images of every style guide, then rebuild
        for st in styles:
            st.update(style_images(client, {**st["content"], "image_query": st.get("image_query", ""),
                                            "photo_queries": st.get("photo_queries", []),
                                            "essential_queries": st.get("essential_queries", [])}))
            print("   images ok -", st["content"]["en"]["headline"][:60])
        save_styles(styles)
        build_site(published, styles)
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

    styles = load_styles()
    wanted = max(STYLE_MIN_GUIDES - len(styles), 1 if ("--style" in sys.argv or style_due(styles)) else 0)
    styles_new = []
    for _ in range(min(wanted, STYLE_MIN_GUIDES)):
        try:
            styles.insert(0, write_style(client, styles))
            styles_new.append(styles[0])
            save_styles(styles)
            print(f"[Style] New guide: {styles[0]['topic']}")
        except Exception as e:
            print(f"      Style guide skipped ({e})")
    heal_style_images(client, styles)
    save_styles(styles)

    try:
        community.run(ask, client, FILTER_MODEL, WRITER_MODEL, extract_json, stock_photos, USED_PHOTOS)
    except Exception as e:
        print(f"      Voices skipped ({e})")

    try:
        make_social_kits(client, new_articles, styles_new[:1])
    except Exception as e:
        print(f"      Social kits skipped ({e})")

    articles = new_articles + published  # newest first
    save_articles(articles)
    print(f"[5/6] Added {len(new_articles)} new articles (total {len(articles)})")
    build_site(articles[:KEEP_ARTICLES], styles)


if __name__ == "__main__":
    main()
