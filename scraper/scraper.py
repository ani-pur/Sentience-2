import requests
import json
import time
import os
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count

# ── CONFIG ────────────────────────────────────────────────────────────────────

OUTPUT_DIR      = "data/raw"
POST_LIMIT      = 500
COMMENT_LIMIT   = 20
FLUSH_INTERVAL  = 60
COMMENT_DELAY   = 2
WORKERS         = min(8, cpu_count())  # parallel processes

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Samsung Galaxy S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# ── BRANDS ────────────────────────────────────────────────────────────────────

AI_BRANDS = {
    "anthropic": {"subreddits": ["ClaudeAI", "MachineLearning", "artificial", "LocalLLaMA"], "ticker": None},
    "google":    {"subreddits": ["Gemini", "google", "MachineLearning", "LocalLLaMA"], "ticker": "GOOGL"},
    "xai":       {"subreddits": ["grok", "xAI", "MachineLearning", "artificial"], "ticker": None},
    "deepseek":  {"subreddits": ["deepseek", "MachineLearning", "LocalLLaMA", "artificial"], "ticker": None},
    "microsoft": {"subreddits": ["Copilot", "microsoft", "MachineLearning", "LocalLLaMA"], "ticker": "MSFT"},
    "alibaba":   {"subreddits": ["qwen", "MachineLearning", "LocalLLaMA", "artificial"], "ticker": None},
}

HARDWARE_BRANDS = {
    "nvidia":    {"subreddits": ["nvidia", "hardware", "MachineLearning", "LocalLLaMA", "wallstreetbets", "stocks"], "ticker": "NVDA"},
    "amd":       {"subreddits": ["Amd", "hardware", "MachineLearning", "wallstreetbets", "stocks"], "ticker": "AMD"},
    "intel":     {"subreddits": ["intel", "hardware", "MachineLearning", "wallstreetbets", "stocks"], "ticker": "INTC"},
    "tsmc":      {"subreddits": ["hardware", "investing", "stocks", "wallstreetbets", "economics"], "ticker": "TSM"},
    "qualcomm":  {"subreddits": ["qualcomm", "hardware", "investing", "wallstreetbets", "stocks"], "ticker": "QCOM"},
    "broadcom":  {"subreddits": ["hardware", "investing", "wallstreetbets", "stocks"], "ticker": "AVGO"},
    "amazon":    {"subreddits": ["aws", "MachineLearning", "wallstreetbets", "stocks"], "ticker": "AMZN"},
    "meta":      {"subreddits": ["facebook", "MachineLearning", "LocalLLaMA", "wallstreetbets", "stocks"], "ticker": "META"},
    "samsung":   {"subreddits": ["samsung", "hardware", "investing", "wallstreetbets", "stocks"], "ticker": "SSNLF"},
    "micron":    {"subreddits": ["hardware", "investing", "wallstreetbets", "stocks"], "ticker": "MU"},
    "apple":     {"subreddits": ["apple", "MachineLearning", "wallstreetbets", "stocks"], "ticker": "AAPL"},
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def to_iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

def flush(posts, out_path, label=""):
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f"  [{out_path.split('/')[-1]}] 💾 {len(posts)} posts saved {label}")

# ── FETCH POSTS ───────────────────────────────────────────────────────────────

def fetch_posts(subreddit, limit, headers):
    posts, after, batch = [], None, 100

    while len(posts) < limit:
        params = {"limit": batch}
        if after:
            params["after"] = after
        try:
            res = requests.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json",
                headers=headers, params=params, timeout=10
            )
            if res.status_code == 429:
                print(f"  [r/{subreddit}] ⚠ Rate limited. Waiting 30s...")
                time.sleep(30)
                continue
            if res.status_code != 200:
                print(f"  [r/{subreddit}] ✗ HTTP {res.status_code}. Skipping.")
                break

            data     = res.json()["data"]
            children = data["children"]
            if not children:
                break

            for child in children:
                p = child["data"]
                posts.append({
                    "type":         "post",
                    "id":           p.get("id"),
                    "brand":        None,
                    "ticker":       None,
                    "subreddit":    subreddit,
                    "title":        p.get("title"),
                    "body":         p.get("selftext"),
                    "author":       p.get("author"),
                    "created_utc":  to_iso(p.get("created_utc")),
                    "score":        p.get("score"),
                    "upvote_ratio": p.get("upvote_ratio"),
                    "num_comments": p.get("num_comments"),
                    "url":          p.get("url"),
                    "comments":     [],
                })

            after = data.get("after")
            if not after:
                break
            time.sleep(1)

        except Exception as e:
            print(f"  [r/{subreddit}] ✗ Error: {e}")
            break

    return posts[:limit]

# ── FETCH COMMENTS ────────────────────────────────────────────────────────────

def fetch_comments(subreddit, post_id, limit, headers):
    try:
        res = requests.get(
            f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json",
            headers=headers, params={"limit": limit}, timeout=10
        )
        if res.status_code == 429:
            time.sleep(30)
            return fetch_comments(subreddit, post_id, limit, headers)
        if res.status_code != 200:
            return []

        comments = []
        for child in res.json()[1]["data"]["children"][:limit]:
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

    except Exception:
        return []

# ── SCRAPE BRAND (runs in its own process) ────────────────────────────────────

def scrape_brand(args):
    brand, config, include_comments, agent_index = args
    headers  = {"User-Agent": USER_AGENTS[agent_index % len(USER_AGENTS)]}
    ticker   = config["ticker"] or "private"
    out_path = os.path.join(OUTPUT_DIR, f"{brand}_posts.json")
    all_posts, seen = [], set()

    print(f"\n  ▶ START {brand.upper()} | ticker: {ticker} | comments: {include_comments} | agent: {agent_index}")

    for sub in config["subreddits"]:
        print(f"  [{brand}] Scraping r/{sub}...")
        posts = fetch_posts(sub, POST_LIMIT, headers)

        new_posts = []
        for p in posts:
            if p["id"] not in seen:
                p["brand"]  = brand
                p["ticker"] = config["ticker"]
                seen.add(p["id"])
                new_posts.append(p)

        all_posts.extend(new_posts)
        flush(all_posts, out_path, "(after posts)")

        if include_comments:
            last_flush = time.time()
            for i, post in enumerate(new_posts):
                post["comments"] = fetch_comments(sub, post["id"], COMMENT_LIMIT, headers)
                time.sleep(COMMENT_DELAY)

                if time.time() - last_flush >= FLUSH_INTERVAL:
                    flush(all_posts, out_path, f"({i+1}/{len(new_posts)} comments)")
                    last_flush = time.time()

                if (i + 1) % 50 == 0:
                    print(f"  [{brand}] {i+1}/{len(new_posts)} comments fetched...")

    flush(all_posts, out_path, "(final)")
    print(f"  ✅ DONE {brand.upper()} — {len(all_posts)} posts → {out_path}")

# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 55)
    print("  Pulse Reddit Scraper — PARALLEL MODE")
    print("=" * 55)
    print(f"  Workers       : {WORKERS} parallel processes")
    print(f"  Post limit    : {POST_LIMIT} per subreddit")
    print(f"  Comment limit : {COMMENT_LIMIT} per post (AI brands only)")
    print(f"  Comment delay : {COMMENT_DELAY}s between requests")
    print(f"  AI brands     : {len(AI_BRANDS)}")
    print(f"  HW brands     : {len(HARDWARE_BRANDS)}")
    print("=" * 55)

    # Build task list — (brand, config, include_comments)
    tasks = (
        [(b, c, True,  i)               for i, (b, c) in enumerate(AI_BRANDS.items())] +
        [(b, c, False, i + len(AI_BRANDS)) for i, (b, c) in enumerate(HARDWARE_BRANDS.items())]
    )

    print(f"\n  Launching {len(tasks)} brands across {WORKERS} workers...\n")

    with Pool(processes=WORKERS) as pool:
        pool.map(scrape_brand, tasks)

    print("\n" + "=" * 55)
    print(f"  ✓ All {len(tasks)} brands done! Files in: {OUTPUT_DIR}")
    print("=" * 55)