"""
Pulse ML Pipeline
Run in order:
  1. python ml_pipeline.py install     → installs all libraries
  2. python ml_pipeline.py score       → FinBERT scores every post
  3. python ml_pipeline.py features    → extracts all parameters
  4. python ml_pipeline.py aggregate   → builds daily buckets
  5. python ml_pipeline.py train       → trains LSTM
  6. python ml_pipeline.py predict     → generates CSS + 14-day projection
"""

import sys
import os
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "pulse"
AI_BRANDS = ["openai", "anthropic", "google", "xai", "deepseek", "microsoft", "alibaba"]

def get_db():
    return MongoClient(MONGO_URI)[DB_NAME]

# ══════════════════════════════════════════════════════════
# STEP 1 — INSTALL
# ══════════════════════════════════════════════════════════

def install():
    print("Installing ML libraries...")
    os.system("pip install transformers torch vaderSentiment scikit-learn pandas numpy pymongo")
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
            except:
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

    def comment_alignment(post, raw_score):
        comments = post.get("comments", [])
        if not comments:
            return "unknown"
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        vader    = SentimentIntensityAnalyzer()
        scores   = [vader.polarity_scores(c.get("body",""))["compound"] for c in comments if c.get("body")]
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
            except:
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

    print("\n✅ Aggregation complete. Run: python ml_pipeline.py train")

# ══════════════════════════════════════════════════════════
# STEP 5 — TRAIN LSTM
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

    model     = LSTMModel(input_size=len(FEATURES))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    print(f"\n  Training LSTM on {len(X)} sequences across {len(AI_BRANDS)} brands...")
    model.train()
    for epoch in range(EPOCHS):
        optimizer.zero_grad()
        loss = criterion(model(X), y)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1}/{EPOCHS} — Loss: {loss.item():.6f}")

    torch.save(model.state_dict(), "pulse_lstm.pt")
    with open("pulse_scalers.pkl", "wb") as f:
        pickle.dump({"scalers": scalers, "features": FEATURES, "seq_len": SEQ_LEN}, f)

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
            css = max(-1.0, min(1.0, css * 2 - 1))  # rescale to -1 to +1
            graph_rows.append({
                "brand":         brand,
                "date":          rows[i]["date"],
                "css":           round(css, 4),
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
            css = max(-1.0, min(1.0, css * 2 - 1))

            future_date = (last_date + timedelta(days=day)).strftime("%Y-%m-%d")
            graph_rows.append({
                "brand":         brand,
                "date":          future_date,
                "css":           round(css, 4),
                "post_volume":   0,
                "is_projection": True,
            })

            # Roll window forward
            new_row         = future_window[-1].copy()
            new_row[0]      = (css + 1) / 2  # convert back to 0-1 scale
            future_window   = np.vstack([future_window[1:], new_row])

        out_col.insert_many(graph_rows)
        hist  = sum(1 for r in graph_rows if not r["is_projection"])
        proj  = sum(1 for r in graph_rows if r["is_projection"])
        print(f"  ✅ {brand.upper()} — {hist} historical points + {proj} projections saved")

    print("\n✅ sentiment_graph collection ready!")
    print("Run: python ml_pipeline.py predict  ← re-run anytime after retraining")

# ══════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════

COMMANDS = {
    "install":   install,
    "score":     score,
    "features":  features,
    "aggregate": aggregate,
    "train":     train,
    "predict":   predict,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python ml_pipeline.py [install|score|features|aggregate|train|predict]")
        print("\nRun in order:")
        for i, cmd in enumerate(COMMANDS, 1):
            print(f"  {i}. python ml_pipeline.py {cmd}")
    else:
        COMMANDS[sys.argv[1]]()