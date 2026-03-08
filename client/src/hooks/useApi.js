import { useState, useEffect } from "react";

const fetchOpts = { credentials: "include" };

function useFetch(url, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(url, fetchOpts)
      .then((res) => {
        if (!res.ok) throw new Error(res.status);
        return res.json();
      })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, deps);

  return { data, loading, error };
}

export function useUser() {
  const { data, loading, error } = useFetch("/api/me");
  return { user: data, loading, error };
}

export function useBrands() {
  const { data, loading } = useFetch("/api/brands");
  return { brands: data || [], loading };
}

export function useSentiment(brand) {
  const { data, loading } = useFetch(`/api/sentiment?brand=${brand}`, [brand]);
  return { data: data || [], loading };
}

export function useDaily(brand) {
  const { data, loading } = useFetch(`/api/daily?brand=${brand}`, [brand]);
  return { data: data || [], loading };
}

export function usePosts(brand) {
  const { data, loading } = useFetch(`/api/posts?brand=${brand}`, [brand]);
  return { posts: data || [], loading };
}

export function useStock(brand, startDate) {
  const from = startDate ? `&from=${startDate}` : "";
  const { data, loading } = useFetch(`/api/stock?brand=${brand}${from}`, [brand, startDate]);
  return { stock: data || null, loading };
}
