"""
Madam CEO – Content Studio.
After every update it prepares a ready-to-publish pack for Instagram, TikTok, LinkedIn and X
and emails it (images attached + captions) so it can be posted from a phone in a few minutes.

Per story:
  Instagram  post 4:5 (1080x1350) + story 9:16 (1080x1920, room left for the link sticker)
  TikTok     photo carousel of 3 slides 9:16 + caption
  LinkedIn   text + the 4:5 image
  X          post + 16:9 image (1600x900)
The first pack of each day (Madrid time) also includes the Power Word post + story.

Settings (GitHub secrets or .env):
  RESEND_API_KEY   key from resend.com (domain themadamceo.com verified)
  PACK_EMAIL       where the pack is sent (kept secret because the repository is public)
"""

import base64
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # very old Python: fall back to UTC+1
    MADRID = timezone(timedelta(hours=1))

OUT_DIR = "output/studio"
STATE_FILE = "data/studio_state.json"
STORIES_PER_PACK = 3
SENDER = "Madam CEO Studio <studio@themadamceo.com>"
REPLY_TO = "hello@themadamceo.com"

C = {"granate": "#6E1630", "accent": "#7A1F3D", "paper": "#F4E4E2", "blush": "#FBF1EF", "gold": "#C9A45C",
     "ink": "#16171B", "muted": "#5C5A60", "cream": "#FBF6F1", "pink": "#F5D7DF"}
CAT_COLORS = {
    "Leadership": "#7A1F3D", "Boards": "#2E4A62", "Money": "#A87E2E", "Policy": "#2F6F6A",
    "Deals": "#B4532F", "Workplace": "#6B4E8C", "Careers": "#3F6B4A", "Style": "#C9A45C", "Voices": "#7A1F3D",
}
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&'
         'family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">')


# ---------------------------------------------------------------- helpers
def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if len(s) > n:
        s = s[:n].rsplit("-", 1)[0]
    return s or "story"


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def image_src(item: dict) -> tuple[str, bool]:
    if item.get("photo"):
        return item["photo"]["src"], False
    if item.get("art"):
        return ("data:image/svg+xml;base64," + base64.b64encode(item["art"]["svg"].encode()).decode(),
                item["art"].get("kind") != "vector")
    return "", False


def base_css(w: int, h: int) -> str:
    return f"""*{{box-sizing:border-box}} body{{margin:0}}
.c{{width:{w}px;height:{h}px;overflow:hidden;position:relative;font-family:Inter,sans-serif;color:{C['ink']}}}
.serif{{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600}}
.brand{{display:flex;align-items:center;gap:16px;font-family:'Cormorant Garamond',Georgia,serif;font-weight:600}}
.brand b{{color:{C['gold']}}}
.pill{{display:inline-block;color:#fff;font-weight:600;letter-spacing:.14em;text-transform:uppercase;border-radius:999px}}"""


def page(w: int, h: int, css: str, body: str) -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{base_css(w, h)}{css}</style></head>'
            f'<body><div class="c">{body}</div></body></html>')


def fit(text: str, sizes: list[tuple[int, int]]) -> int:
    """Pick a font size from (max_chars, size) pairs."""
    for limit, size in sizes:
        if len(text) <= limit:
            return size
    return sizes[-1][1]


# ---------------------------------------------------------------- templates
def post_4x5(t: dict, logo: str, domain: str) -> str:
    color = CAT_COLORS.get(t["category"], C["accent"])
    hs = fit(t["headline"], [(50, 80), (75, 68), (999, 58)])
    px = "image-rendering:pixelated;" if t["pixel"] else ""
    css = f""".c{{background:{C['paper']};display:flex;flex-direction:column}}
.img{{height:700px;background:#EBD5D2 url('{t['src']}') center/cover no-repeat;{px}border-bottom:14px solid {color}}}
.t{{flex:1;padding:54px 72px 44px;display:flex;flex-direction:column}}
.pill{{align-self:flex-start;background:{color};font-size:25px;padding:12px 24px}}
h1{{color:{C['granate']};font-size:{hs}px;line-height:1.04;margin:28px 0 0}}
.dek{{font-size:29px;line-height:1.45;color:#4A4D55;margin:20px 0 0}}
.f{{margin-top:auto;display:flex;align-items:center;justify-content:space-between}}
.brand{{font-size:42px;color:{C['granate']}}} .brand svg{{width:68px;height:68px}} .u{{font-size:25px;color:{C['muted']};font-weight:500}}"""
    dek = f'<p class="dek">{esc(t["dek"][:140])}</p>' if t["dek"] and len(t["headline"]) < 75 else ""
    body = (f'<div class="img"></div><div class="t"><span class="pill">{esc(t["kicker"])}</span>'
            f'<h1 class="serif">{esc(t["headline"])}</h1>{dek}'
            f'<div class="f"><div class="brand">{logo}<span>Madam CEO<b>.</b></span></div><span class="u">{esc(domain)}</span></div></div>')
    return page(1080, 1350, css, body)


def story_9x16(t: dict, logo_light: str) -> str:
    """Instagram story: safe zones top/bottom kept clear; space for the link sticker."""
    color = CAT_COLORS.get(t["category"], C["accent"])
    hs = fit(t["story_hook"], [(40, 92), (65, 78), (999, 64)])
    px = "image-rendering:pixelated;" if t["pixel"] else ""
    css = f""".c{{background:{C['granate']};color:#fff}}
.img{{position:absolute;inset:0 0 auto 0;height:1060px;background:#3a0d1c url('{t['src']}') center/cover no-repeat;{px}}}
.img:after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.35) 0%,rgba(0,0,0,0) 25%,rgba(110,22,48,0) 60%,{C['granate']} 100%)}}
.top{{position:absolute;top:150px;left:72px;right:72px;display:flex;align-items:center;justify-content:space-between}}
.brand{{font-size:44px;color:#fff}} .brand svg{{width:70px;height:70px}}
.pill{{background:{color};font-size:24px;padding:12px 22px;border:2px solid rgba(255,255,255,.5)}}
.t{{position:absolute;left:72px;right:72px;top:1000px}}
h1{{font-size:{hs}px;line-height:1.02;margin:0;color:#fff}}
.sub{{font-size:34px;line-height:1.4;color:{C['pink']};margin:26px 0 0}}
.cta{{position:absolute;left:0;right:0;bottom:250px;text-align:center;font-size:30px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:{C['gold']}}}"""
    body = (f'<div class="img"></div><div class="top"><div class="brand">{logo_light}<span>Madam CEO<b>.</b></span></div>'
            f'<span class="pill">{esc(t["kicker"])}</span></div>'
            f'<div class="t"><h1 class="serif">{esc(t["story_hook"])}</h1><p class="sub">{esc(t["story_sub"])}</p></div>'
            f'<div class="cta">Read the full story ↓</div>')
    return page(1080, 1920, css, body)


def tiktok_slides(t: dict, logo: str, logo_light: str, domain: str) -> list[str]:
    color = CAT_COLORS.get(t["category"], C["accent"])
    px = "image-rendering:pixelated;" if t["pixel"] else ""
    hs = fit(t["tt_hook"], [(35, 104), (60, 88), (999, 72)])
    s1 = page(1080, 1920, f""".c{{background:#111 url('{t['src']}') center/cover no-repeat;{px}color:#fff}}
.c:after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.15) 30%,rgba(20,4,10,.88) 72%)}}
.w{{position:absolute;z-index:2;left:80px;right:80px;bottom:420px}}
.pill{{background:{color};font-size:26px;padding:12px 24px}}
h1{{font-size:{hs}px;line-height:1.02;margin:30px 0 0}}
.sw{{position:absolute;z-index:2;right:80px;bottom:300px;font-size:30px;font-weight:600;color:{C['pink']}}}""",
              f'<div class="w"><span class="pill">{esc(t["kicker"])}</span><h1 class="serif">{esc(t["tt_hook"])}</h1></div>'
              f'<div class="sw">Swipe →</div>')
    pts = "".join(f'<li><span>{i}</span><p>{esc(p)}</p></li>' for i, p in enumerate(t["tt_points"][:3], 1))
    s2 = page(1080, 1920, f""".c{{background:{C['paper']};padding:330px 80px 0}}
.k{{font-size:28px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:{color}}}
h2{{font-size:110px;color:{C['granate']};margin:16px 0 70px;line-height:1}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:64px}}
li{{display:flex;gap:30px;align-items:flex-start}}
li span{{flex:none;width:76px;height:76px;border-radius:50%;background:{C['granate']};color:#fff;font-weight:700;font-size:36px;display:flex;align-items:center;justify-content:center}}
li p{{margin:4px 0 0;font-size:54px;line-height:1.25;font-weight:500}}""",
              f'<div class="k">{esc(t["kicker"])}</div><h2 class="serif">What happened</h2><ul>{pts}</ul>')
    s3 = page(1080, 1920, f""".c{{background:{C['granate']};color:#fff;padding:340px 80px 0;text-align:center}}
.lg svg{{width:170px;height:170px}}
.k{{font-size:28px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:{C['gold']};margin-top:50px}}
p.w{{font-size:50px;line-height:1.35;margin:26px 0 0;font-family:'Cormorant Garamond',Georgia,serif;font-weight:500;font-style:italic;color:{C['cream']}}}
.cta{{display:inline-block;margin-top:70px;background:{C['cream']};color:{C['granate']};font-size:40px;font-weight:600;padding:26px 46px;border-radius:999px}}
.s{{margin-top:28px;font-size:30px;color:{C['pink']}}}""",
              f'<div class="lg">{logo_light}</div><div class="k">Why it matters</div><p class="w">{esc(t["tt_why"])}</p>'
              f'<div class="cta">{esc(domain)}</div><div class="s">Full story · link in bio · follow for daily career news</div>')
    return [s1, s2, s3]


def x_16x9(t: dict, logo: str, domain: str) -> str:
    color = CAT_COLORS.get(t["category"], C["accent"])
    hs = fit(t["headline"], [(50, 64), (80, 54), (999, 46)])
    px = "image-rendering:pixelated;" if t["pixel"] else ""
    css = f""".c{{background:{C['paper']};display:flex}}
.img{{width:760px;height:900px;background:#EBD5D2 url('{t['src']}') center/cover no-repeat;{px}border-right:12px solid {color}}}
.t{{flex:1;padding:70px 64px 54px;display:flex;flex-direction:column}}
.pill{{align-self:flex-start;background:{color};font-size:22px;padding:10px 20px}}
h1{{color:{C['granate']};font-size:{hs}px;line-height:1.05;margin:28px 0 0}}
.f{{margin-top:auto;display:flex;align-items:center;justify-content:space-between}}
.brand{{font-size:38px;color:{C['granate']}}} .brand svg{{width:60px;height:60px}} .u{{font-size:22px;color:{C['muted']}}}"""
    body = (f'<div class="img"></div><div class="t"><span class="pill">{esc(t["kicker"])}</span>'
            f'<h1 class="serif">{esc(t["headline"])}</h1>'
            f'<div class="f"><div class="brand">{logo}<span>Madam CEO<b>.</b></span></div><span class="u">{esc(domain)}</span></div></div>')
    return page(1600, 900, css, body)


def game_page(num: int, prev: list | None, logo_light: str, domain: str, w: int, h: int) -> str:
    story = h > 1500
    tiles = "".join("<i></i>" for _ in range(5))
    if prev:
        word = "".join(f"<b>{l}</b>" for l in prev[0])
        box = f'<div class="prev"><small>Yesterday\'s word</small><div class="word">{word}</div><p>{esc(prev[1])}</p></div>'
    else:
        box = ('<div class="prev"><small>How to play</small><p>Guess the five-letter business word in six tries. '
               'Burgundy: right letter, right spot. Gold: in the word, wrong spot.</p></div>')
    css = f""".c{{background:{C['granate']};color:#fff;display:flex;flex-direction:column;align-items:center;
padding:{'260px 80px 300px' if story else '90px 80px 70px'}}}
.top{{font-size:28px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#E9C3CC}}
h1{{font-size:{170 if story else 150}px;line-height:1;margin:22px 0 6px}}
.num{{font-size:42px;font-weight:600;color:{C['gold']};margin:0 0 {80 if story else 56}px}}
.tiles{{display:flex;gap:18px}} .tiles i{{width:150px;height:150px;border:5px solid #E9C3CC;border-radius:12px;display:block}}
.q{{font-size:{46 if story else 40}px;line-height:1.35;text-align:center;margin:{70 if story else 52}px 0 0;color:#F5DDE4}}
.prev{{margin-top:auto;width:100%;background:{C['paper']};color:{C['ink']};border-radius:18px;padding:30px 36px}}
.prev small{{font-size:22px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:{C['accent']}}}
.word{{display:flex;gap:10px;margin:14px 0 12px}} .word b{{width:64px;height:64px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:700;color:#fff;background:{C['accent']}}}
.prev p{{font-size:28px;line-height:1.4;margin:0;color:#3D3F45}}
.f{{display:flex;align-items:center;justify-content:space-between;width:100%;margin-top:34px}}
.brand{{font-size:42px}} .brand svg{{width:66px;height:66px}} .u{{font-size:28px;color:#F5DDE4}}"""
    body = (f'<div class="top">The daily business word game</div><h1 class="serif">Power Word</h1><p class="num">#{num}</p>'
            f'<div class="tiles">{tiles}</div><p class="q">Can you crack today\'s five-letter<br>business word in six tries?</p>'
            f'{box}<div class="f"><div class="brand">{logo_light}<span>Madam CEO<b>.</b></span></div><span class="u">{esc(domain)}/game</span></div>')
    return page(w, h, css, body)


# ---------------------------------------------------------------- rendering
def render_all(jobs: list[tuple[str, str, int, int]]) -> list[str]:
    """jobs = (html, out_path, width, height). Returns the paths that were rendered."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("      [Studio] Playwright not installed: no images")
        return []
    done = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for doc, path, w, h in jobs:
            try:
                pg = browser.new_page(viewport={"width": w, "height": h})
                pg.set_content(doc, wait_until="networkidle", timeout=30000)
                pg.wait_for_timeout(300)
                pg.screenshot(path=path, type="jpeg", quality=88)
                pg.close()
                done.append(path)
            except Exception as e:
                print(f"      [Studio] Image failed {os.path.basename(path)}: {e}")
        browser.close()
    return done


# ---------------------------------------------------------------- copy
def write_copy(ask, client, model: str, extract_json, item: dict, kind: str, url: str) -> dict:
    en = item["content"]["en"]
    facts = {
        "headline": en.get("headline", ""), "standfirst": en.get("dek", ""),
        "key_points": en.get("key_points", []), "why_it_matters": en.get("why_it_matters", en.get("tip", "")),
        "body_start": " ".join(en.get("body", [])[:2])[:900],
    }
    what = {"news": "news story", "style": "office style guide", "voice": "reader story from our Voices section"}[kind]
    prompt = f"""You are the social media editor of "Madam CEO" (themadamceo.com), a premium news brand for
ambitious women in the corporate world. Tone: smart, warm, confident, like a top business magazine.
No clickbait, no exaggeration, no emojis overload (max 2 per caption), never invent facts: use ONLY the text below.

Promote this {what}:
{json.dumps(facts, ensure_ascii=False)}
Link: {url}

Reply ONLY with JSON inside <copy></copy>:
{{
 "kicker": "2-3 words for the image label, e.g. 'Boardroom news'",
 "instagram": "Strong first line (the hook), 2-4 short lines of context, one question to the audience, the line 'Full story: link in bio', then 8-12 relevant hashtags on the last line",
 "story_hook": "max 9 words, big text on the story image",
 "story_sub": "max 18 words under it",
 "tiktok_hook": "max 9 words for the first carousel slide, curiosity without clickbait",
 "tiktok_points": ["3 short facts, max 12 words each"],
 "tiktok_why": "max 25 words: why it matters for a woman's career",
 "tiktok_caption": "max 150 characters + 4-6 hashtags, ends with 'link in bio'",
 "linkedin": "Written by the founder sharing today's story: a strong first line, 3-4 short paragraphs, a question for the comments, the link on its own line, 3 hashtags",
 "x": "max 230 characters, one sharp line or two, no hashtags or at most one, then the link"
}}"""
    data = None
    for _ in range(2):
        try:
            data = extract_json(ask(client, model, prompt, 2500), "copy")
            if data.get("instagram") and data.get("x"):
                break
        except Exception as e:
            print(f"      [Studio] Copy attempt failed: {e}")
            data = None
    if not data:  # safe template from the article's own text
        hd, dek = facts["headline"], facts["standfirst"]
        pts = [p for p in facts["key_points"]][:3] or [dek]
        data = {"kicker": "Today's news", "instagram": f"{hd}\n\n{dek}\n\nFull story: link in bio\n\n#womeninbusiness #leadership #careers #madamceo",
                "story_hook": hd, "story_sub": dek[:110], "tiktok_hook": hd, "tiktok_points": pts,
                "tiktok_why": facts["why_it_matters"][:160], "tiktok_caption": f"{hd[:90]} #careertok #womeninbusiness link in bio",
                "linkedin": f"{hd}\n\n{dek}\n\n{url}\n\n#leadership #careers #womeninbusiness", "x": f"{hd}\n{url}"}
    if url not in data.get("x", ""):
        data["x"] = data["x"][: 270 - len(url)].rstrip() + "\n" + url
    if url not in data.get("linkedin", ""):
        data["linkedin"] = data["linkedin"].rstrip() + "\n\n" + url
    return data


# ---------------------------------------------------------------- pack
def choose(news: list[dict], styles_new: list[dict], voices_new: list[dict]) -> list[tuple[str, dict]]:
    picks = [("news", a) for a in sorted(news, key=lambda a: -a.get("score", 0))[:2]]
    if voices_new:
        picks.append(("voice", voices_new[0]))
    elif styles_new:
        picks.append(("style", styles_new[0]))
    for a in sorted(news, key=lambda a: -a.get("score", 0))[2:]:
        if len(picks) >= STORIES_PER_PACK:
            break
        picks.append(("news", a))
    return picks[:STORIES_PER_PACK]


def build_pack(ask, client, model, extract_json, site_url: str, news: list[dict], styles_new: list[dict],
               voices_new: list[dict], words: list, game_start: datetime, logo: str, logo_light: str) -> dict | None:
    now_md = datetime.now(MADRID)
    state = load_state()
    with_game = state.get("game_date") != now_md.date().isoformat()
    picks = choose(news, styles_new, voices_new)
    if not picks and not with_game:
        return None
    os.makedirs(OUT_DIR, exist_ok=True)
    domain = site_url.replace("https://", "")
    jobs, sections, n = [], [], 0

    if with_game:
        day = max(0, (now_md.date() - game_start.date()).days)
        num, prev = day + 1, (words[(day - 1) % len(words)] if day > 0 else None)
        n += 1
        f_post, f_story = f"{n:02d}-PowerWord-instagram-post.jpg", f"{n:02d}-PowerWord-instagram-story.jpg"
        jobs += [(game_page(num, prev, logo_light, domain, 1080, 1350), os.path.join(OUT_DIR, f_post), 1080, 1350),
                 (game_page(num, prev, logo_light, domain, 1080, 1920), os.path.join(OUT_DIR, f_story), 1080, 1920)]
        url = f"{site_url}/game/"
        prev_line = f"Yesterday's word: {prev[0]}. {prev[1]}" if prev else "A new word every day."
        sections.append({
            "title": f"Power Word #{num}", "url": url, "kind": "game",
            "nets": [
                ("Instagram · Post", [f_post], f"Power Word #{num} 👑\nToday's five-letter business word is waiting. Six tries, two minutes.\n{prev_line}\nHow many tries did you need? Tell us below.\n\nPlay now: link in bio\n\n#powerword #wordgame #dailypuzzle #businessenglish #womeninbusiness #careergrowth #leadership #madamceo"),
                ("Instagram · Story", [f_story], f"Add a link sticker → {url}\nOptional: add a poll sticker “Did you get it?” Yes / Not yet"),
                ("TikTok", [f_story], f"Power Word #{num} 👑 can you get it in 3? #wordgame #dailypuzzle #businesstok #careertok link in bio"),
                ("LinkedIn", [f_post], f"Power Word #{num} is live.\n\nOne five-letter business word, six tries, two minutes. A small daily habit to sharpen your business vocabulary.\n\n{prev_line}\n\nShare your score in the comments.\n\n{url}\n\n#leadership #careers #womeninbusiness"),
                ("X", [f_post], f"Power Word #{num} is live 👑 Can you crack today's five-letter business word in six tries?\n{url}"),
            ]})

    for kind, item in picks:
        en = item["content"]["en"]
        path = {"news": "article", "style": "style", "voice": "voices"}[kind]
        url = f"{site_url}/{path}/{item['id']}.html"
        try:
            cp = write_copy(ask, client, model, extract_json, item, kind, url)
        except Exception as e:
            print(f"      [Studio] Skipped one story ({e})")
            continue
        src, pixel = image_src(item)
        category = {"news": item.get("category", "Leadership"), "style": "Style", "voice": "Voices"}[kind]
        t = {"headline": en.get("headline", ""), "dek": en.get("dek", ""), "kicker": cp.get("kicker") or category,
             "category": category, "src": src, "pixel": pixel, "story_hook": cp.get("story_hook") or en.get("headline", ""),
             "story_sub": cp.get("story_sub", ""), "tt_hook": cp.get("tiktok_hook") or en.get("headline", ""),
             "tt_points": cp.get("tiktok_points") or en.get("key_points", [])[:3], "tt_why": cp.get("tiktok_why", "")}
        n += 1
        base = f"{n:02d}-{slug(t['headline'], 28)}"
        f_post, f_story, f_x = f"{base}-instagram-post.jpg", f"{base}-instagram-story.jpg", f"{base}-x.jpg"
        f_tt = [f"{base}-tiktok-{i}.jpg" for i in (1, 2, 3)]
        jobs += [(post_4x5(t, logo, domain), os.path.join(OUT_DIR, f_post), 1080, 1350),
                 (story_9x16(t, logo_light), os.path.join(OUT_DIR, f_story), 1080, 1920),
                 (x_16x9(t, logo, domain), os.path.join(OUT_DIR, f_x), 1600, 900)]
        jobs += [(doc, os.path.join(OUT_DIR, f), 1080, 1920) for doc, f in zip(tiktok_slides(t, logo, logo_light, domain), f_tt)]
        sections.append({
            "title": t["headline"], "url": url, "kind": kind,
            "nets": [
                ("Instagram · Post", [f_post], cp["instagram"]),
                ("Instagram · Story", [f_story], f"Add a link sticker → {url}\nSticker text: Read more"),
                ("TikTok · Photo carousel", f_tt, cp.get("tiktok_caption", "")),
                ("LinkedIn", [f_post], cp["linkedin"]),
                ("X", [f_x], cp["x"]),
            ]})

    rendered = set(os.path.basename(p) for p in render_all(jobs))
    for s in sections:
        s["nets"] = [(net, [f for f in files if f in rendered], text) for net, files, text in s["nets"]]
    edition = "Morning" if now_md.hour < 11 else ("Midday" if now_md.hour < 17 else "Evening")
    return {"date": now_md, "edition": edition, "sections": sections, "with_game": with_game,
            "files": sorted(rendered)}


# ---------------------------------------------------------------- email
def copy_link(site_url: str, text: str) -> str:
    """A private page on the site that shows the text with a big Copy button (text travels in the #fragment only)."""
    return f"{site_url}/copy.html#" + base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def email_html(pack: dict, site_url: str, logo_cid: str | None) -> str:
    d = pack["date"]
    head_logo = f'<img src="cid:{logo_cid}" width="56" height="56" alt="" style="display:block;border:0">' if logo_cid else ""
    toc = "".join(f'<li style="margin:0 0 6px">{esc(s["title"])}</li>' for s in pack["sections"])
    blocks = []
    for i, s in enumerate(pack["sections"], 1):
        nets = []
        for net, files, text in s["nets"]:
            thumbs = "".join(
                f'<img src="cid:{esc(slug(f, 60))}" alt="{esc(f)}" width="{96 if "story" in f or "tiktok" in f else 120}" '
                f'style="border-radius:6px;margin:0 8px 8px 0;border:1px solid #E2C9C6;vertical-align:top">' for f in files)
            names = "<br>".join(f'📎 {esc(f)}' for f in files)
            nets.append(f"""
<tr><td style="padding:18px 0 4px;border-top:1px solid #EAD6D3">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font:600 12px/1.4 Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#7A1F3D">{esc(net)}</td>
    <td align="right"><a href="{esc(copy_link(site_url, text))}" style="display:inline-block;background:#7A1F3D;color:#fff;text-decoration:none;font:600 13px Arial,sans-serif;padding:8px 16px;border-radius:999px">Copy text</a></td>
  </tr></table>
  <div style="margin:10px 0 6px">{thumbs}</div>
  <div style="font:12px/1.5 Arial,sans-serif;color:#8A7F84;margin:0 0 8px">{names}</div>
  <div style="white-space:pre-wrap;font:15px/1.55 Arial,sans-serif;color:#16171B;background:#FBF6F1;border-radius:8px;padding:14px 16px">{esc(text)}</div>
</td></tr>""")
        label = {"game": "Power Word", "news": "News", "style": "Style", "voice": "Voices"}[s["kind"]]
        blocks.append(f"""
<tr><td style="padding:28px 28px 8px;background:#fff;border-radius:14px">
  <div style="font:600 12px Arial,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#C9A45C">{i:02d} · {label}</div>
  <h2 style="margin:6px 0 4px;font:600 26px/1.15 Georgia,serif;color:#6E1630">{esc(s["title"])}</h2>
  <a href="{esc(s["url"])}" style="font:13px Arial,sans-serif;color:#7A1F3D">{esc(s["url"])}</a>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px">{"".join(nets)}</table>
</td></tr><tr><td style="height:18px"></td></tr>""")
    return f"""<!doctype html><html><body style="margin:0;background:#F4E4E2">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4E4E2"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px">
<tr><td style="background:#6E1630;border-radius:14px;padding:26px 28px">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr><td style="padding-right:14px">{head_logo}</td>
  <td><div style="font:600 28px Georgia,serif;color:#fff">Madam CEO<span style="color:#C9A45C">.</span> Studio</div>
  <div style="font:14px Arial,sans-serif;color:#F5D7DF;margin-top:4px">{pack["edition"]} pack · {d.strftime("%A %d %B %Y · %H:%M")}</div></td></tr></table>
</td></tr>
<tr><td style="height:18px"></td></tr>
<tr><td style="background:#fff;border-radius:14px;padding:22px 28px;font:15px/1.6 Arial,sans-serif;color:#16171B">
  <b style="color:#6E1630">In this pack</b>
  <ol style="margin:10px 0 12px;padding-left:20px">{toc}</ol>
  <div style="color:#5C5A60;font-size:13px">How to post from your phone: save the attached images (file names are numbered by story and network), tap <b>Copy text</b>, paste.
  Instagram stories: add the <b>link sticker</b> with the URL shown. TikTok: post the 3 slides as a photo carousel and add a trending sound.
  Best times: Instagram & TikTok 12:00–14:00 and 19:00–21:00 · LinkedIn 8:00–10:00 · X anytime.</div>
</td></tr>
<tr><td style="height:18px"></td></tr>
{"".join(blocks)}
<tr><td style="font:12px Arial,sans-serif;color:#8A7F84;text-align:center;padding:8px 0 24px">Generated automatically after each update of {esc(site_url.replace("https://", ""))}.</td></tr>
</table></td></tr></table></body></html>"""


def send(pack: dict, site_url: str, logo_png: str | None) -> bool:
    key, to = os.getenv("RESEND_API_KEY"), os.getenv("PACK_EMAIL")
    if not (key and to):
        print("      [Studio] RESEND_API_KEY / PACK_EMAIL not set: pack built but not emailed")
        return False
    attachments, logo_cid = [], None
    if logo_png and os.path.exists(logo_png):
        logo_cid = "madamceo-logo"
        with open(logo_png, "rb") as f:
            attachments.append({"filename": "logo.png", "content": base64.b64encode(f.read()).decode(), "content_id": logo_cid})
    for name in pack["files"]:
        with open(os.path.join(OUT_DIR, name), "rb") as f:
            attachments.append({"filename": name, "content": base64.b64encode(f.read()).decode(), "content_id": slug(name, 60)})
    d = pack["date"]
    subject = f"Madam CEO · {pack['edition']} pack · {d.strftime('%a %d %b')} · {len(pack['sections'])} posts ready"
    body = json.dumps({"from": SENDER, "to": [t.strip() for t in to.split(",") if t.strip()], "reply_to": REPLY_TO,
                       "subject": subject, "html": email_html(pack, site_url, logo_cid),
                       "attachments": attachments}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "MadamCEO-Studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            print(f"[Studio] Pack emailed ({len(pack['files'])} images): {json.loads(r.read()).get('id')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"      [Studio] Email failed: {e.code} {e.read().decode('utf-8', 'ignore')[:300]}")
    except Exception as e:
        print(f"      [Studio] Email failed: {e}")
    return False


def run(ask, client, model, extract_json, site_url, news, styles_new, voices_new, words, game_start,
        logo: str, logo_light: str, logo_png: str | None) -> None:
    pack = build_pack(ask, client, model, extract_json, site_url, news, styles_new, voices_new,
                      words, game_start, logo, logo_light)
    if not pack:
        print("[Studio] Nothing new for a pack")
        return
    if send(pack, site_url, logo_png) and pack["with_game"]:
        state = load_state()
        state["game_date"] = pack["date"].date().isoformat()
        save_state(state)


# ---------------------------------------------------------------- copy page (site/copy.html)
COPY_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>Copy — Madam CEO Studio</title>
<style>
body{margin:0;background:#F4E4E2;font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#16171B}
header{background:#6E1630;color:#fff;padding:18px 20px;font:600 22px Georgia,serif} header b{color:#C9A45C}
main{max-width:640px;margin:0 auto;padding:20px 16px 40px}
button{width:100%;min-height:56px;border:0;border-radius:999px;background:#7A1F3D;color:#fff;font:600 18px system-ui,sans-serif;cursor:pointer}
button.ok{background:#2F6F6A}
pre{white-space:pre-wrap;word-wrap:break-word;background:#fff;border-radius:12px;padding:16px;font:16px/1.55 system-ui,sans-serif;margin:16px 0 0}
</style></head><body>
<header>Madam CEO<b>.</b> Studio</header>
<main><button id="b" type="button">Copy text</button><pre id="t"></pre></main>
<script>
var h = location.hash.slice(1).replace(/-/g,'+').replace(/_/g,'/');
while (h.length % 4) h += '=';
var txt = '';
try { txt = decodeURIComponent(escape(atob(h))); } catch (e) { txt = ''; }
document.getElementById('t').textContent = txt || 'Nothing to copy.';
document.getElementById('b').addEventListener('click', function () {
  var b = this;
  function done() { b.textContent = 'Copied ✓'; b.className = 'ok'; }
  if (navigator.clipboard) { navigator.clipboard.writeText(txt).then(done, fallback); } else { fallback(); }
  function fallback() { var r = document.createRange(); r.selectNodeContents(document.getElementById('t'));
    var s = getSelection(); s.removeAllRanges(); s.addRange(r); document.execCommand('copy'); done(); }
});
</script></body></html>"""
