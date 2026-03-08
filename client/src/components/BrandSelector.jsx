const BRAND_NAMES = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  xai: "xAI",
  deepseek: "DeepSeek",
  microsoft: "Microsoft",
  alibaba: "Alibaba",
};

export default function BrandSelector({ brands, selected, onSelect }) {
  const list = brands.length > 0 ? brands : Object.keys(BRAND_NAMES);

  return (
    <div className="flex flex-wrap gap-2">
      {list.map((brand) => (
        <button
          key={brand}
          onClick={() => onSelect(brand)}
          className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-all cursor-pointer ${
            selected === brand
              ? "bg-primary text-[#101f22]"
              : "bg-primary/5 border border-primary/10 text-slate-400 hover:border-primary/40 hover:text-slate-200"
          }`}
        >
          {BRAND_NAMES[brand] || brand}
        </button>
      ))}
    </div>
  );
}
