import json
import os
from pymongo import MongoClient

client   = MongoClient("mongodb://localhost:27017/")
db       = client["pulse"]
data_dir = "data/raw"

for filename in os.listdir(data_dir):
    if not filename.endswith("_posts.json"):
        continue

    brand = filename.replace("_posts.json", "")
    path  = os.path.join(data_dir, filename)

    with open(path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    db[brand].drop()             # clear old data
    db[brand].insert_many(posts) # insert fresh
    print(f"✅ {brand} → {len(posts)} posts loaded into db.pulse.{brand}")

print("\n✓ All done!")