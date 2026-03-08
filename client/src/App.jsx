import { useState, useEffect } from "react";
import { useUser, useBrands, useSentiment, useDaily, usePosts, useStock } from "./hooks/useApi";
import Header from "./components/Header";
import SentimentChart from "./components/SentimentChart";
import MetricCards from "./components/MetricCards";
import PostsFeed from "./components/PostsFeed";
import StockChart from "./components/StockChart";

function App() {
  const { user, loading: authLoading } = useUser();
  const { brands } = useBrands();
  const [selectedBrand, setSelectedBrand] = useState("openai");
  const { data: sentimentData, loading: chartLoading } = useSentiment(selectedBrand);
  const { data: dailyData, loading: dailyLoading } = useDaily(selectedBrand);
  const { posts, loading: postsLoading } = usePosts(selectedBrand);
  const sentimentStart = sentimentData.find((d) => !d.is_projection)?.date ?? null;
  const { stock, loading: stockLoading } = useStock(selectedBrand, sentimentStart);

  useEffect(() => {
    if (!authLoading && !user) {
      window.location.href = '/landing';
    }
  }, [user, authLoading]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-bg-dark flex items-center justify-center">
        <div className="text-center">
          <div className="text-primary">
            <svg className="w-12 h-12 mx-auto mb-4" fill="none" viewBox="0 0 48 48">
              <path d="M44 4H30.6666V17.3334H17.3334V30.6666H4V44H44V4Z" fill="currentColor" />
            </svg>
          </div>
          <p className="text-slate-500 animate-pulse">Loading Sentience...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg-dark">
      {/* Background glows */}
      <div className="fixed top-0 left-0 w-full h-full -z-10 pointer-events-none overflow-hidden">
        <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[120px]" />
      </div>

      <Header user={user} brands={brands} selected={selectedBrand} onSelect={setSelectedBrand} />

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <MetricCards data={dailyData} loading={dailyLoading} />
        <SentimentChart data={sentimentData} brand={selectedBrand} loading={chartLoading} />
        <PostsFeed posts={posts} loading={postsLoading} />
        <StockChart stock={stock} brand={selectedBrand} loading={stockLoading} />
      </main>
    </div>
  );
}

export default App;
