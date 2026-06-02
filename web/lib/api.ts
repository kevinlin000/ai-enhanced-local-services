const JAVA_API = process.env.NEXT_PUBLIC_JAVA_API ?? "http://localhost:8081";
// AI calls use relative /api/ai/* — proxied through Next.js rewrite to http://localhost:8000
// This avoids mixed content (HTTPS page → HTTP direct). Never use http://localhost:8000 directly.
const AI_API = "";
// Client-side calls must go through Next.js rewrite proxy to avoid
// mixed content (HTTPS page → HTTP API). Only use from "use client" components.
const CLIENT_JAVA_API = "/api/java";
const CLIENT_AI_API = "/api/ai";

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
  comments?: number;
  district?: string;
  mrtStation?: string;
  priceRange?: number;
  businessHours?: string;
  x?: number;
  y?: number;
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
  category?: string | null;
  avg_price?: number | null;
  price_per_person?: string | null;
  booking_difficulty?: string | null;
  atmosphere_tags?: string[];
  signature_dishes?: string[];
  hot_seat_count?: number;
};

export type ShopAiMetadata = {
  shopId: number;
  aiSummary?: string;
  highlightReview?: string;
  signatureDishes?: string;
  atmosphereTags?: string;
  bookingDifficulty?: string;
  pricePerPerson?: string;
  phone?: string;
  openingHours?: string;
  extractedAt?: string;
  modelVersion?: string;
};

export type AbsaEvidence = {
  claim: string;
  concrete_terms: string[];
  source_review_ids: number[];
};

export type AbsaAspect = {
  aspect: "dishes" | "service" | "environment" | "price";
  summary: string;
  sentiment: "positive" | "negative" | "mixed" | "neutral";
  confidence: "high" | "medium" | "low";
  mention_count?: number;
  positive_evidence?: AbsaEvidence[];
  negative_evidence?: AbsaEvidence[];
};

export type ShopAbsa = {
  shopId: number;
  aspects: string;
  charHitRate?: number;
  semanticHitRate?: number;
  promptVersion?: string;
  model?: string;
  generatedAt?: string;
};

export type VoucherOffer = {
  id: number;
  shopId: number;
  title: string;
  subTitle?: string;
  rules?: string;
  payValue: number;
  actualValue: number;
  type: number;
  status: number;
  stock?: number;
  beginTime?: string;
  endTime?: string;
};

export type MerchantShop = {
  id: number;
  name: string;
  district?: string;
  address?: string;
  role: string;
};

export type MerchantSlot = {
  time: string;
  tableType: string;
  capacity: number;
  bookedCount: number;
  remaining: number;
};

function merchantHeaders(token?: string | null): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Demo-Mode": token ? "false" : "true",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export const javaApi = {
  listCategories: () =>
    fetchJson<{ success: boolean; data: Category[] }>(
      `${JAVA_API}/api/category/list`,
    ),
  listMrtStations: () =>
    fetchJson<{ success: boolean; data: unknown[] }>(
      `${JAVA_API}/api/mrt/stations`,
    ),
  shopCount: () =>
    fetchJson<{ success: boolean; data: number }>(`${JAVA_API}/api/shop/count`),
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
  shopAiMetadata: (id: string | number) =>
    fetchJson<{ success: boolean; data: ShopAiMetadata | null }>(
      `${JAVA_API}/api/shop/${id}/ai-metadata`,
    ),
  shopAbsa: (id: string | number) =>
    fetchJson<{ success: boolean; data: ShopAbsa | null }>(
      `${JAVA_API}/api/shop/${id}/absa`,
    ),
  shopVouchers: (shopId: number) =>
    fetchJson<{ success: boolean; data: VoucherOffer[] }>(
      `${JAVA_API}/voucher/list/${shopId}`,
    ),
  hotSeatVouchers: (shopId: number) =>
    fetchJson<{
      success: boolean;
      data: {
        id: number;
        title: string;
        pay_value: number;
        actual_value: number;
        stock: number;
      }[];
    }>(`${JAVA_API}/api/shop/${shopId}/hot-seat-vouchers`),
  paymentMethods: () =>
    fetchJson<{ success: boolean; data: { code: number; label: string }[] }>(
      `${JAVA_API}/api/payment/methods`,
    ),
  tappayMockCallback: (body: { orderId: number; payType: number; amount: number }) =>
    fetchJson<{ success: boolean; data: { status: string; rec_trade_id: string; pay_type: number; label: string; amount: number } }>(
      `${JAVA_API}/api/payment/tappay/mock-callback`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  // shopFilterOptions + shopSearch: client-side only → use proxy to avoid mixed content
  shopFilterOptions: () =>
    fetchJson<{
      success: boolean;
      data: {
        types: { id: number; name: string; count: number }[];
        districts: { name: string; count: number }[];
        mrtStations: { name: string; count: number }[];
        totalShops: number;
      };
    }>(`${CLIENT_JAVA_API}/api/shop/filter-options`),
  shopSearch: (params: {
    q?: string;
    typeIds?: number[];
    districts?: string[];
    mrtStations?: string[];
    minScore?: number;
    page?: number;
    size?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params.q) sp.set("q", params.q);
    params.typeIds?.forEach((id) => sp.append("typeIds", String(id)));
    params.districts?.forEach((d) => sp.append("districts", d));
    params.mrtStations?.forEach((m) => sp.append("mrtStations", m));
    if (params.minScore != null) sp.set("minScore", String(params.minScore));
    if (params.page) sp.set("page", String(params.page));
    if (params.size) sp.set("size", String(params.size));
    return fetchJson<{ success: boolean; data: { records: Shop[]; total: number } }>(
      `${CLIENT_JAVA_API}/api/shop/search?${sp.toString()}`,
    );
  },
  merchantShops: (token?: string | null) =>
    fetchJson<{ success: boolean; data: MerchantShop[] }>(
      `${CLIENT_JAVA_API}/api/merchant/shops`,
      { headers: merchantHeaders(token) },
    ),
  merchantSlots: (params: {
    shopId: number;
    date: string;
    tableType?: string;
    token?: string | null;
  }) =>
    fetchJson<{
      success: boolean;
      data: {
        shopId: number;
        date: string;
        tableType: string;
        slots: MerchantSlot[];
      };
    }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/slots?date=${encodeURIComponent(params.date)}&tableType=${encodeURIComponent(params.tableType ?? "normal")}`,
      { headers: merchantHeaders(params.token) },
    ),
  updateMerchantSlots: (params: {
    shopId: number;
    date: string;
    tableType?: string;
    token?: string | null;
    slots: { time: string; capacity: number }[];
  }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        shopId: number;
        date: string;
        tableType: string;
        slots: MerchantSlot[];
      };
    }>(`${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/slots`, {
      method: "PUT",
      headers: merchantHeaders(params.token),
      body: JSON.stringify({
        date: params.date,
        tableType: params.tableType ?? "normal",
        slots: params.slots,
      }),
    }),
};

export const aiApi = {
  health: () => fetchJson<{ status: string }>(`/api/python/health`),
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
