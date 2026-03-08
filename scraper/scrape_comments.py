import requests
import json
import time
import os
from datetime import datetime, timezone

# ── CONFIG ────────────────────────────────────────────────────────────────────

DATA_DIR      = "data/raw"
COMMENT_LIMIT = 20
FLUSH_EVERY   = 25       # save every 25 posts
BASE_DELAY    = 1.5      # seconds between requests when healthy
BACKOFF_TIME  = 60      # wait 5 full minutes after rate limit before retrying

AI_BRANDS = [
    "openai",
    "anthropic",
    "google",
    "xai",
    "deepseek",
    "microsoft",
    "alibaba",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def to_iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

def fetch_comments(subreddit, post_id):
    """Fetch top comments for a single post with smart backoff."""
    while True:
        try:
            res = requests.get(
                f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json",
                headers=HEADERS,
                params={"limit": COMMENT_LIMIT},
                timeout=10
            )

            if res.status_code == 429:
                print(f"\n  ⚠ Rate limited. Waiting {BACKOFF_TIME//60} minutes for Reddit to fully reset...")
                time.sleep(BACKOFF_TIME)
                print(f"  ✓ Resuming...")
                continue  # retry after full backoff

            if res.status_code != 200:
                return []  # skip bad posts silently

            comments = []
            for child in res.json()[1]["data"]["children"][:COMMENT_LIMIT]:
                if child.get("kind") != "t1":
                    continue
                c = child["data"]
                comments.append({
                    "id":          c.get("id"),
                    "author":      c.get("author"),
                    "body":        c.get("body"),
                    "score":       c.get("score"),
                    "created_utc": to_iso(c.get("created_utc")),
                })
            return comments

        except Exception as e:
            print(f"  ✗ Error on {post_id}: {e}. Skipping.")
            return []

# ── PER BRAND ─────────────────────────────────────────────────────────────────

def scrape_brand(brand):
    path = os.path.join(DATA_DIR, f"{brand}_posts.json")

    if not os.path.exists(path):
        print(f"\n  ✗ [{brand}] File not found. Skipping.")
        return

    with open(path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    to_process = [p for p in posts if p.get("type") == "post" and not p.get("comments")]
    already    = len(posts) - len(to_process)

    print(f"\n{'='*55}")
    print(f"  Brand    : {brand.upper()}")
    print(f"  To do    : {len(to_process)} posts")
    print(f"  Done     : {already} posts already have comments")
    print(f"{'='*55}")

    if not to_process:
        print(f"  ✅ Already complete!\n")
        return

    for i, post in enumerate(to_process):
        subreddit = post.get("subreddit")
        post_id   = post.get("id")

        if not subreddit or not post_id:
            continue

        post["comments"] = fetch_comments(subreddit, post_id)
        time.sleep(BASE_DELAY)

        # Progress + flush every FLUSH_EVERY posts
        if (i + 1) % FLUSH_EVERY == 0:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)
            pct = round((i + 1) / len(to_process) * 100)
            print(f"  💾 {i+1}/{len(to_process)} ({pct}%) saved...")

    # Final save
    with open(path, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)

    total = sum(len(p.get("comments", [])) for p in posts if p.get("type") == "post")
    print(f"\n  ✅ {brand.upper()} complete — {total} total comments saved\n")

# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Comment Scraper — SEQUENTIAL MODE")
    print("  One brand at a time. No parallel = no rate wars.")
    print("=" * 55)

    for brand in AI_BRANDS:
        scrape_brand(brand)

    print("=" * 55)
    print("  ✓ All brands complete!")
    print("=" * 55)