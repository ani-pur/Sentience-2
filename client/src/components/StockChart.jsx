import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
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

const PRIVATE_REASON = {
  openai: "OpenAI has not completed an IPO and is not publicly traded.",
  anthropic: "Anthropic is a private company with no public listing.",
  deepseek: "DeepSeek is a privately held Chinese research lab.",
  xai: "xAI is privately held by Elon Musk and has not gone public.",
};

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function StockTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#101f22] border border-primary/20 rounded-lg px-4 py-3 shadow-xl">
      <p className="text-xs text-slate-400 mb-1">{formatDate(label)}</p>
      <p className="text-sm font-bold text-emerald-400">
        ${payload[0].value?.toFixed(2)}
      </p>
    </div>
  );
}

export default function StockChart({ stock, brand, loading }) {
  const brandName = BRAND_NAMES[brand] || brand;

  if (loading) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6 h-[340px] flex items-center justify-center">
        <p className="text-slate-500 animate-pulse">Loading stock data...</p>
      </div>
    );
  }

  // Private company
  if (!stock || stock.private) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold">Stock Price</h2>
            <p className="text-sm text-slate-500">{brandName}</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center h-52 text-center gap-3">
          <span className="material-symbols-outlined text-5xl text-slate-600">lock</span>
          <p className="text-slate-300 font-semibold text-base">Privately Owned</p>
          <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
            {PRIVATE_REASON[brand] || `${brandName} is not publicly traded.`}
          </p>
        </div>
      </div>
    );
  }

  // Public company with no data
  if (!stock.data?.length) {
    return (
      <div className="bg-panel border border-border rounded-2xl p-6 h-[340px] flex items-center justify-center">
        <p className="text-slate-500">No stock data available for {stock.ticker}</p>
      </div>
    );
  }

  const prices = stock.data.map((d) => d.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const latest = prices[prices.length - 1];
  const prev = prices[prices.length - 2] ?? latest;
  const change = latest - prev;
  const changePct = ((change / prev) * 100).toFixed(2);
  const isUp = change >= 0;
  const changeColor = isUp ? "text-emerald-400" : "text-red-400";

  // Y-axis domain with 5% padding
  const pad = (maxPrice - minPrice) * 0.05;
  const yMin = +(minPrice - pad).toFixed(2);
  const yMax = +(maxPrice + pad).toFixed(2);

  return (
    <div className="bg-panel border border-border rounded-2xl p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">Stock Price</h2>
          <p className="text-sm text-slate-500">
            {brandName} &middot; <span className="text-primary font-mono">{stock.ticker}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-slate-100">${latest.toFixed(2)}</p>
          <p className={`text-xs font-semibold ${changeColor}`}>
            {isUp ? "+" : ""}{change.toFixed(2)} ({isUp ? "+" : ""}{changePct}%) today
          </p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={stock.data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <defs>
            <linearGradient id="stockGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#34d399" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(52, 211, 153, 0.06)" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            stroke="#475569"
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={{ stroke: "rgba(52, 211, 153, 0.1)" }}
          />
          <YAxis
            domain={[yMin, yMax]}
            tickFormatter={(v) => `$${v}`}
            stroke="#475569"
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={{ stroke: "rgba(52, 211, 153, 0.1)" }}
            width={60}
          />
          <Tooltip content={<StockTooltip />} />
          <Area
            type="monotone"
            dataKey="price"
            stroke="#34d399"
            strokeWidth={2}
            fill="url(#stockGradient)"
            dot={false}
            isAnimationActive={true}
            animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>

      <p className="text-[10px] text-slate-600 mt-3 text-right">
        Source: Yahoo Finance &middot; 90-day window &middot; EOD close prices
      </p>
    </div>
  );
}
