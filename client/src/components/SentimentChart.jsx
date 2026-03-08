import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

const BRAND_NAMES = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  xai: "xAI",
  deepseek: "DeepSeek",
  microsoft: "Microsoft",
  alibaba: "Alibaba",
};

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#101f22] border border-primary/20 rounded-lg px-4 py-3 shadow-xl">
      <p className="text-xs text-slate-400 mb-1">{formatDate(label)}</p>
      <p className="text-sm font-bold text-primary">
        CSS: {d.css?.toFixed(1)}
      </p>
      <p className="text-xs text-slate-400">
        Volume: {d.post_volume} posts
      </p>
      {d.is_projection && (
        <p className="text-xs text-yellow-400 mt-1">Projected</p>
      )}
    </div>
  );
}

const TIME_RANGES = [
  { label: "1W", days: 7 },
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "All", days: null },
];

function filterByRange(data, days) {
  if (!days) return data;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().split("T")[0];
  return data.filter((d) => d.date >= cutoffStr);
}

export default function SentimentChart({ data, brand, loading }) {
  const [range, setRange] = useState("All");

  if (loading) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6 h-[400px] flex items-center justify-center">
        <p className="text-slate-500 animate-pulse">Loading chart...</p>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6 h-[400px] flex items-center justify-center">
        <div className="text-center">
          <span className="material-symbols-outlined text-4xl text-slate-600 mb-2 block">analytics</span>
          <p className="text-slate-500">No sentiment data yet</p>
          <p className="text-xs text-slate-600 mt-1">Run the ML pipeline to generate scores</p>
        </div>
      </div>
    );
  }

  const selectedRange = TIME_RANGES.find((r) => r.label === range);
  const filtered = filterByRange(data, selectedRange?.days);

  // Prepare data: historical vs projected
  const chartData = filtered.map((d) => ({
    date: d.date,
    css: d.css,
    post_volume: d.post_volume,
    is_projection: d.is_projection,
    historical: d.is_projection ? null : d.css,
    projected: d.is_projection ? d.css : null,
  }));

  // Bridge: set the last historical point as first projected point
  for (let i = 0; i < chartData.length; i++) {
    if (chartData[i].is_projection && i > 0 && !chartData[i - 1].is_projection) {
      chartData[i - 1].projected = chartData[i - 1].css;
    }
  }

  return (
    <div className="bg-panel border border-border rounded-2xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">Composite Sentiment Score</h2>
          <p className="text-sm text-slate-500">{BRAND_NAMES[brand] || brand}</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center bg-[#0a1a1d] rounded-lg p-0.5 gap-0.5">
            {TIME_RANGES.map((r) => (
              <button
                key={r.label}
                onClick={() => setRange(r.label)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                  range === r.label
                    ? "bg-primary/20 text-primary"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 rounded" style={{ background: "#25d1f4" }} /> Historical
            </span>
            <span className="flex items-center gap-2">
              <span className="flex items-center gap-[3px]">
                <span className="w-1.5 h-0.5 rounded-full" style={{ background: "#25d2f48d" }} />
                <span className="w-1.5 h-0.5 rounded-full" style={{ background: "#25d2f48d" }} />
              </span>
              Projected
            </span>
          </div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <defs>
            <linearGradient id="cssGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#25d1f4" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#25d1f4" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(37, 209, 244, 0.06)" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#475569"
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={{ stroke: "rgba(37, 209, 244, 0.1)" }}
          />
          <YAxis
            domain={[0, 100]}
            stroke="#475569"
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={{ stroke: "rgba(37, 209, 244, 0.1)" }}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={50} stroke="rgba(37, 209, 244, 0.2)" strokeDasharray="6 3" />
          <Area
            type="monotone"
            dataKey="historical"
            stroke="#25d1f4"
            strokeWidth={2}
            fill="url(#cssGradient)"
            connectNulls={false}
            dot={false}
            isAnimationActive={true}
            animationDuration={800}
          />
          <Area
            type="monotone"
            dataKey="projected"
            stroke="#25d2f48d"
            strokeWidth={2}
            strokeDasharray="6 4"
            fill="none"
            connectNulls={false}
            dot={false}
            isAnimationActive={true}
            animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
