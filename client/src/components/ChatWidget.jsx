import { useState, useRef, useEffect } from "react";
import { useChat } from "../hooks/useChat";

const BRAND_NAMES = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google",
  xai: "xAI",
  deepseek: "DeepSeek",
  microsoft: "Microsoft",
  alibaba: "Alibaba",
};

function renderMarkdown(text) {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong class='text-slate-100 font-semibold'>$1</strong>");

  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code class='px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-mono'>$1</code>");

  // Convert bullet lines
  html = html.replace(/^[-•]\s+(.+)$/gm, "<li class='ml-3 pl-1'>$1</li>");
  html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, (match) => `<ul class='space-y-1 my-1.5 list-disc list-outside ml-2 text-slate-400'>${match}</ul>`);

  // Numbered lists
  html = html.replace(/^\d+\.\s+(.+)$/gm, "<li class='ml-3 pl-1'>$1</li>");

  // Line breaks
  html = html.replace(/\n/g, "<br/>");

  return html;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      <div className="flex items-center gap-[3px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="block w-[5px] h-[5px] rounded-full bg-primary/60"
            style={{
              animation: "chatDot 1.4s ease-in-out infinite",
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>
      <span className="text-[11px] text-slate-600 ml-1.5">Analyzing...</span>
    </div>
  );
}

export default function ChatWidget({ brand }) {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const { messages, loading, sendMessage, clearHistory } = useChat(brand);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    sendMessage(text);
  }

  const suggestions = [
    `Summarize ${BRAND_NAMES[brand] || brand}'s sentiment`,
    "Any recent anomalies?",
    "Stock correlation insights",
    "Compare with competitors",
  ];

  return (
    <>
      <style>{`
        @keyframes chatDot {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
        @keyframes chatSlideUp {
          from { opacity: 0; transform: translateY(12px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes chatFadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .chat-panel { animation: chatSlideUp 0.25s ease-out; }
        .chat-msg { animation: chatFadeIn 0.2s ease-out; }
      `}</style>

      {/* Floating toggle button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-primary/20 border border-primary/30 text-primary flex items-center justify-center shadow-lg shadow-primary/10 hover:bg-primary/30 hover:scale-105 hover:shadow-primary/20 transition-all duration-200 cursor-pointer backdrop-blur-sm"
        >
          <span className="material-symbols-outlined text-2xl">chat</span>
        </button>
      )}

      {/* Chat panel */}
      {isOpen && (
        <div className="chat-panel fixed bottom-6 right-6 z-50 w-[400px] h-[520px] flex flex-col rounded-2xl border border-primary/15 shadow-2xl shadow-black/40 overflow-hidden"
          style={{ background: "linear-gradient(165deg, rgba(16, 31, 34, 0.97) 0%, rgba(10, 22, 26, 0.98) 100%)", backdropFilter: "blur(20px)" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-primary/10 shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-[16px]">neurology</span>
              </div>
              <div>
                <h3 className="text-sm font-bold tracking-tight text-slate-100">Sentience AI</h3>
              </div>
              <span className="ml-1 px-2 py-0.5 rounded-md bg-primary/10 text-primary text-[10px] font-medium uppercase tracking-wide">
                {BRAND_NAMES[brand] || brand}
              </span>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  onClick={clearHistory}
                  className="w-7 h-7 rounded-lg hover:bg-slate-800/60 flex items-center justify-center text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
                  title="Clear chat"
                >
                  <span className="material-symbols-outlined text-[16px]">delete_sweep</span>
                </button>
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="w-7 h-7 rounded-lg hover:bg-slate-800/60 flex items-center justify-center text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && !loading && (
              <div className="h-full flex flex-col items-center justify-center text-center px-4">
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                  <span className="material-symbols-outlined text-primary text-2xl">insights</span>
                </div>
                <p className="text-sm text-slate-300 font-medium mb-1">Ask me anything</p>
                <p className="text-xs text-slate-500 mb-5">
                  I analyze sentiment data, anomalies, stock correlations, and more for {BRAND_NAMES[brand] || brand}.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setInput(""); sendMessage(s); }}
                      className="px-3 py-1.5 rounded-lg border border-primary/15 bg-primary/5 text-xs text-slate-300 hover:bg-primary/10 hover:text-primary hover:border-primary/25 transition-all duration-150 cursor-pointer"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`chat-msg flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-[13px] leading-relaxed ${
                    msg.role === "user"
                      ? "bg-primary/15 text-slate-200 rounded-br-md"
                      : "bg-slate-800/40 border border-slate-700/30 text-slate-300 rounded-bl-md"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <div
                      className="[&_strong]:text-slate-100 [&_ul]:my-1 [&_li]:text-slate-400"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                    />
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="chat-msg flex justify-start">
                <div className="bg-slate-800/40 border border-slate-700/30 rounded-2xl rounded-bl-md">
                  <TypingIndicator />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="shrink-0 px-3 pb-3 pt-1">
            <div className="flex items-center gap-2 rounded-xl border border-primary/10 bg-slate-900/60 px-3 py-1.5 focus-within:border-primary/25 transition-colors">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder="Ask about sentiment, stocks, trends..."
                className="flex-1 bg-transparent text-sm text-slate-200 placeholder:text-slate-600 outline-none"
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="w-8 h-8 rounded-lg bg-primary/20 text-primary flex items-center justify-center hover:bg-primary/30 disabled:opacity-30 disabled:hover:bg-primary/20 transition-all cursor-pointer disabled:cursor-default"
              >
                <span className="material-symbols-outlined text-[18px]">arrow_upward</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
