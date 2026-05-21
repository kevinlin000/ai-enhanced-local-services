const JAVA_API = process.env.NEXT_PUBLIC_JAVA_API ?? "http://localhost:8081";
const AI_API = process.env.NEXT_PUBLIC_AI_API ?? "http://localhost:8000";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export type Shop = {
  id: number;
  name: string;
  typeId: number;
  area?: string;
  address?: string;
  images?: string;
  avgPrice?: number;
  score?: number;
  district?: string;
  mrtStation?: string;
  priceRange?: number;
  businessHours?: string;
};

export type Category = {
  id: number;
  name: string;
  slug: string;
};

export type SearchHit = {
  shop_id: number;
  name: string;
  district: string | null;
  mrt_station: string | null;
  score: number;
};

export const javaApi = {
  listCategories: () =>
    fetchJson<{ success: boolean; data: Category[] }>(
      `${JAVA_API}/api/category/list`,
    ),
  listMrtStations: () =>
    fetchJson<{ success: boolean; data: unknown[] }>(
      `${JAVA_API}/api/mrt/stations`,
    ),
  popularShopsByMrt: (station: string) =>
    fetchJson<{ success: boolean; data: Shop[] }>(
      `${JAVA_API}/api/mrt/${encodeURIComponent(station)}/popular-shops`,
    ),
  shopsByCategory: (slug: string, page = 1, size = 20) =>
    fetchJson<{ success: boolean; data: Shop[] }>(
      `${JAVA_API}/api/category/${slug}/shops?page=${page}&size=${size}`,
    ),
  shopDetail: (id: number) =>
    fetchJson<{ success: boolean; data: Shop }>(`${JAVA_API}/api/shop/${id}`),
};

export const aiApi = {
  health: () => fetchJson<{ status: string }>(`${AI_API}/health`),
  search: (query: string, top_k = 5) =>
    fetchJson<{ query: string; hits: SearchHit[] }>(`${AI_API}/api/ai/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k }),
    }),
  recommend: (query: string, top_k = 5) =>
    fetchJson<{ query: string; answer: string; hits: SearchHit[] }>(
      `${AI_API}/api/ai/recommend`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k }),
      },
    ),
  agent: (query: string) =>
    fetchJson<{
      query: string;
      answer: string;
      tool_used: string | null;
      tool_args?: unknown;
    }>(`${AI_API}/api/ai/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    }),
};
