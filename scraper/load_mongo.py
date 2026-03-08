import json
import csv
import os
from pathlib import Path
from pymongo import MongoClient
import certifi

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client    = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db        = client["sentience-mongoDB"]
data_dir  = "data/raw"

# ── Load Reddit posts ──────────────────────────────────
for filename in os.listdir(data_dir):
    if not filename.endswith("_posts.json"):
        continue

    brand = filename.replace("_posts.json", "")
    path  = os.path.join(data_dir, filename)

    with open(path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    db[brand].drop()
    db[brand].insert_many(posts)
    print(f"✅ {brand} → {len(posts)} posts loaded into db.pulse.{brand}")

# ── Load stock CSVs ────────────────────────────────────
for filename in os.listdir(data_dir):
    if not filename.endswith("_stock.csv"):
        continue

    ticker = filename.replace("_stock.csv", "")
    path   = os.path.join(data_dir, filename)

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if rows:
        col_name = f"{ticker}_stock"
        db[col_name].drop()
        db[col_name].insert_many(rows)
        print(f"📈 {ticker} → {len(rows)} rows loaded into db.pulse.{col_name}")

print("\n✓ All done!")