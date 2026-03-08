function SentimentBadge({ score }) {
  if (score === undefined || score === null) {
    return <span className="px-2 py-0.5 rounded-full text-xs bg-slate-800 text-slate-500">Unscored</span>;
  }
  if (score > 0.1) {
    return <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 font-medium">+{score.toFixed(2)}</span>;
  }
  if (score < -0.1) {
    return <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-400 font-medium">{score.toFixed(2)}</span>;
  }
  return <span className="px-2 py-0.5 rounded-full text-xs bg-slate-700/50 text-slate-400 font-medium">{score.toFixed(2)}</span>;
}

function FeaturePill({ label }) {
  return <span className="px-2 py-0.5 rounded-full text-[10px] bg-primary/10 text-primary/80">{label}</span>;
}

function formatDate(utc) {
  const d = new Date(utc);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function PostsFeed({ posts, loading }) {
  if (loading) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6">
        <h2 className="text-lg font-bold mb-4">Sentiment Drivers</h2>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-primary/5 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  // Sort by date descending, take top 50
  const sorted = [...posts]
    .sort((a, b) => new Date(b.created_utc) - new Date(a.created_utc))
    .slice(0, 50);

  return (
    <div className="bg-panel border border-border rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold">Sentiment Drivers</h2>
        <span className="text-xs text-slate-500">{posts.length} posts</span>
      </div>
      <div className="max-h-[500px] overflow-y-auto space-y-2 pr-2">
        {sorted.map((post) => (
          <div
            key={post.id || post._id}
            className="p-4 rounded-xl bg-[#101f22] border border-primary/5 hover:border-primary/20 transition-colors"
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <h3 className="text-sm font-medium leading-snug line-clamp-2 flex-1">
                {post.title}
              </h3>
              <SentimentBadge score={post.finbert_score ?? post.raw_score} />
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">arrow_upward</span>
                {post.score}
              </span>
              <span className="flex items-center gap-1">
                <span className="material-symbols-outlined text-xs">chat_bubble</span>
                {post.num_comments}
              </span>
              <span>r/{post.subreddit}</span>
              <span>{formatDate(post.created_utc)}</span>
            </div>
            {post.features && (
              <div className="flex gap-1.5 mt-2">
                {post.features.churn_signal && <FeaturePill label="Churn" />}
                {post.features.advocacy_signal && <FeaturePill label="Advocacy" />}
                {post.features.trust_loss_signal && <FeaturePill label="Trust Loss" />}
                {post.features.competitor_mentioned && <FeaturePill label="Competitor" />}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
