"""
Madam CEO – social media kit.
For the top story of each run (and each new Style guide) it creates:
  - a branded 1080x1350 JPEG card (works for Instagram, LinkedIn, X and TikTok photo posts)
  - captions written for X, Instagram, LinkedIn and TikTok
Everything is saved in data/social/ and shown on a private page: /social/ (not linked, not indexed).
Rendering the card needs Playwright + Chromium; without it the captions are still created.
"""

import base64
import html
import json
import os
import re
from datetime import datetime, timezone, timedelta

SOCIAL_DIR = os.path.join("data", "social")
QUEUE_FILE = os.path.join(SOCIAL_DIR, "queue.json")
KEEP_DAYS = 45            # older kits are removed to keep the repository small
PER_RUN = 1               # news stories turned into a kit per run (3 runs a day = 3 a day)

CAT_COLORS = {
    "Leadership": "#7A1F3D", "Boards": "#2E4A62", "Money": "#A87E2E", "Policy": "#2F6F6A",
    "Deals": "#B4532F", "Workplace": "#6B4E8C", "Careers": "#3F6B4A", "Style": "#C9A45C",
}


def load_queue() -> list[dict]:
    try:
        with open(QUEUE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_queue(queue: list[dict]) -> None:
    os.makedirs(SOCIAL_DIR, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    kept = []
    for item in queue:
        if datetime.fromisoformat(item["created"]) >= cutoff:
            kept.append(item)
        else:
            try:
                os.remove(os.path.join(SOCIAL_DIR, item["image"]))
            except (OSError, KeyError, TypeError):
                pass
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=1)


def write_captions(ask, client, model: str, site_name: str, headline: str, dek: str,
                   why: str, url: str, kind: str) -> dict:
    prompt = f"""You run the social accounts of "{site_name}", a news brand for ambitious women in the corporate world.
Write posts promoting this {"style guide" if kind == "style" else "news story"}:

Headline: {headline}
Summary: {dek}
Why it matters: {why}
Link: {url}

Rules: smart, warm, confident; no clickbait, no invented facts beyond the text above; English.
Reply ONLY with JSON inside <social></social> tags:
{{
 "x": "max 240 characters, punchy, ends with the link",
 "instagram": "a hook line, 2-3 short lines of context, a question to the audience, then 'Full story: link in bio', then 8-12 relevant hashtags",
 "linkedin": "3-4 short paragraphs for professionals, a question at the end, the link on its own line, 3 hashtags",
 "tiktok": "max 150 characters with 4-6 hashtags",
 "card_kicker": "2-4 words for the top of the image, e.g. 'Boardroom news'"
}}"""
    text = ask(client, model, prompt, max_tokens=2000)
    m = re.search(r"<social>(.*?)</social>", text, re.S)
    data = json.loads(re.search(r"\{.*\}", m.group(1) if m else text, re.S).group(0))
    for k in ("x", "instagram", "linkedin", "tiktok"):
        data[k] = str(data.get(k, "")).strip()
    return ensure_link(data, url)


def ensure_link(caps: dict, url: str) -> dict:
    """Every caption must contain the link to the site."""
    if url not in caps.get("x", ""):
        caps["x"] = (caps.get("x", "")[: 280 - len(url) - 2].rstrip() + "\n" + url).strip()
    for net in ("instagram", "linkedin", "tiktok"):
        text = caps.get(net, "")
        if url not in text:
            caps[net] = (text.rstrip() + f"\n\n🔗 {url}").strip()
    return caps


def card_html(headline: str, kicker: str, category: str, image_src: str, pixel: bool, site_url: str,
              logo_svg: str, dek: str = "") -> str:
    color = CAT_COLORS.get(category, "#7A1F3D")
    domain = site_url.replace("https://", "")
    rendering = "image-rendering:pixelated;" if pixel else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@500;600&display=swap" rel="stylesheet">
<style>
body{{margin:0}}
.card{{width:1080px;height:1350px;background:#F4E4E2;display:flex;flex-direction:column;font-family:Inter,sans-serif;overflow:hidden}}
.img{{height:690px;background:#EBD5D2 url('{image_src}') center/cover no-repeat;{rendering}border-bottom:14px solid {color}}}
.txt{{flex:1;padding:56px 72px 40px;display:flex;flex-direction:column}}
.pill{{align-self:flex-start;background:{color};color:#fff;font-weight:600;font-size:26px;letter-spacing:.12em;text-transform:uppercase;padding:12px 24px;border-radius:999px}}
h1{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;color:#6E1630;font-size:{74 if len(headline) < 70 else 62}px;line-height:1.05;margin:30px 0 0}}
.dek{{font-size:30px;line-height:1.45;color:#4A4D55;margin:22px 0 0}}
.foot{{margin-top:auto;display:flex;align-items:center;justify-content:space-between}}
.brand{{display:flex;align-items:center;gap:18px;font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:44px;color:#6E1630}}
.brand svg{{width:72px;height:72px}} .brand b{{color:#C9A45C}}
.url{{font-size:26px;color:#5C5A60;font-weight:500}}
</style></head><body><div class="card">
<div class="img"></div>
<div class="txt"><span class="pill">{html.escape(kicker)}</span><h1>{html.escape(headline)}</h1>{f'<p class="dek">{html.escape(dek[:150])}</p>' if dek and len(headline) < 80 else ""}
<div class="foot"><div class="brand">{logo_svg}<span>Madam CEO<b>.</b></span></div><span class="url">{html.escape(domain)}</span></div>
</div></div></body></html>"""


def render_card(page_html: str, out_path: str) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("      (Playwright not installed: social images skipped, captions still created)")
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pg = browser.new_page(viewport={"width": 1080, "height": 1350})
            pg.set_content(page_html, wait_until="networkidle", timeout=30000)
            pg.wait_for_timeout(500)
            pg.screenshot(path=out_path, type="jpeg", quality=90)
            browser.close()
        return True
    except Exception as e:
        print(f"      Social image failed ({e})")
        return False


def make_kit(ask, client, model: str, site_name: str, site_url: str, item: dict, kind: str, logo_svg: str) -> dict | None:
    """item = an article or a style guide from ascent_news.py."""
    en = item["content"]["en"]
    path = ("style/" if kind == "style" else "article/") + f'{item["id"]}.html'
    url = f"{site_url}/{path}"
    try:
        caps = write_captions(ask, client, model, site_name, en.get("headline", ""), en.get("dek", ""),
                              en.get("why_it_matters", en.get("tip", "")), url, kind)
    except Exception as e:
        print(f"      Social captions failed ({e})")
        return None
    image_name = None
    if item.get("photo"):
        src, pixel = item["photo"]["src"], False
    elif item.get("art"):
        src = "data:image/svg+xml;base64," + base64.b64encode(item["art"]["svg"].encode()).decode()
        pixel = item["art"].get("kind") != "vector"
    else:
        src, pixel = "", False
    os.makedirs(SOCIAL_DIR, exist_ok=True)
    name = f'{item["id"]}.jpg'
    category = "Style" if kind == "style" else item.get("category", "Leadership")
    if render_card(card_html(en.get("headline", ""), caps.get("card_kicker") or category, category, src, pixel,
                             site_url, logo_svg, en.get("dek", "")), os.path.join(SOCIAL_DIR, name)):
        image_name = name
    return {
        "id": item["id"], "kind": kind, "created": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "headline": en.get("headline", ""), "url": url, "image": image_name,
        "captions": {k: caps[k] for k in ("x", "instagram", "linkedin", "tiktok")},
        "posted": {"x": False, "instagram": False, "linkedin": False, "tiktok": False},
    }


GAME_START = datetime(2026, 10, 27, tzinfo=timezone.utc)


def game_card_html(num: int, prev_word: str, prev_def: str, site_url: str, logo_svg: str) -> str:
    domain = site_url.replace("https://", "")
    tiles = "".join('<i></i>' for _ in range(5))
    sample = "".join(f'<b class="{c}">{l}</b>' for l, c in zip(prev_word, ["hit"] * 5))
    prev_box = (f'<div class="prev"><small>Yesterday\'s word</small><div class="word">{sample}</div>'
                f'<p>{html.escape(prev_def)}</p></div>') if prev_word else \
        '<div class="prev"><small>How to play</small><p>Type any five-letter word. Burgundy: right letter, right spot. Gold: in the word, wrong spot. Grey: not in the word.</p></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@500;600;700&display=swap" rel="stylesheet">
<style>
body{{margin:0}}
.card{{width:1080px;height:1350px;background:#6E1630;color:#fff;font-family:Inter,sans-serif;display:flex;flex-direction:column;align-items:center;padding:90px 80px 70px;box-sizing:border-box}}
.top{{font-size:28px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#E9C3CC}}
h1{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:150px;line-height:1;margin:22px 0 6px}}
.num{{font-size:40px;font-weight:600;color:#C9A45C;margin:0 0 56px}}
.tiles{{display:flex;gap:18px}} .tiles i{{width:150px;height:150px;border:5px solid #E9C3CC;border-radius:12px;display:block}}
.q{{font-size:40px;line-height:1.35;text-align:center;margin:52px 0 0;color:#F5DDE4}}
.prev{{margin-top:auto;width:100%;background:#F4E4E2;color:#16171B;border-radius:18px;padding:30px 36px;box-sizing:border-box}}
.prev small{{font-size:22px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#7A1F3D}}
.word{{display:flex;gap:10px;margin:14px 0 12px}} .word b{{width:64px;height:64px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:700;color:#fff}}
.hit{{background:#7A1F3D}} .near{{background:#C9A45C;color:#16171B !important}} .miss{{background:#8C8A90}}
.prev p{{font-size:28px;line-height:1.4;margin:0;color:#3D3F45}}
.foot{{display:flex;align-items:center;justify-content:space-between;width:100%;margin-top:34px}}
.brand{{display:flex;align-items:center;gap:16px;font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:42px}}
.brand svg{{width:66px;height:66px}} .brand span b{{color:#C9A45C}} .url{{font-size:28px;color:#F5DDE4}}
</style></head><body><div class="card">
<div class="top">The daily business word game</div>
<h1>Power Word</h1><p class="num">#{num}</p>
<div class="tiles">{tiles}</div>
<p class="q">Can you crack today's five-letter<br>business word in six tries?</p>
{prev_box}
<div class="foot"><div class="brand">{logo_svg}<span>Madam CEO<b>.</b></span></div><span class="url">{html.escape(domain)}/game</span></div>
</div></body></html>"""


def make_game_kit(site_url: str, words: list, logo_svg: str) -> dict | None:
    """Daily Power Word post. The puzzle number matches the game on the site."""
    today = datetime.now(timezone.utc)
    day = max(0, (today.date() - GAME_START.date()).days)
    num = day + 1
    prev = words[(day - 1) % len(words)] if day > 0 else None
    url = f"{site_url}/game/"
    prev_line = f"Yesterday's word: {prev[0]}." if prev else "A new word every day."
    caps = {
        "x": f"Power Word #{num} is live 👑 Can you guess today's five-letter business word in 6 tries?\n{prev_line}\n{url}",
        "instagram": (f"Power Word #{num} 👑\nToday's five-letter business word is waiting. Six tries. No hints.\n"
                      f"{prev_line}" + (f" {prev[1]}" if prev else "") +
                      f"\nHow many tries did you need? Tell us below 👇\n\nPlay now: link in bio\n🔗 {url}\n\n"
                      "#powerword #wordgame #dailypuzzle #wordle #businessenglish #womeninbusiness #careergrowth "
                      "#leadership #madamceo"),
        "linkedin": (f"Power Word #{num} is live.\n\nOne five-letter business word, six tries, two minutes. "
                     f"A small daily habit to sharpen your business vocabulary.\n\n{prev_line}"
                     + (f" {prev[1]}" if prev else "") +
                     f"\n\nShare your score in the comments.\n\n{url}\n\n#leadership #careers #womeninbusiness"),
        "tiktok": f"Power Word #{num} 👑 can you get it in 3? #wordgame #dailypuzzle #businesstok #careertok\n🔗 {url}",
    }
    caps = ensure_link(caps, url)
    os.makedirs(SOCIAL_DIR, exist_ok=True)
    item_id = f"pw-{today.strftime('%Y%m%d')}"
    name = f"{item_id}.jpg"
    ok = render_card(game_card_html(num, prev[0] if prev else "", prev[1] if prev else "",
                                    site_url, logo_svg), os.path.join(SOCIAL_DIR, name))
    return {
        "id": item_id, "kind": "game", "created": today.isoformat(timespec="minutes"),
        "headline": f"Power Word #{num}", "url": url, "image": name if ok else None,
        "captions": caps, "posted": {"x": False, "instagram": False, "linkedin": False, "tiktok": False},
    }


def build_kit_page(queue: list[dict]) -> str:
    """Private page (not linked, not indexed) to copy captions and download images."""
    cards = []
    for it in queue:
        img = (f'<a href="{html.escape(it["image"])}" download><img src="{html.escape(it["image"])}" alt=""></a>'
               if it.get("image") else '<div class="noimg">Sin imagen</div>')
        blocks = "".join(
            f'<div class="cap"><div class="cap-h"><b>{net}</b><button type="button" data-copy="{it["id"]}-{net}">Copiar</button></div>'
            f'<pre id="{it["id"]}-{net}">{html.escape(text)}</pre></div>'
            for net, text in it["captions"].items())
        cards.append(f'<article><div class="pic">{img}<p class="date">{it["created"][:16].replace("T", " ")} UTC · '
                     f'<a href="{html.escape(it["url"])}" target="_blank">ver artículo</a></p></div>'
                     f'<div class="caps"><h2>{html.escape(it["headline"])}</h2>{blocks}</div></article>')
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>Kit de redes — Madam CEO</title>
<style>
body{{margin:0;background:#F4E4E2;font-family:system-ui,sans-serif;color:#16171B}}
header{{background:#7A1F3D;color:#fff;padding:20px 24px}} header h1{{margin:0;font-family:Georgia,serif}}
header p{{margin:6px 0 0;color:#F1D3DA;font-size:14px}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px;display:grid;gap:24px}}
article{{background:#fff;border-radius:10px;padding:20px;display:grid;grid-template-columns:320px 1fr;gap:24px}}
.pic img{{width:100%;border-radius:6px;display:block}} .noimg{{aspect-ratio:4/5;background:#EBD5D2;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#5C5A60}}
.date{{font-size:12px;color:#5C5A60}} h2{{margin:0 0 12px;font-family:Georgia,serif;color:#6E1630}}
.cap{{margin-bottom:12px}} .cap-h{{display:flex;justify-content:space-between;align-items:center;text-transform:capitalize}}
.cap-h button{{min-height:36px;padding:0 14px;border:0;border-radius:999px;background:#7A1F3D;color:#fff;font:inherit;font-size:13px;cursor:pointer}}
pre{{white-space:pre-wrap;font:14px/1.5 system-ui,sans-serif;background:#FBF6F1;border-radius:6px;padding:10px 12px;margin:6px 0 0}}
@media (max-width:760px){{article{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>Kit de redes</h1><p>Página privada: no está enlazada ni aparece en Google. Toca la imagen para descargarla y copia el texto de cada red.</p></header>
<main>{"".join(cards) or "<p>Todavía no hay publicaciones preparadas.</p>"}</main>
<script>
document.querySelectorAll('[data-copy]').forEach(function (b) {{
  b.addEventListener('click', function () {{
    var t = document.getElementById(b.dataset.copy).innerText;
    navigator.clipboard.writeText(t).then(function () {{ b.textContent = '¡Copiado!'; setTimeout(function () {{ b.textContent = 'Copiar'; }}, 1500); }});
  }});
}});
</script></body></html>"""
