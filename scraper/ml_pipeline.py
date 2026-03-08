"""
Sentience ML Pipeline
Run in order:
  1. python ml_pipeline.py install     → installs all libraries
  2. python ml_pipeline.py score       → FinBERT scores every post
  3. python ml_pipeline.py features    → extracts all parameters
  4. python ml_pipeline.py aggregate   → builds daily buckets
  5. python ml_pipeline.py anomalies   → z-score anomaly detection
  6. python ml_pipeline.py train       → trains LSTM
  7. python ml_pipeline.py predict     → generates CSS (0-100) + 14-day projection
  8. python ml_pipeline.py correlate   → sentiment-stock correlation
  9. python ml_pipeline.py sms         → Sentiment Momentum Score + alerts
"""

import sys
import os
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME   = "sentience-mongoDB"
AI_BRANDS = ["openai", "anthropic", "google", "xai", "deepseek", "microsoft", "alibaba"]

def get_db():
    import certifi
    return MongoClient(MONGO_URI, tlsCAFile=certifi.where())[DB_NAME]

# ══════════════════════════════════════════════════════════
# STEP 1 — INSTALL
# ══════════════════════════════════════════════════════════

def install():
    print("Installing ML libraries...")
    os.system("pip install transformers torch vaderSentiment scikit-learn pandas numpy pymongo certifi")
    print("✅ Done. Run: python ml_pipeline.py score")

# ══════════════════════════════════════════════════════════
# STEP 2 — FINBERT SCORING
# ══════════════════════════════════════════════════════════

def score():
    from transformers import pipeline
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    print("Loading FinBERT model (first run downloads ~500MB)...")
    finbert = pipeline(
        "sentiment-analysis",
        model="ProsusAI/finbert",
        tokenizer="ProsusAI/finbert",
        truncation=True,
        max_length=512
    )
    vader = SentimentIntensityAnalyzer()
    db    = get_db()

    for brand in AI_BRANDS:
        col   = db[brand]
        posts = list(col.find({"type": "post", "finbert_score": {"$exists": False}}))
        print(f"\n  [{brand.upper()}] Scoring {len(posts)} posts...")

        for i, post in enumerate(posts):
            # Combine title + body for scoring
            text = f"{post.get('title', '')} {post.get('body', '')}".strip()[:512]
            if not text:
                continue

            # FinBERT score
            try:
                result = finbert(text)[0]
                label  = result["label"].lower()   # positive / negative / neutral
                conf   = result["score"]
                if label == "positive":
                    fb_score = conf
                elif label == "negative":
                    fb_score = -conf
                else:
                    fb_score = 0.0
            except Exception as e:
                print(f"    ⚠ FinBERT error on post {post.get('_id')}: {e}")
                fb_score = 0.0

            # VADER score (on comments too)
            comment_texts = [c.get("body", "") for c in post.get("comments", []) if c.get("body")]
            comment_scores = [vader.polarity_scores(c)["compound"] for c in comment_texts]
            avg_comment_score = sum(comment_scores) / len(comment_scores) if comment_scores else 0.0

            # Weighted final raw score (70% post, 30% comments)
            raw_score = (0.7 * fb_score) + (0.3 * avg_comment_score)

            col.update_one({"_id": post["_id"]}, {"$set": {
                "finbert_score":       round(fb_score, 4),
                "vader_comment_score": round(avg_comment_score, 4),
                "raw_score":           round(raw_score, 4),
            }})

            if (i + 1) % 50 == 0:
                print(f"    {i+1}/{len(posts)} scored...")

        print(f"  ✅ {brand.upper()} scoring complete")

    print("\n✅ All brands scored. Run: python ml_pipeline.py features")

# ══════════════════════════════════════════════════════════
# STEP 3 — FEATURE EXTRACTION
# ══════════════════════════════════════════════════════════

def features():
    import re
    db = get_db()

    # Keyword lists for rule-based signals
    CHURN_KEYWORDS      = ["switching to", "moved to", "switching from", "cancelled", "cancelling",
                           "unsubscribed", "leaving", "switched to", "going back to", "done with"]
    ADVOCACY_KEYWORDS   = ["recommend", "best ai", "love this", "amazing", "incredible",
                           "game changer", "blown away", "absolutely love", "best model"]
    TRUST_LOSS_KEYWORDS = ["trust", "privacy", "data breach", "sold my data", "lying",
                           "disappointed", "unreliable", "keeps failing", "worse than before"]
    COMPETITOR_NAMES    = ["chatgpt", "gpt-4", "gpt-5", "claude", "gemini", "copilot",
                           "deepseek", "grok", "llama", "mistral", "qwen", "perplexity"]

    def engagement_weight(post):
        score      = post.get("score", 0) or 0
        ratio      = post.get("upvote_ratio", 0.5) or 0.5
        comments   = post.get("num_comments", 0) or 0
        raw        = (score * ratio) + (comments * 2)
        return round(min(raw / 1000, 10), 2)  # normalize to 0-10

    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    vader_feat = SentimentIntensityAnalyzer()

    def comment_alignment(post, raw_score):
        comments = post.get("comments", [])
        if not comments:
            return "unknown"
        scores   = [vader_feat.polarity_scores(c.get("body",""))["compound"] for c in comments if c.get("body")]
        if not scores:
            return "unknown"
        avg = sum(scores) / len(scores)
        if raw_score > 0.1 and avg > 0.05:
            return "agree"
        elif raw_score < -0.1 and avg < -0.05:
            return "agree"
        elif abs(avg) < 0.05:
            return "mixed"
        else:
            return "disagree"

    for brand in AI_BRANDS:
        col   = db[brand]
        posts = list(col.find({"type": "post", "features": {"$exists": False}, "raw_score": {"$exists": True}}))
        print(f"\n  [{brand.upper()}] Extracting features for {len(posts)} posts...")

        for i, post in enumerate(posts):
            text       = f"{post.get('title','').lower()} {post.get('body','').lower()}"
            raw_score  = post.get("raw_score", 0)
            e_weight   = engagement_weight(post)

            # Churn signal
            churn = any(kw in text for kw in CHURN_KEYWORDS)

            # Advocacy signal
            advocacy = any(kw in text for kw in ADVOCACY_KEYWORDS)

            # Trust loss signal
            trust_loss = any(kw in text for kw in TRUST_LOSS_KEYWORDS)

            # Competitor mentions
            competitors = [c for c in COMPETITOR_NAMES if c in text and c != brand.lower()]

            # Emotion intensity — proxy via text length + punctuation
            exclamations = text.count("!") + text.count("?")
            caps_ratio   = sum(1 for c in post.get("title","") if c.isupper()) / max(len(post.get("title","1")), 1)
            intensity    = min(round((exclamations * 1.5) + (caps_ratio * 5) + (abs(raw_score) * 3), 1), 10)

            # Comment alignment
            alignment = comment_alignment(post, raw_score)

            col.update_one({"_id": post["_id"]}, {"$set": {
                "features": {
                    "churn_signal":             churn,
                    "advocacy_signal":          advocacy,
                    "trust_loss_signal":        trust_loss,
                    "competitor_mentioned":     len(competitors) > 0,
                    "competitor_names":         competitors,
                    "emotion_intensity":        intensity,
                    "engagement_weight":        e_weight,
                    "comment_alignment":        alignment,
                }
            }})

            if (i + 1) % 100 == 0:
                print(f"    {i+1}/{len(posts)} features extracted...")

        print(f"  ✅ {brand.upper()} features complete")

    print("\n✅ All features extracted. Run: python ml_pipeline.py aggregate")

# ══════════════════════════════════════════════════════════
# STEP 4 — DAILY AGGREGATION
# ══════════════════════════════════════════════════════════

def aggregate():
    from collections import defaultdict
    db  = get_db()
    col = db["daily_sentiment"]
    col.drop()

    for brand in AI_BRANDS:
        posts  = list(db[brand].find({"type": "post", "raw_score": {"$exists": True}}))
        buckets = defaultdict(list)

        for post in posts:
            ts = post.get("created_utc")
            if not ts:
                continue
            try:
                dt  = datetime.fromisoformat(ts)
                day = dt.strftime("%Y-%m-%d")
                buckets[day].append(post)
            except ValueError:
                continue

        rows = []
        for day, day_posts in sorted(buckets.items()):
            scores      = [p.get("raw_score", 0) for p in day_posts]
            weights     = [p.get("features", {}).get("engagement_weight", 1) for p in day_posts]
            intensities = [p.get("features", {}).get("emotion_intensity", 0) for p in day_posts]
            churn_rate  = sum(1 for p in day_posts if p.get("features", {}).get("churn_signal")) / len(day_posts)
            advocacy_rate = sum(1 for p in day_posts if p.get("features", {}).get("advocacy_signal")) / len(day_posts)
            comp_rate   = sum(1 for p in day_posts if p.get("features", {}).get("competitor_mentioned")) / len(day_posts)

            # Engagement-weighted average score
            total_weight   = sum(weights) or 1
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

            rows.append({
                "brand":            brand,
                "date":             day,
                "weighted_score":   round(weighted_score, 4),
                "avg_intensity":    round(sum(intensities) / len(intensities), 4),
                "churn_rate":       round(churn_rate, 4),
                "advocacy_rate":    round(advocacy_rate, 4),
                "competitor_rate":  round(comp_rate, 4),
                "post_volume":      len(day_posts),
                "is_projection":    False,
            })

        if rows:
            col.insert_many(rows)
            print(f"  ✅ {brand.upper()} — {len(rows)} daily buckets saved")

    print("\n✅ Aggregation complete. Run: python ml_pipeline.py anomalies")

# ══════════════════════════════════════════════════════════
# STEP 5 — ANOMALY DETECTION
# ══════════════════════════════════════════════════════════

# Interdependency map: AI company → hardware/infra dependencies
INTERDEPENDENCIES = {
    "openai":    [("NVDA", "NVIDIA"), ("MSFT", "Microsoft")],
    "anthropic": [("NVDA", "NVIDIA"), ("AMD", "AMD"), ("AMZN", "Amazon")],
    "google":    [("NVDA", "NVIDIA"), ("AMD", "AMD"), ("AVGO", "Broadcom"), ("005930.KS", "Samsung"), ("TSM", "TSMC")],
    "xai":       [("NVDA", "NVIDIA")],
    "deepseek":  [("NVDA", "NVIDIA"), ("AMD", "AMD")],
    "microsoft": [("NVDA", "NVIDIA"), ("AMD", "AMD"), ("INTC", "Intel")],
    "alibaba":   [("NVDA", "NVIDIA"), ("TSM", "TSMC")],
}

def anomalies():
    """Z-score anomaly detection on daily sentiment with volume gating."""
    import numpy as np
    db  = get_db()
    col = db["daily_sentiment"]
    out = db["anomalies"]
    out.drop()

    WINDOW = 14  # rolling baseline window (days)
    Z_THRESH = 2.0
    VOL_MULT = 1.5

    total = 0
    for brand in AI_BRANDS:
        rows = list(col.find({"brand": brand, "is_projection": False}).sort("date", 1))
        if len(rows) < WINDOW + 1:
            print(f"  ⚠ {brand.upper()} — not enough data for anomaly detection ({len(rows)} days). Skipping.")
            continue

        scores  = np.array([r["weighted_score"] for r in rows])
        volumes = np.array([r["post_volume"] for r in rows])

        anomaly_rows = []
        for i in range(WINDOW, len(rows)):
            window_scores = scores[i - WINDOW:i]
            window_vols   = volumes[i - WINDOW:i]

            mean_s = window_scores.mean()
            std_s  = window_scores.std()
            mean_v = window_vols.mean()

            if std_s < 1e-6:
                continue  # no variance in window

            z_score = (scores[i] - mean_s) / std_s
            vol_elevated = volumes[i] > (mean_v * VOL_MULT)

            if abs(z_score) >= Z_THRESH and vol_elevated:
                direction = "bullish" if z_score > 0 else "bearish"
                deps = INTERDEPENDENCIES.get(brand, [])
                anomaly_rows.append({
                    "brand":        brand,
                    "date":         rows[i]["date"],
                    "z_score":      round(float(z_score), 3),
                    "direction":    direction,
                    "weighted_score": rows[i]["weighted_score"],
                    "post_volume":  int(volumes[i]),
                    "rolling_mean": round(float(mean_s), 4),
                    "rolling_std":  round(float(std_s), 4),
                    "dependencies": [{"ticker": t, "name": n} for t, n in deps],
                })

        if anomaly_rows:
            out.insert_many(anomaly_rows)
            total += len(anomaly_rows)
            print(f"  ✅ {brand.upper()} — {len(anomaly_rows)} anomalies detected")
        else:
            print(f"  ✅ {brand.upper()} — no anomalies")

    print(f"\n✅ Anomaly detection complete — {total} total anomalies. Run: python ml_pipeline.py train")

# ══════════════════════════════════════════════════════════
# STEP 6 — TRAIN LSTM
# ══════════════════════════════════════════════════════════

def train():
    import numpy as np
    import torch
    import torch.nn as nn
    from sklearn.preprocessing import MinMaxScaler
    import pickle

    db     = get_db()
    col    = db["daily_sentiment"]
    FEATURES = ["weighted_score", "avg_intensity", "churn_rate", "advocacy_rate",
                "competitor_rate", "post_volume"]
    SEQ_LEN  = 7   # look at 7 days to predict next day
    EPOCHS   = 100

    class LSTMModel(nn.Module):
        def __init__(self, input_size, hidden_size=64, num_layers=2):
            super().__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
            self.fc   = nn.Linear(hidden_size, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])

    all_X, all_y = [], []
    scalers      = {}

    for brand in AI_BRANDS:
        rows = list(col.find({"brand": brand, "is_projection": False}).sort("date", 1))
        if len(rows) < SEQ_LEN + 1:
            print(f"  ⚠ {brand.upper()} — not enough data ({len(rows)} days). Skipping.")
            continue

        data = np.array([[r.get(f, 0) for f in FEATURES] for r in rows], dtype=np.float32)

        scaler = MinMaxScaler()
        data   = scaler.fit_transform(data)
        scalers[brand] = scaler

        for i in range(len(data) - SEQ_LEN):
            all_X.append(data[i:i + SEQ_LEN])
            all_y.append(data[i + SEQ_LEN][0])  # predict weighted_score

    if not all_X:
        print("❌ Not enough data to train. Make sure aggregation ran successfully.")
        return

    X = torch.tensor(np.array(all_X), dtype=torch.float32)
    y = torch.tensor(np.array(all_y), dtype=torch.float32).unsqueeze(1)

    # 80/20 train/test split (chronological — no shuffle)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model     = LSTMModel(input_size=len(FEATURES))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    print(f"\n  Training LSTM on {len(X_train)} sequences (test: {len(X_test)})...")
    model.train()
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        loss = criterion(model(X_train), y_train)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1}/{EPOCHS} — Train Loss: {loss.item():.6f}")

    # Evaluate on test set
    model.eval()
    with torch.no_grad():
        test_loss = criterion(model(X_test), y_test).item()
        train_loss = criterion(model(X_train), y_train).item()
        preds = model(X_test).squeeze().numpy()
        actuals = y_test.squeeze().numpy()
        mae = float(np.mean(np.abs(preds - actuals)))

    print(f"\n  📊 Train MSE: {train_loss:.6f}")
    print(f"  📊 Test MSE:  {test_loss:.6f}")
    print(f"  📊 Test MAE:  {mae:.6f}")

    # Retrain on full data for production model
    print(f"\n  Retraining on full dataset ({len(X)} sequences) for deployment...")
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        loss = criterion(model(X), y)
        loss.backward()
        optimizer.step()

    torch.save(model.state_dict(), "pulse_lstm.pt")
    with open("pulse_scalers.pkl", "wb") as f:
        pickle.dump({
            "scalers": scalers, "features": FEATURES, "seq_len": SEQ_LEN,
            "metrics": {"train_mse": train_loss, "test_mse": test_loss, "test_mae": mae}
        }, f)

    print("\n✅ Model saved → pulse_lstm.pt")
    print("✅ Scalers saved → pulse_scalers.pkl")
    print("Run: python ml_pipeline.py predict")

# ══════════════════════════════════════════════════════════
# STEP 6 — GENERATE CSS + PROJECTIONS
# ══════════════════════════════════════════════════════════

def predict():
    import numpy as np
    import torch
    import torch.nn as nn
    from sklearn.preprocessing import MinMaxScaler
    import pickle

    class LSTMModel(nn.Module):
        def __init__(self, input_size, hidden_size=64, num_layers=2):
            super().__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
            self.fc   = nn.Linear(hidden_size, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.fc(out[:, -1, :])

    with open("pulse_scalers.pkl", "rb") as f:
        meta     = pickle.load(f)
    FEATURES = meta["features"]
    SEQ_LEN  = meta["seq_len"]
    scalers  = meta["scalers"]

    model = LSTMModel(input_size=len(FEATURES))
    model.load_state_dict(torch.load("pulse_lstm.pt"))
    model.eval()

    db      = get_db()
    col     = db["daily_sentiment"]
    out_col = db["sentiment_graph"]
    out_col.drop()

    for brand in AI_BRANDS:
        rows = list(col.find({"brand": brand, "is_projection": False}).sort("date", 1))
        if len(rows) < SEQ_LEN:
            # Use whatever data exists, even if less than SEQ_LEN
            if len(rows) < 3:
                print(f"  ⚠ {brand} — only {len(rows)} days, too little to predict. Skipping.")
                continue
            print(f"  ⚠ {brand} — only {len(rows)} days, using reduced window...")

        scaler = scalers.get(brand)
        if not scaler:
            continue

        data = np.array([[r.get(f, 0) for f in FEATURES] for r in rows], dtype=np.float32)
        data = scaler.transform(data)

        graph_rows = []

        # Historical CSS — run LSTM over each window
        for i in range(SEQ_LEN, len(data)):
            window   = torch.tensor(data[i-SEQ_LEN:i], dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                css = model(window).item()
            css = max(0, min(100, round(css * 100, 2)))  # rescale to 0-100
            graph_rows.append({
                "brand":         brand,
                "date":          rows[i]["date"],
                "css":           css,
                "post_volume":   rows[i].get("post_volume", 0),
                "is_projection": False,
            })

        # Future projection — 14 days
        future_window = data[-SEQ_LEN:].copy()
        last_date     = datetime.strptime(rows[-1]["date"], "%Y-%m-%d")

        for day in range(1, 15):
            inp = torch.tensor(future_window, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                css = model(inp).item()
            css = max(0, min(100, round(css * 100, 2)))  # rescale to 0-100

            future_date = (last_date + timedelta(days=day)).strftime("%Y-%m-%d")
            graph_rows.append({
                "brand":         brand,
                "date":          future_date,
                "css":           css,
                "post_volume":   0,
                "is_projection": True,
            })

            # Roll window forward
            new_row         = future_window[-1].copy()
            new_row[0]      = css / 100  # convert back to 0-1 scale for scaler
            future_window   = np.vstack([future_window[1:], new_row])

        out_col.insert_many(graph_rows)
        hist  = sum(1 for r in graph_rows if not r["is_projection"])
        proj  = sum(1 for r in graph_rows if r["is_projection"])
        print(f"  ✅ {brand.upper()} — {hist} historical points + {proj} projections saved")

    print("\n✅ sentiment_graph collection ready!")
    print("Run: python ml_pipeline.py correlate")

# ══════════════════════════════════════════════════════════
# STEP 8 — STOCK CORRELATION
# ══════════════════════════════════════════════════════════

def correlate():
    """Compute Pearson correlation between AI sentiment deltas and hardware stock deltas at multiple lags."""
    import numpy as np
    import pandas as pd
    db = get_db()

    # Map AI brand → list of (ticker, stock_collection_name)
    STOCK_MAP = {
        "openai":    ["nvidia", "microsoft"],
        "anthropic": ["nvidia", "amd", "amazon"],
        "google":    ["nvidia", "amd", "broadcom", "samsung", "tsmc"],
        "xai":       ["nvidia"],
        "deepseek":  ["nvidia", "amd"],
        "microsoft": ["nvidia", "amd", "intel"],
        "alibaba":   ["nvidia", "tsmc"],
    }
    LAGS = [1, 2, 3, 5, 7]  # days

    out_col = db["correlations"]
    out_col.drop()
    results = []

    for brand in AI_BRANDS:
        # Get daily sentiment
        sent_rows = list(db["daily_sentiment"].find({"brand": brand, "is_projection": False}).sort("date", 1))
        if len(sent_rows) < 10:
            print(f"  ⚠ {brand.upper()} — too few days for correlation. Skipping.")
            continue

        sent_df = pd.DataFrame(sent_rows)[["date", "weighted_score"]]
        sent_df["date"] = pd.to_datetime(sent_df["date"])
        sent_df = sent_df.sort_values("date").set_index("date")
        sent_df["sent_delta"] = sent_df["weighted_score"].diff()

        stock_names = STOCK_MAP.get(brand, [])
        for stock_name in stock_names:
            stock_col_name = f"{stock_name}_stock"
            stock_rows = list(db[stock_col_name].find())
            if not stock_rows:
                continue

            stock_df = pd.DataFrame(stock_rows)
            # Stock data has date in "Price" column (CSV artifact)
            date_col = "Date" if "Date" in stock_df.columns else "Price"
            if date_col not in stock_df.columns or "Close" not in stock_df.columns:
                continue
            # Filter out header artifact rows
            stock_df = stock_df[stock_df[date_col].str.match(r"^\d{4}-", na=False)].copy()
            stock_df["date"] = pd.to_datetime(stock_df[date_col])
            stock_df["Close"] = pd.to_numeric(stock_df["Close"], errors="coerce")
            stock_df = stock_df.dropna(subset=["date", "Close"])
            stock_df = stock_df.sort_values("date").set_index("date")
            stock_df["price_delta"] = stock_df["Close"].pct_change()

            # Merge on date
            merged = sent_df[["sent_delta"]].join(stock_df[["price_delta"]], how="inner").dropna()
            if len(merged) < 5:
                continue

            for lag in LAGS:
                lagged = sent_df[["sent_delta"]].copy()
                lagged.index = lagged.index + pd.Timedelta(days=lag)
                lag_merged = lagged.join(stock_df[["price_delta"]], how="inner").dropna()
                if len(lag_merged) < 5:
                    continue

                corr = float(lag_merged["sent_delta"].corr(lag_merged["price_delta"]))
                if np.isnan(corr):
                    continue

                results.append({
                    "brand":       brand,
                    "stock":       stock_name,
                    "lag_days":    lag,
                    "correlation": round(corr, 4),
                    "n_samples":   len(lag_merged),
                })

        print(f"  ✅ {brand.upper()} — correlation computed for {len(stock_names)} stocks")

    if results:
        out_col.insert_many(results)
    print(f"\n✅ Stock correlation complete — {len(results)} entries. Run: python ml_pipeline.py sms")

# ══════════════════════════════════════════════════════════
# STEP 9 — SENTIMENT MOMENTUM SCORE (SMS) + DECISION RULE
# ══════════════════════════════════════════════════════════

def sms():
    """Compute SMS per brand per day and fire alerts based on decision rules."""
    import numpy as np
    db = get_db()

    sent_col = db["daily_sentiment"]
    graph_col = db["sentiment_graph"]
    alert_col = db["alerts"]
    sms_col   = db["sms_scores"]
    alert_col.drop()
    sms_col.drop()

    all_sms = []
    all_alerts = []

    for brand in AI_BRANDS:
        rows = list(sent_col.find({"brand": brand, "is_projection": False}).sort("date", 1))
        if len(rows) < 4:
            print(f"  ⚠ {brand.upper()} — not enough data for SMS. Skipping.")
            continue

        # Get LSTM predictions for direction
        predictions = {r["date"]: r["css"] for r in graph_col.find({"brand": brand})}

        scores = np.array([r["weighted_score"] for r in rows])
        volumes = np.array([r["post_volume"] for r in rows])

        for i in range(3, len(rows)):
            current = scores[i]
            # Sentiment velocity: rate of change over last 3 windows
            velocity = (scores[i] - scores[i - 3]) / 3

            # Volume anomaly factor: current vs rolling average
            rolling_vol = volumes[max(0, i - 7):i].mean() if i >= 1 else volumes[i]
            vol_factor = (volumes[i] / rolling_vol - 1) if rolling_vol > 0 else 0
            vol_factor = max(-1, min(1, vol_factor))  # clamp

            # LSTM predicted direction (from CSS: >50 = positive, <50 = negative)
            css_val = predictions.get(rows[i]["date"], 50)
            lstm_direction = (css_val - 50) / 50  # normalize to [-1, +1]

            # SMS formula (0-100 scale): base at 50
            raw_sms = (0.4 * current) + (0.3 * velocity) + (0.2 * vol_factor) + (0.1 * lstm_direction)
            sms_score = max(0, min(100, round((raw_sms + 1) * 50, 2)))

            sms_entry = {
                "brand":     brand,
                "date":      rows[i]["date"],
                "sms":       sms_score,
                "current_sentiment": round(float(current), 4),
                "velocity":  round(float(velocity), 4),
                "vol_factor": round(float(vol_factor), 4),
                "lstm_dir":  round(float(lstm_direction), 4),
            }
            all_sms.append(sms_entry)

            # Decision rules
            deps = INTERDEPENDENCIES.get(brand, [])
            if sms_score < 35 and deps:
                for ticker, name in deps:
                    all_alerts.append({
                        "brand":     brand,
                        "date":      rows[i]["date"],
                        "type":      "negative_impact",
                        "sms":       sms_score,
                        "message":   f"Potential negative stock impact on {name} ({ticker})",
                        "ticker":    ticker,
                        "stock_name": name,
                    })

            # Sustained positive momentum: SMS > 75 for 2+ consecutive windows
            if sms_score > 75 and i >= 4:
                prev_sms_raw = (0.4 * scores[i-1]) + (0.3 * (scores[i-1] - scores[i-4]) / 3) + (0.2 * 0) + (0.1 * 0)
                prev_sms = (prev_sms_raw + 1) * 50
                if prev_sms > 75 and deps:
                    for ticker, name in deps:
                        all_alerts.append({
                            "brand":     brand,
                            "date":      rows[i]["date"],
                            "type":      "positive_momentum",
                            "sms":       sms_score,
                            "message":   f"Sustained positive momentum — check {name} ({ticker}) position",
                            "ticker":    ticker,
                            "stock_name": name,
                        })

        print(f"  ✅ {brand.upper()} — {len([s for s in all_sms if s['brand'] == brand])} SMS scores")

    if all_sms:
        sms_col.insert_many(all_sms)
    if all_alerts:
        alert_col.insert_many(all_alerts)

    print(f"\n✅ SMS complete — {len(all_sms)} scores, {len(all_alerts)} alerts fired.")

# ══════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════

COMMANDS = {
    "install":    install,
    "score":      score,
    "features":   features,
    "aggregate":  aggregate,
    "anomalies":  anomalies,
    "train":      train,
    "predict":    predict,
    "correlate":  correlate,
    "sms":        sms,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python ml_pipeline.py [install|score|features|aggregate|anomalies|train|predict|correlate|sms]")
        print("\nRun in order:")
        for i, cmd in enumerate(COMMANDS, 1):
            print(f"  {i}. python ml_pipeline.py {cmd}")
    else:
        COMMANDS[sys.argv[1]]()