import { useState } from "react";

const BRAND_NAMES = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  xai: "xAI",
  deepseek: "DeepSeek",
  microsoft: "Microsoft",
  alibaba: "Alibaba",
};

function timeAgo(utc) {
  const now = Date.now();
  const then = typeof utc === "number" ? utc * 1000 : new Date(utc).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs === 1 ? "" : "s"} ago`;
  const days = Math.floor(hrs / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function buildHashtags(post) {
  const tags = [];
  if (post.subreddit) tags.push(`#${post.subreddit.toUpperCase()}`);
  if (post.features) {
    if (post.features.churn_signal) tags.push("#CHURN");
    if (post.features.advocacy_signal) tags.push("#ADVOCACY");
    if (post.features.trust_loss_signal) tags.push("#TRUSTLOSS");
    if (post.features.competitor_mentioned) tags.push("#COMPETITOR");
  }
  return tags.slice(0, 2);
}

function SentimentCard({ post }) {
  const score = post.finbert_score ?? post.raw_score ?? 0;
  const isBullish = score > 0.1;

  return (
    <div className="flex-none w-[280px] md:w-[300px] p-4 rounded-xl bg-[#101f22] border border-primary/5 hover:border-primary/20 transition-all group">
      {/* Badge + Timestamp */}
      <div className="flex items-center justify-between mb-3">
        {isBullish ? (
          <span className="px-2.5 py-0.5 rounded text-[10px] font-bold tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
            BULLISH
          </span>
        ) : (
          <span className="px-2.5 py-0.5 rounded text-[10px] font-bold tracking-wider bg-red-500/15 text-red-400 border border-red-500/20">
            BEARISH
          </span>
        )}
        <span className="text-[10px] text-slate-500">{timeAgo(post.created_utc)}</span>
      </div>

      {/* Title */}
      <p className="text-sm text-slate-200 leading-snug line-clamp-2 mb-3 min-h-[2.5rem]">
        {post.title}
      </p>

      {/* Hashtags */}
      <div className="flex gap-2 flex-wrap">
        {buildHashtags(post).map((tag) => (
          <span key={tag} className="text-[10px] text-slate-500 font-medium">
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function PostsFeed({ posts, loading }) {
  const [filter, setFilter] = useState("all"); // "all" or "high"

  if (loading) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6">
        <h2 className="text-lg font-bold mb-4">Real-time Sentiment Drivers</h2>
        <div className="flex gap-4 overflow-hidden">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex-none w-[280px] h-28 rounded-xl bg-primary/5 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  // Filter for only bullish (> 0.1) and bearish (< -0.1)
  const scored = posts.filter((p) => {
    const s = p.finbert_score ?? p.raw_score;
    return s !== undefined && s !== null && (s > 0.1 || s < -0.1);
  });

  // For "High Impact" filter, use stronger thresholds
  const filtered = filter === "high"
    ? scored.filter((p) => {
        const s = p.finbert_score ?? p.raw_score ?? 0;
        return s > 0.4 || s < -0.4;
      })
    : scored;

  // Sort newest first
  const sorted = [...filtered]
    .sort((a, b) => {
      const tA = typeof a.created_utc === "number" ? a.created_utc : new Date(a.created_utc).getTime() / 1000;
      const tB = typeof b.created_utc === "number" ? b.created_utc : new Date(b.created_utc).getTime() / 1000;
      return tB - tA;
    })
    .slice(0, 20);

  return (
    <div className="bg-panel border border-border rounded-2xl p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold">Real-time Sentiment Drivers</h2>
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] font-bold text-red-400 tracking-wider">LIVE FEED</span>
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-slate-500">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1 rounded-md transition-colors ${
              filter === "all"
                ? "text-slate-200 bg-primary/10"
                : "hover:text-slate-300"
            }`}
          >
            All News
          </button>
          <button
            onClick={() => setFilter("high")}
            className={`px-3 py-1 rounded-md transition-colors ${
              filter === "high"
                ? "text-primary bg-primary/10"
                : "hover:text-slate-300"
            }`}
          >
            High Impact
          </button>
        </div>
      </div>

      {/* Scrollable news feed */}
      {sorted.length === 0 ? (
        <div className="text-center py-8">
          <span className="material-symbols-outlined text-3xl text-slate-600 mb-2 block">newspaper</span>
          <p className="text-sm text-slate-500">No sentiment drivers to show</p>
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
          {sorted.map((post) => (
            <SentimentCard key={post.id || post._id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
