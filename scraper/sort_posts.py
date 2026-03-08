import json
import os

DATA_DIR = "data/raw"

files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]

for filename in files:
    path = os.path.join(DATA_DIR, filename)

    with open(path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    sorted_posts = sorted(posts, key=lambda p: p.get("created_utc") or "")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted_posts, f, indent=2, ensure_ascii=False)

    print(f"✅ Sorted {len(sorted_posts)} posts → {filename}  |  oldest: {sorted_posts[0].get('created_utc')}  |  latest: {sorted_posts[-1].get('created_utc')}")

print("\n✓ All files sorted oldest → latest.")