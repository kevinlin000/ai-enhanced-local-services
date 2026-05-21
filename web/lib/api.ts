const JAVA_API = process.env.NEXT_PUBLIC_JAVA_API ?? "http://localhost:8081";
const AI_API = process.env.NEXT_PUBLIC_AI_API ?? "http://localhost:8000";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const javaApi = {
  listCategories: () =>
    fetchJson<{ success: boolean; data: unknown[] }>(
      `${JAVA_API}/api/category/list`,
    ),
  listMrtStations: () =>
    fetchJson<{ success: boolean; data: unknown[] }>(
      `${JAVA_API}/api/mrt/stations`,
    ),
};

export const aiApi = {
  health: () => fetchJson<{ status: string }>(`${AI_API}/health`),
};
