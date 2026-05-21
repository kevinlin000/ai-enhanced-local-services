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

export const javaApi = {
  listCategories: () =>
    fetchJson<{ success: boolean; data: Category[] }>(
      `${JAVA_API}/api/category/list`,
    ),
  listMrtStations: () =>
    fetchJson<{ success: boolean; data: unknown[] }>(
      `${JAVA_API}/api/mrt/stations`,
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
};
