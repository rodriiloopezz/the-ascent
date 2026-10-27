"""
Madam CEO – automatic posting to Instagram and X.
Runs after the website is published (the images must be online for Instagram).
Reads data/social/queue.json, posts what is pending, and marks it as posted.

Secrets (GitHub → Settings → Secrets, or .env locally):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET   → X (Twitter), OAuth 1.0a with Read and Write
  IG_ACCESS_TOKEN                                           → Instagram (Instagram API with Instagram Login)
A network is skipped automatically if its secrets are missing.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

import social

SITE_URL = "https://themadamceo.com"
MAX_AGE_HOURS = 30          # only post fresh kits
X_MAX_PER_DAY = 2           # X charges per post (more with links): Power Word + top story by default
IG_MAX_PER_DAY = 4          # Instagram is free; keep a natural rhythm
IG_TOKEN_FILE = "ig_token_refreshed.txt"   # read by the workflow to update the secret


# ---------------------------------------------------------------- helpers
def http(method: str, url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"error": body[:500]}


def posted_today(queue: list[dict], net: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    n = 0
    for it in queue:
        when = (it.get("posted_at") or {}).get(net)
        if when and datetime.fromisoformat(when) >= since:
            n += 1
    return n


def pending(queue: list[dict], net: str) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    items = [it for it in queue
             if not it.get("posted", {}).get(net) and it.get("image")
             and datetime.fromisoformat(it["created"]) >= cutoff]
    # Power Word first (one a day), then the newest stories
    games = [i for i in items if i.get("kind") == "game"]
    others = sorted([i for i in items if i.get("kind") != "game"], key=lambda i: i["created"], reverse=True)
    return games + others


def mark(item: dict, net: str, ref: str) -> None:
    item.setdefault("posted", {})[net] = True
    item.setdefault("posted_at", {})[net] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    item.setdefault("post_ids", {})[net] = ref


# ---------------------------------------------------------------- X (OAuth 1.0a)
def _pct(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~")


def x_auth_header(method: str, url: str, query: dict | None = None) -> str:
    k, ks = os.environ["X_API_KEY"], os.environ["X_API_SECRET"]
    t, ts = os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"]
    oauth = {
        "oauth_consumer_key": k, "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())), "oauth_token": t, "oauth_version": "1.0",
    }
    params = {**oauth, **(query or {})}
    base_params = "&".join(f"{_pct(a)}={_pct(b)}" for a, b in sorted(params.items()))
    base = "&".join([method.upper(), _pct(url), _pct(base_params)])
    key = f"{_pct(ks)}&{_pct(ts)}"
    sig = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{_pct(a)}="{_pct(b)}"' for a, b in sorted(oauth.items()))


def x_upload_image(path: str) -> str:
    with open(path, "rb") as f:
        img = f.read()
    boundary = "----madamceo" + secrets.token_hex(8)

    def multipart(fields: dict, file_field: str) -> bytes:
        out = b""
        for name, value in fields.items():
            out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"card.jpg\"\r\n"
                f"Content-Type: image/jpeg\r\n\r\n").encode() + img + b"\r\n"
        return out + f"--{boundary}--\r\n".encode()

    ctype = f"multipart/form-data; boundary={boundary}"
    # v2 media upload
    url = "https://api.x.com/2/media/upload"
    status, data = http("POST", url, multipart({"media_category": "tweet_image", "media_type": "image/jpeg"}, "media"),
                        {"Authorization": x_auth_header("POST", url), "Content-Type": ctype})
    if status < 300 and (data.get("data") or {}).get("id"):
        return data["data"]["id"]
    # fallback: v1.1 media upload
    url = "https://upload.twitter.com/1.1/media/upload.json"
    status2, data2 = http("POST", url, multipart({}, "media"),
                          {"Authorization": x_auth_header("POST", url), "Content-Type": ctype})
    if status2 < 300 and data2.get("media_id_string"):
        return data2["media_id_string"]
    raise RuntimeError(f"X media upload failed: {status} {data} / {status2} {data2}")


def x_post(item: dict) -> str:
    media_id = x_upload_image(os.path.join(social.SOCIAL_DIR, item["image"]))
    url = "https://api.x.com/2/tweets"
    body = json.dumps({"text": item["captions"]["x"][:280], "media": {"media_ids": [media_id]}}).encode()
    status, data = http("POST", url, body, {"Authorization": x_auth_header("POST", url), "Content-Type": "application/json"})
    if status >= 300:
        raise RuntimeError(f"X post failed: {status} {data}")
    return data["data"]["id"]


# ---------------------------------------------------------------- Instagram (Instagram Login)
IG = "https://graph.instagram.com"


def ig_token() -> str:
    return os.environ["IG_ACCESS_TOKEN"]


def ig_refresh_token() -> None:
    """Long-lived tokens last 60 days; refreshing extends them. The workflow saves the new one."""
    status, data = http("GET", f"{IG}/refresh_access_token?" +
                        urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": ig_token()}))
    if status < 300 and data.get("access_token"):
        os.environ["IG_ACCESS_TOKEN"] = data["access_token"]
        with open(IG_TOKEN_FILE, "w") as f:
            f.write(data["access_token"])
        days = int(data.get("expires_in", 0)) // 86400
        print(f"[Instagram] Token refreshed (valid {days} days)")
    else:
        print(f"[Instagram] Token refresh skipped: {status} {data}")


def ig_post(item: dict) -> str:
    status, me = http("GET", f"{IG}/me?" + urllib.parse.urlencode({"fields": "user_id,username", "access_token": ig_token()}))
    if status >= 300:
        raise RuntimeError(f"Instagram /me failed: {status} {me}")
    uid = me.get("user_id") or me.get("id")
    image_url = f"{SITE_URL}/social/{item['image']}"
    status, data = http("POST", f"{IG}/{uid}/media", urllib.parse.urlencode({
        "image_url": image_url, "caption": item["captions"]["instagram"][:2200], "access_token": ig_token()}).encode())
    if status >= 300 or not data.get("id"):
        raise RuntimeError(f"Instagram container failed: {status} {data}")
    container = data["id"]
    for _ in range(20):  # wait until Instagram has fetched and processed the image
        s, st = http("GET", f"{IG}/{container}?" + urllib.parse.urlencode({"fields": "status_code", "access_token": ig_token()}))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing error: {st}")
        time.sleep(3)
    status, data = http("POST", f"{IG}/{uid}/media_publish", urllib.parse.urlencode({
        "creation_id": container, "access_token": ig_token()}).encode())
    if status >= 300 or not data.get("id"):
        raise RuntimeError(f"Instagram publish failed: {status} {data}")
    return data["id"]


def image_online(item: dict) -> bool:
    try:
        req = urllib.request.Request(f"{SITE_URL}/social/{item['image']}", method="HEAD",
                                     headers={"User-Agent": "MadamCEO/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------- main
def main() -> None:
    load_dotenv()
    queue = social.load_queue()
    if not queue:
        print("Nothing in the social queue.")
        return
    dry = "--dry-run" in sys.argv

    has_x = all(os.getenv(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"))
    has_ig = bool(os.getenv("IG_ACCESS_TOKEN"))
    if not has_x:
        print("[X] No credentials: skipped")
    if not has_ig:
        print("[Instagram] No token: skipped")

    if has_ig and not dry:
        ig_refresh_token()

    for net, enabled, limit, poster in (("instagram", has_ig, IG_MAX_PER_DAY, ig_post),
                                        ("x", has_x, X_MAX_PER_DAY, x_post)):
        if not enabled:
            continue
        room = max(0, limit - posted_today(queue, net))
        todo = pending(queue, net)[:room]
        for item in todo:
            if net == "instagram" and not image_online(item):
                print(f"[{net}] Image not online yet, will retry: {item['image']}")
                continue
            if dry:
                print(f"[{net}] Would post: {item['headline']}")
                continue
            try:
                ref = poster(item)
                mark(item, net, ref)
                print(f"[{net}] Posted: {item['headline']} ({ref})")
            except Exception as e:
                print(f"[{net}] Failed: {item['headline']} → {e}")
        if not todo:
            print(f"[{net}] Nothing to post (or daily limit reached)")

    if not dry:
        with open(social.QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
