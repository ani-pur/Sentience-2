# Sentience

**Mapping the AI ecosystem's sentiment landscape — tracking how public perception of AI companies ripples through their hardware supply chain and predicting where sentiment is heading next.**

---

## The Problem

AI companies don't exist in a vacuum. When public sentiment shifts for OpenAI, Anthropic, or DeepSeek, the ripple effects reach their hardware suppliers — NVIDIA, AMD, TSMC, and beyond. Traditional sentiment tools analyze companies in isolation. Nobody is modeling the *relationships* between them.

## What Sentience Does

Sentience ingests thousands of Reddit posts across AI communities, scores them with **FinBERT** (a finance-domain transformer), extracts behavioral signals like user churn, brand advocacy, and trust erosion, then feeds everything into an **LSTM neural network** that forecasts sentiment 14 days into the future.

The key insight: we map an **interdependency network** between AI companies and their hardware suppliers, so when sentiment shifts for one company, Sentience traces the impact downstream and flags potential market movement before it happens.

**Demo story:** *DeepSeek drops a new open-source model. Reddit explodes. Sentience catches the sentiment spike in real time, traces the dependency to NVIDIA (their GPU supplier), and our LSTM predicts elevated positive sentiment will hold for 48 hours. Meanwhile, NVIDIA's stock ticks up 3%. Sentience saw it coming.*

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    REACT FRONTEND                        │
│   Sentiment Trajectory · Drivers Feed · Network Graph    │
│   Stock Overlay · Forecast View                          │
├─────────────────────────────────────────────────────────┤
│               EXPRESS / NODE BACKEND                     │
│   /api/sentiment    — scores by entity + time range      │
│   /api/brands       — list tracked entities              │
│   /api/posts        — raw posts by brand                 │
│   /api/daily        — daily aggregated sentiment         │
├─────────────────────────────────────────────────────────┤
│               PYTHON ML PIPELINE                         │
│                                                          │
│   1. FinBERT    — domain-specific sentiment scoring      │
│   2. Features   — churn, advocacy, trust, intensity      │
│   3. Aggregate  — daily bucketing + weighted scores      │
│   4. LSTM       — 14-day sentiment trajectory forecast   │
│   5. Predict    — composite sentiment score (CSS)        │
├─────────────────────────────────────────────────────────┤
│                    MONGODB                                │
│   Raw posts · Daily sentiment · Sentiment graph          │
│   Stock data · Interdependency mappings                  │
└─────────────────────────────────────────────────────────┘
```

### ML Pipeline Deep Dive

| Stage | What It Does | Key Detail |
|-------|-------------|------------|
| **FinBERT Scoring** | Sentiment-analyzes every Reddit post | 70% post score + 30% VADER comment score for hybrid accuracy |
| **Feature Extraction** | Extracts 7 behavioral signals per post | Churn signal, advocacy signal, trust loss, competitor mentions, emotion intensity, engagement weight, comment alignment |
| **Daily Aggregation** | Buckets posts into daily windows | Volume-weighted sentiment, churn/advocacy/competitor rates |
| **LSTM Training** | 2-layer LSTM (64 hidden units) | 7-day sliding windows → predict next day's weighted sentiment |
| **Prediction** | Generates Composite Sentiment Score | Projects 14 days into the future per brand |

### Signal: Sentiment Momentum Score (SMS)

```
SMS = 0.4 × current_sentiment
    + 0.3 × sentiment_velocity
    + 0.2 × volume_anomaly_factor
    + 0.1 × lstm_direction
```

**Decision rule:** If SMS drops below **-0.3** for an AI company with a hardware dependency → flag potential stock impact alert. If SMS sustains above **+0.5** for 2+ windows → signal positive momentum.

---

## Interdependency Network

This is the differentiator. We model the supply chain relationships between AI companies and their hardware infrastructure:

```
OpenAI ──────→ NVIDIA (H100/B200)  ·  Microsoft/Azure
Anthropic ───→ NVIDIA + AMD  ·  AWS  ·  Google Cloud
Google ──────→ NVIDIA + AMD  ·  Broadcom (TPU)  ·  Samsung + TSMC
xAI ─────────→ NVIDIA (Memphis supercluster)
DeepSeek ────→ NVIDIA + AMD

Cross-cutting:
NVIDIA ──────→ TSMC (fab)  ·  Micron (HBM)  ·  Broadcom (networking)
AMD ─────────→ TSMC + Samsung (fab)
```

When sentiment shifts for an AI company, Sentience traces edges to dependent hardware companies and checks for correlated stock movement.

---

## Tracked Entities

**AI Companies** (Reddit sentiment): OpenAI, Anthropic, Google, xAI, DeepSeek, Microsoft, Alibaba

**Hardware/Infra** (stock correlation): NVIDIA, AMD, Amazon, Broadcom, Intel, Meta, Micron, Qualcomm, Samsung, TSMC

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 7 |
| Backend | Express 5, Mongoose 9 |
| ML/NLP | PyTorch (LSTM), FinBERT (transformers), VADER |
| Data | MongoDB, pandas, scikit-learn |
| Scraping | Custom Reddit scraper (parallel, multiprocessing) |

---

## Quickstart

```bash
# Frontend
cd client && npm install && npm run dev

# Backend
cd server && npm install && node index.js

# ML Pipeline (run stages in order)
cd scraper
python ml_pipeline.py install
python load_mongo.py
python ml_pipeline.py score
python ml_pipeline.py features
python ml_pipeline.py aggregate
python ml_pipeline.py train
python ml_pipeline.py predict
```

**Requires:** Node.js, Python 3.8+, MongoDB on localhost:27017

---

## Validation

- **Backtest** against historical stock data — sentiment shifts that preceded price movement
- **Baseline comparison** — FinBERT + LSTM vs. plain VADER (precision/recall improvement)
- **Signal decay analysis** — correlation strength at 6h, 12h, 24h, 48h, 72h lags

---

*Built at HackAI 2026*
