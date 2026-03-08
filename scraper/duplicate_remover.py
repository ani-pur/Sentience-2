import json
import os

DATA_DIR = "data/raw"

files = [f for f in os.listdir(DATA_DIR) if f.endswith("_posts.json")]

total_removed = 0

for filename in sorted(files):
    path = os.path.join(DATA_DIR, filename)

    with open(path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    before = len(posts)

    # Deduplicate by post ID
    seen    = set()
    deduped = []
    for post in posts:
        pid = post.get("id")
        if pid and pid not in seen:
            seen.add(pid)
            deduped.append(post)

    # Also deduplicate comments within each post
    for post in deduped:
        comments = post.get("comments", [])
        if comments:
            seen_comments = set()
            clean_comments = []
            for c in comments:
                cid = c.get("id")
                if cid and cid not in seen_comments:
                    seen_comments.add(cid)
                    clean_comments.append(c)
            post["comments"] = clean_comments

    after   = len(deduped)
    removed = before - after
    total_removed += removed

    # Save cleaned file
    with open(path, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    status = f"removed {removed} duplicates" if removed > 0 else "no duplicates found"
    print(f"  {'✅' if removed == 0 else '🧹'} {filename:<35} {before} → {after} posts  ({status})")

print(f"\n  Total duplicates removed: {total_removed}")
print(f"  ✓ All files cleaned and saved")