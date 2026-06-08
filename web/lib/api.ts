const JAVA_API = process.env.NEXT_PUBLIC_JAVA_API ?? "http://localhost:8081";
// AI calls use relative /api/ai/* — proxied through Next.js rewrite to http://localhost:8000
// This avoids mixed content (HTTPS page → HTTP direct). Never use http://localhost:8000 directly.
const AI_API = "";
// Client-side calls must go through Next.js rewrite proxy to avoid
// mixed content (HTTPS page → HTTP API). Only use from "use client" components.
const CLIENT_JAVA_API = "/api/java";

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

export type MyBooking = {
  bookingCode: string;
  userId?: number | null;
  shopId: number;
  shopName: string;
  people: number;
  date: string;
  time: string;
  tableType: string;
  needsDeposit: boolean;
  depositTotal: number;
  status: "PENDING_PAYMENT" | "PAID" | "CONFIRMED" | "CANCELED" | "EXPIRED";
  paymentTransId?: string | null;
  holdExpiresAt?: string | null;
  holdMinutes?: number | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  idempotentReplay?: boolean;
};

export type AvailabilityWatch = {
  id: number;
  shopId: number;
  shopName: string;
  date: string;
  time: string;
  tableType: string;
  people: number;
  status: "ACTIVE" | "TRIGGERED" | "CANCELED" | "EXPIRED";
  triggeredAt?: string | null;
  expiresAt: string;
  createdAt: string;
};

export type UserNotification = {
  id: number;
  type: "AVAILABILITY_RELEASED" | string;
  title: string;
  body: string;
  shopId?: number | null;
  shopName?: string | null;
  watchId?: number | null;
  status: "UNREAD" | "READ";
  date?: string | null;
  time?: string | null;
  tableType?: string | null;
  people?: number | null;
  createdAt: string;
  readAt?: string | null;
};

export type FavoriteShop = Shop & {
  shopId: number;
  favoritedAt: string;
};

function merchantHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Demo-Mode": "true",
  };
}

export class AuthRequiredError extends Error {
  constructor() {
    super("請先用 LINE 登入後再使用此功能");
    this.name = "AuthRequiredError";
  }
}

function authHeaders(contentType = false): HeadersInit {
  const headers: Record<string, string> = {};
  if (contentType) headers["Content-Type"] = "application/json";

  const token = typeof window !== "undefined"
    ? window.localStorage.getItem("bytebites_token")
    : null;
  if (!token) throw new AuthRequiredError();
  headers.Authorization = `Bearer ${token}`;
  return headers;
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
  payBookingWithTestCard: (bookingCode: string) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        bookingCode: string;
        rec_trade_id: string;
        amount: number;
        status: "PAID";
        note?: string;
      };
    }>(`${CLIENT_JAVA_API}/api/booking/pay-test`, {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({ bookingCode }),
    }),
  payBookingByPrime: (body: { prime: string; amount: number; bookingCode: string }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        bookingCode: string;
        rec_trade_id: string;
        amount: number;
        status: "PAID";
        tappay_status: number;
        msg?: string;
      };
    }>(`${CLIENT_JAVA_API}/api/payment/tappay/pay-by-prime`, {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({
        prime: body.prime,
        amount: body.amount,
        bookingCode: body.bookingCode,
        orderId: Math.floor(Math.random() * 100000000),
      }),
    }),
  myBookings: () =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking[] }>(
      `${CLIENT_JAVA_API}/api/booking/my`,
      { headers: authHeaders() },
    ),
  cancelBooking: (bookingCode: string) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/cancel`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  createAvailabilityWatch: (body: {
    shopId: number;
    date: string;
    time: string;
    tableType?: string;
    people: number;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: AvailabilityWatch }>(
      `${CLIENT_JAVA_API}/api/availability/watches`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          shopId: body.shopId,
          date: body.date,
          time: body.time,
          tableType: body.tableType ?? "normal",
          people: body.people,
        }),
      },
    ),
  availabilityWatches: () =>
    fetchJson<{ success: boolean; errorMsg?: string; data: AvailabilityWatch[] }>(
      `${CLIENT_JAVA_API}/api/availability/watches`,
      { headers: authHeaders() },
    ),
  cancelAvailabilityWatch: (id: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: { id: number; status: "CANCELED" } }>(
      `${CLIENT_JAVA_API}/api/availability/watches/${id}/cancel`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  notifications: () =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: { unreadCount: number; items: UserNotification[] };
    }>(`${CLIENT_JAVA_API}/api/availability/notifications`, {
      headers: authHeaders(),
    }),
  markNotificationRead: (id: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: { id: number; status: "READ" } }>(
      `${CLIENT_JAVA_API}/api/availability/notifications/${id}/read`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  markAllNotificationsRead: () =>
    fetchJson<{ success: boolean; errorMsg?: string; data: { updated: number } }>(
      `${CLIENT_JAVA_API}/api/availability/notifications/read-all`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  favoriteShops: () =>
    fetchJson<{ success: boolean; errorMsg?: string; data: FavoriteShop[] }>(
      `${CLIENT_JAVA_API}/api/favorites/shops`,
      { headers: authHeaders() },
    ),
  favoriteStatus: (shopId: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: { shopId: number; favorited: boolean } }>(
      `${CLIENT_JAVA_API}/api/favorites/shops/${shopId}`,
      { headers: authHeaders() },
    ),
  saveFavoriteShop: (shopId: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: { shopId: number; favorited: boolean } }>(
      `${CLIENT_JAVA_API}/api/favorites/shops/${shopId}`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  removeFavoriteShop: (shopId: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: { shopId: number; favorited: boolean } }>(
      `${CLIENT_JAVA_API}/api/favorites/shops/${shopId}`,
      {
        method: "DELETE",
        headers: authHeaders(true),
      },
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
  merchantShops: () =>
    fetchJson<{ success: boolean; data: MerchantShop[] }>(
      `${CLIENT_JAVA_API}/api/merchant/shops`,
      { headers: merchantHeaders() },
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
      { headers: merchantHeaders() },
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
      headers: merchantHeaders(),
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
