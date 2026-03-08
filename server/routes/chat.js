const { getDb } = require("../DB/mongo");
const router = require("express").Router();

const BRANDS = ["openai", "anthropic", "google", "xai", "deepseek", "microsoft", "alibaba"];

const API_URL = "https://api.featherless.ai/v1/chat/completions";
const DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct";

async function gatherContext(db, brand, message) {
  const ctx = {};
  const msgLower = message.toLowerCase();

  // Always fetch core metrics
  const [sentiment, daily, sms] = await Promise.all([
    db.collection("sentiment_graph")
      .find({ brand })
      .sort({ date: -1 })
      .limit(14)
      .toArray(),
    db.collection("daily_sentiment")
      .find({ brand })
      .sort({ date: -1 })
      .limit(7)
      .toArray(),
    db.collection("sms_scores")
      .find({ brand })
      .sort({ date: -1 })
      .limit(1)
      .toArray(),
  ]);

  ctx.sentimentGraph = sentiment.reverse();
  ctx.dailySentiment = daily.reverse();
  ctx.sms = sms[0] || null;

  // Fetch anomalies and alerts (useful for most queries)
  const [anomalies, alerts] = await Promise.all([
    db.collection("anomalies")
      .find({ brand })
      .sort({ date: -1 })
      .limit(5)
      .toArray(),
    db.collection("alerts")
      .find({ brand })
      .sort({ date: -1 })
      .limit(5)
      .toArray(),
  ]);

  ctx.anomalies = anomalies;
  ctx.alerts = alerts;

  // Fetch correlations if stock-related
  if (msgLower.match(/stock|correlat|price|ticker|market|nvidia|amd|invest/)) {
    ctx.correlations = await db.collection("correlations")
      .find({ brand })
      .toArray();
  }

  // Fetch comparison brand data if another brand is mentioned
  const otherBrand = BRANDS.find(b => b !== brand && msgLower.includes(b));
  if (otherBrand) {
    const [compSentiment, compDaily, compSms] = await Promise.all([
      db.collection("sentiment_graph")
        .find({ brand: otherBrand })
        .sort({ date: -1 })
        .limit(7)
        .toArray(),
      db.collection("daily_sentiment")
        .find({ brand: otherBrand })
        .sort({ date: -1 })
        .limit(7)
        .toArray(),
      db.collection("sms_scores")
        .find({ brand: otherBrand })
        .sort({ date: -1 })
        .limit(1)
        .toArray(),
    ]);
    ctx.comparison = {
      brand: otherBrand,
      sentimentGraph: compSentiment.reverse(),
      dailySentiment: compDaily.reverse(),
      sms: compSms[0] || null,
    };
  }

  return ctx;
}

function buildSystemPrompt(brand, ctx) {
  let prompt = `You are the Sentience AI Analyst, an expert on AI company public sentiment and market impact.
You are currently analyzing: ${brand}.

## Metric Definitions
- **CSS (Composite Sentiment Score)**: 0-100 scale derived from LSTM model. >50 = positive, <50 = negative.
- **weighted_score**: Engagement-weighted daily sentiment from -1 (very negative) to +1 (very positive).
- **SMS (Sentiment Momentum Score)**: 0-100 momentum indicator combining current sentiment, velocity, volume, and LSTM direction.
- **churn_rate**: Fraction of posts signaling users switching away (0-1).
- **advocacy_rate**: Fraction of posts recommending the brand (0-1).
- **competitor_rate**: Fraction of posts mentioning competitors (0-1).
- **Anomalies**: Days where sentiment deviated >2 standard deviations from the 14-day rolling mean.
- **Alerts**: Trading signals — "negative_impact" (SMS<35) or "positive_momentum" (SMS>75 for 2+ days).
- **Correlations**: Pearson correlation between sentiment changes and stock price changes at various lag days.

## Current Data for ${brand}

### CSS Scores (last 14 entries, newest last)
${JSON.stringify(ctx.sentimentGraph.map(d => ({ date: d.date, css: d.css, volume: d.post_volume, projected: d.is_projection })), null, 1)}

### Daily Metrics (last 7 days)
${JSON.stringify(ctx.dailySentiment.map(d => ({ date: d.date, score: d.weighted_score, intensity: d.avg_intensity, churn: d.churn_rate, advocacy: d.advocacy_rate, competitors: d.competitor_rate, volume: d.post_volume })), null, 1)}

### Sentiment Momentum
${ctx.sms ? JSON.stringify({ sms: ctx.sms.sms, velocity: ctx.sms.velocity, vol_factor: ctx.sms.vol_factor, lstm_dir: ctx.sms.lstm_dir }) : "No SMS data available."}

### Recent Anomalies
${ctx.anomalies.length ? JSON.stringify(ctx.anomalies.map(a => ({ date: a.date, z_score: a.z_score, direction: a.direction, score: a.weighted_score })), null, 1) : "No recent anomalies."}

### Active Alerts
${ctx.alerts.length ? JSON.stringify(ctx.alerts.map(a => ({ date: a.date, type: a.type, sms: a.sms, message: a.message })), null, 1) : "No active alerts."}`;

  if (ctx.correlations) {
    prompt += `\n\n### Stock Correlations\n${JSON.stringify(ctx.correlations.map(c => ({ stock: c.stock, lag: c.lag_days, correlation: c.correlation, samples: c.n_samples })), null, 1)}`;
  }

  if (ctx.comparison) {
    const c = ctx.comparison;
    prompt += `\n\n## Comparison Data for ${c.brand}
### CSS Scores
${JSON.stringify(c.sentimentGraph.map(d => ({ date: d.date, css: d.css })), null, 1)}
### Daily Metrics
${JSON.stringify(c.dailySentiment.map(d => ({ date: d.date, score: d.weighted_score, churn: d.churn_rate, advocacy: d.advocacy_rate })), null, 1)}
### SMS
${c.sms ? JSON.stringify({ sms: c.sms.sms, velocity: c.sms.velocity }) : "No SMS data."}`;
  }

  prompt += `\n\n## Instructions
- Reference specific numbers and dates from the data above.
- Be concise: 2-4 paragraphs unless the user asks for detail.
- Use markdown formatting (bold key numbers, bullet points for lists).
- Provide actionable insights — what the data suggests, not just what it shows.
- Explain metrics in plain language when first mentioning them.`;

  return prompt;
}

router.post("/", async (req, res) => {
  const apiKey = process.env.FEATHERLESS_API_KEY;
  if (!apiKey) {
    return res.status(503).json({ error: "Chat unavailable — FEATHERLESS_API_KEY not configured." });
  }

  const { message, brand, history } = req.body;
  if (!message || !brand) {
    return res.status(400).json({ error: "message and brand are required." });
  }

  try {
    const db = getDb();
    const ctx = await gatherContext(db, brand, message);
    const systemPrompt = buildSystemPrompt(brand, ctx);

    const trimmedHistory = (history || []).slice(-10).map(m => ({
      role: m.role,
      content: m.content,
    }));

    const messages = [
      { role: "system", content: systemPrompt },
      ...trimmedHistory,
      { role: "user", content: message },
    ];

    const model = process.env.FEATHERLESS_MODEL || DEFAULT_MODEL;

    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({ model, messages, max_tokens: 1024 }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error("[chat] Featherless API error:", response.status, errText);
      return res.status(502).json({ error: "Failed to get response from AI." });
    }

    const data = await response.json();
    const reply = data.choices?.[0]?.message?.content || "No response generated.";
    res.json({ reply });
  } catch (err) {
    console.error("[chat] Error:", err);
    res.status(500).json({ error: "Internal server error." });
  }
});

module.exports = router;
