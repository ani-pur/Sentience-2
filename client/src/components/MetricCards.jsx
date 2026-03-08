function MetricCard({ icon, label, value, color }) {
  return (
    <div className="p-5 rounded-2xl bg-panel border border-border">
      <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-3">
        <span className="material-symbols-outlined text-xl">{icon}</span>
      </div>
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color || "text-slate-100"}`}>{value}</p>
    </div>
  );
}

export default function MetricCards({ data, loading }) {
  if (loading || !data.length) {
    const placeholders = ["Post Volume", "Avg Sentiment", "Churn Rate", "Advocacy Rate"];
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {placeholders.map((label) => (
          <div key={label} className="p-5 rounded-2xl bg-panel border border-border">
            <div className="size-10 rounded-xl bg-primary/10 mb-3 animate-pulse" />
            <p className="text-xs text-slate-500 mb-1">{label}</p>
            <p className="text-2xl font-bold text-slate-700">—</p>
          </div>
        ))}
      </div>
    );
  }

  // Use the last 7 entries for volume sum, latest entry for other metrics
  const recent = data.slice(-7);
  const latest = data[data.length - 1];
  const totalVolume = recent.reduce((sum, d) => sum + (d.post_volume || 0), 0);
  const rawSentiment = latest.weighted_score || 0;
  const sentiment = Math.round((rawSentiment + 1) * 50); // convert [-1,+1] to [0,100]
  const sentimentColor = sentiment > 55 ? "text-emerald-400" : sentiment < 45 ? "text-red-400" : "text-slate-300";

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <MetricCard icon="forum" label="Post Volume (7d)" value={totalVolume.toLocaleString()} />
      <MetricCard icon="sentiment_satisfied" label="Avg Sentiment" value={`${sentiment}/100`} color={sentimentColor} />
      <MetricCard icon="trending_down" label="Churn Rate" value={`${((latest.churn_rate || 0) * 100).toFixed(1)}%`} />
      <MetricCard icon="volunteer_activism" label="Advocacy Rate" value={`${((latest.advocacy_rate || 0) * 100).toFixed(1)}%`} />
    </div>
  );
}
