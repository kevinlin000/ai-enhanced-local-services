const RAW_JAVA_API = process.env.NEXT_PUBLIC_JAVA_API ?? "/api/java";
const SERVER_JAVA_API = process.env.JAVA_API_PROXY_TARGET ?? "http://localhost:8081";
const JAVA_API =
  typeof window === "undefined"
    ? SERVER_JAVA_API
    : RAW_JAVA_API.startsWith("http://localhost") || RAW_JAVA_API.startsWith("http://127.0.0.1")
    ? "/api/java"
    : RAW_JAVA_API;
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

export type NearbyParkingLot = {
  id: string;
  name: string;
  area?: string;
  address?: string;
  lng: number;
  lat: number;
  distanceMeters: number;
  totalCar?: number | null;
  availableCar?: number | null;
  payText?: string;
  serviceTime?: string;
  updatedAt?: string;
  navigationUrl: string;
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

export type MerchantAlternativeSlot = {
  time: string;
  tableType: string;
  capacity: number;
  bookedCount: number;
  remaining: number;
  label?: string;
};

export type IncidentProposedChange = {
  status: "PENDING" | "ACCEPTED" | "DECLINED" | "EXPIRED" | string;
  date: string;
  time: string;
  tableType: string;
  people: number;
  message?: string;
  proposedAt?: string;
  expiresAt?: string;
  acceptedAt?: string;
  declinedAt?: string;
};

export type MerchantIncident = {
  id: number;
  bookingCode: string;
  userId?: number | null;
  shopId: number;
  shopName: string;
  bookingDate: string;
  bookingTime: string;
  people: number;
  tableType: string;
  bookingStatus: "PENDING_PAYMENT" | "PAID" | "CONFIRMED" | "CANCELED" | "EXPIRED" | "UNKNOWN";
  incidentType: "RESTAURANT_DELAY" | "CUSTOMER_LATE" | string;
  status: "OPEN" | "RESOLVED" | string;
  delayMinutes: number;
  originalTime: string;
  adjustedTime: string;
  title: string;
  customerMessage: string;
  actionLabel: string;
  source: string;
  alternativeSlots?: MerchantAlternativeSlot[];
  proposedChange?: IncidentProposedChange;
  createdAt?: string;
  updatedAt?: string;
  resolvedAt?: string;
};

export type MerchantDepositAdjustment = {
  id: number;
  bookingCode: string;
  incidentId?: number | null;
  userId?: number | null;
  shopId: number;
  shopName: string;
  bookingDate: string;
  bookingTime: string;
  bookingPeople: number;
  bookingTableType: string;
  bookingStatus: "PENDING_PAYMENT" | "PAID" | "CONFIRMED" | "CANCELED" | "EXPIRED" | "UNKNOWN";
  status: "OPEN" | "RESOLVED" | string;
  adjustmentType: "TOP_UP" | "REFUND" | string;
  source: "CUSTOMER_RESCHEDULE" | "INCIDENT_PROPOSAL" | string;
  currentDepositTotal: number;
  proposedDepositTotal: number;
  deltaAmount: number;
  proposedDate: string;
  proposedTime: string;
  proposedTableType: string;
  proposedPeople: number;
  message: string;
  handlingNote?: string;
  handledByUserId?: number | null;
  handledAt?: string;
  appliedBookingUpdate: boolean;
  settlementStatus: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | string;
  settlementProvider?: string;
  settlementTransId?: string;
  settlementAmount: number;
  settlementRequestedAt?: string;
  settlementCompletedAt?: string;
  settlementNote?: string;
  settlementRecordedByUserId?: number | null;
  refundEscalatedAt?: string;
  refundEscalationNote?: string;
  refundEscalatedByUserId?: number | null;
  createdAt?: string;
  updatedAt?: string;
};

export type MerchantRefundSlaSummary = {
  shopId: number;
  stuckMinutes: number;
  stuckProcessingCount: number;
  failedCount: number;
  escalatedCount: number;
  pendingEscalationCount: number;
  totalAttentionCount: number;
  oldestRequestedAt?: string;
  items: Array<MerchantDepositAdjustment & { slaReason?: "STUCK_PROCESSING" | "FAILED_REFUND" | string }>;
};

export type MerchantRefundOperationsReport = {
  shopId: number;
  stuckMinutes: number;
  status: "ACTION_REQUIRED" | "FOLLOW_UP" | "CLEAR" | string;
  recommendedAction:
    | "ESCALATE_FAILED_REFUNDS"
    | "ESCALATE_STUCK_REFUNDS"
    | "FOLLOW_UP_ESCALATED_REFUNDS"
    | "NO_REFUND_ACTION"
    | string;
  headline: string;
  totalAttentionCount: number;
  pendingEscalationCount: number;
  escalatedCount: number;
  failedCount: number;
  stuckProcessingCount: number;
  pendingFailedCount: number;
  pendingStuckProcessingCount: number;
  escalatedFailedCount: number;
  escalatedStuckProcessingCount: number;
  oldestPendingRequestedAt?: string;
  oldestEscalatedAt?: string;
  pendingEscalationItems: Array<MerchantDepositAdjustment & { slaReason?: "STUCK_PROCESSING" | "FAILED_REFUND" | string }>;
  escalatedItems: Array<MerchantDepositAdjustment & { slaReason?: "STUCK_PROCESSING" | "FAILED_REFUND" | string }>;
};

export type MerchantRefundNotificationPolicy = {
  notificationType: "REFUND_OPERATIONS_DIGEST" | string;
  shopId: number;
  cooldownMinutes: number;
  reportStatus?: string;
  headline?: string;
  totalAttentionCount: number;
  pendingEscalationCount: number;
  escalatedCount: number;
  shouldNotify: boolean;
  reason: "ACTION_REQUIRED" | "NO_REFUND_ATTENTION" | "COOLDOWN_ACTIVE" | "MISSING_SHOP" | string;
  lastSentAt?: string;
  nextEligibleAt?: string;
};

export type MerchantRefundNotificationDispatchResponse = {
  shopId: number;
  lineNotification: "SENT" | "SKIPPED" | string;
  skipped: boolean;
  reason?: string;
  report: MerchantRefundOperationsReport;
  policy?: MerchantRefundNotificationPolicy;
};

export type CustomerTopUpAdjustment = MerchantDepositAdjustment;

export type BookingIncident = {
  id?: number;
  bookingCode: string;
  userId?: number | null;
  shopId: number;
  shopName: string;
  incidentType: "RESTAURANT_DELAY" | "CUSTOMER_LATE" | string;
  status: "OPEN" | "RESOLVED" | string;
  delayMinutes: number;
  originalTime: string;
  adjustedTime: string;
  title: string;
  customerMessage: string;
  actionLabel: string;
  source: string;
  proposedChange?: IncidentProposedChange;
  createdAt?: string;
  updatedAt?: string;
  resolvedAt?: string;
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
  drivingToBooking?: boolean;
  parkingReminderEnabled?: boolean;
  parkingReminderSentAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  idempotentReplay?: boolean;
  latestIncident?: BookingIncident | null;
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

export type DiningMemory = {
  bookingCode: string;
  shopId: number;
  shopName: string;
  rating: 1 | 2 | 3;
  tags: string[];
  note?: string;
  doNotRecommend: boolean;
  createdAt?: string;
  updatedAt?: string;
};

export type DiningMemorySummary = {
  memories: DiningMemory[];
  tagCounts: Record<string, number>;
  avoidShopIds: number[];
};

export type PrivateAiOffer = {
  id?: number;
  shopId: number;
  shopName: string;
  offerCode: string;
  title: string;
  description: string;
  triggerReason: "OFF_PEAK_FILL" | "REPEATED_SEARCH_NO_BOOKING" | "SAVE_MONEY_INTENT" | "AI_RECOMMENDATION" | string;
  offerType: string;
  discountPercent: number;
  minPeople: number;
  validUntil: string;
  status: "ACTIVE" | "CLAIMED" | "EXPIRED" | string;
  createdAt?: string;
  updatedAt?: string;
  claimedAt?: string;
};

export type PrivateAiOfferSummary = {
  offers: PrivateAiOffer[];
  created?: boolean;
  triggerReason?: string;
  reason?: string;
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
  nearbyParking: (params: { lng: number; lat: number; radius?: number; limit?: number }) => {
    const sp = new URLSearchParams({
      lng: String(params.lng),
      lat: String(params.lat),
      radius: String(params.radius ?? 800),
      limit: String(params.limit ?? 5),
    });
    return fetchJson<{ success: boolean; data: NearbyParkingLot[] }>(
      `${JAVA_API}/api/parking/nearby?${sp.toString()}`,
    );
  },
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
  reserveBooking: (body: {
    shopId: number;
    people: number;
    date: string;
    time: string;
    tableType?: string;
    idempotencyKey?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking }>(
      `${CLIENT_JAVA_API}/api/booking/reserve`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          shopId: body.shopId,
          people: body.people,
          date: body.date,
          time: body.time,
          tableType: body.tableType ?? "normal",
          idempotencyKey: body.idempotencyKey,
        }),
      },
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
  customerTopUpAdjustments: () =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        adjustments: CustomerTopUpAdjustment[];
      };
    }>(`${CLIENT_JAVA_API}/api/payment/deposit-adjustments/top-ups`, {
      headers: authHeaders(),
    }),
  payTopUpByPrime: (body: { prime: string; adjustmentId: number }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        adjustmentId: number;
        bookingCode: string;
        rec_trade_id: string;
        amount: number;
        status: "PAID";
        tappay_status: number;
        adjustment: CustomerTopUpAdjustment;
        msg?: string;
      };
    }>(
      `${CLIENT_JAVA_API}/api/payment/tappay/deposit-adjustments/${body.adjustmentId}/top-up/pay-by-prime`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          prime: body.prime,
          orderId: Math.floor(Math.random() * 100000000),
        }),
      },
    ),
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
  rescheduleBooking: (
    bookingCode: string,
    body: { date: string; time: string; people: number; tableType?: string },
  ) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking & { changed?: boolean } }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/reschedule`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          date: body.date,
          time: body.time,
          people: body.people,
          tableType: body.tableType ?? "normal",
        }),
      },
    ),
  bookingIncidents: (bookingCode: string) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: BookingIncident[] }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/incidents`,
      { headers: authHeaders() },
    ),
  createBookingIncident: (
    bookingCode: string,
    body: { incidentType: "RESTAURANT_DELAY" | "CUSTOMER_LATE"; delayMinutes?: number; message?: string },
  ) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: BookingIncident }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/incidents`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify(body),
      },
    ),
  resolveBookingIncident: (bookingCode: string, incidentId: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: BookingIncident | { id: number; status: string } }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/incidents/${incidentId}/resolve`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  acceptBookingIncidentProposal: (bookingCode: string, incidentId: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking & { changed?: boolean; acceptedProposal?: unknown } }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/incidents/${incidentId}/proposal/accept`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  declineBookingIncidentProposal: (bookingCode: string, incidentId: number) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking & { declinedProposal?: unknown } }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/incidents/${incidentId}/proposal/decline`,
      {
        method: "POST",
        headers: authHeaders(true),
      },
    ),
  updateParkingPreference: (bookingCode: string, body: { drivingToBooking: boolean; parkingReminderEnabled?: boolean }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MyBooking }>(
      `${CLIENT_JAVA_API}/api/booking/${encodeURIComponent(bookingCode)}/parking-preference`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          drivingToBooking: body.drivingToBooking,
          parkingReminderEnabled: body.parkingReminderEnabled ?? body.drivingToBooking,
        }),
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
  myDiningMemory: () =>
    fetchJson<{ success: boolean; errorMsg?: string; data: DiningMemorySummary }>(
      `${CLIENT_JAVA_API}/api/dining-memory/me`,
      { headers: authHeaders() },
    ),
  saveDiningMemoryForBooking: (
    bookingCode: string,
    body: { rating: 1 | 2 | 3; tags: string[]; note?: string; doNotRecommend?: boolean },
  ) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: DiningMemory }>(
      `${CLIENT_JAVA_API}/api/dining-memory/bookings/${encodeURIComponent(bookingCode)}`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          rating: body.rating,
          tags: body.tags,
          note: body.note ?? "",
          doNotRecommend: body.doNotRecommend ?? false,
        }),
      },
    ),
  myPrivateAiOffers: () =>
    fetchJson<{ success: boolean; errorMsg?: string; data: PrivateAiOfferSummary }>(
      `${CLIENT_JAVA_API}/api/private-offers/me`,
      { headers: authHeaders() },
    ),
  matchPrivateAiOffers: (body: { shopIds: number[]; trigger?: string; people?: number; targetTime?: string }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: PrivateAiOfferSummary }>(
      `${CLIENT_JAVA_API}/api/private-offers/match`,
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify(body),
      },
    ),
  claimPrivateAiOffer: (offerCode: string) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: PrivateAiOffer }>(
      `${CLIENT_JAVA_API}/api/private-offers/${encodeURIComponent(offerCode)}/claim`,
      {
        method: "POST",
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
  merchantIncidents: (params: { shopId: number; status?: "OPEN" | "RESOLVED" | "ALL" }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        shopId: number;
        status: "OPEN" | "RESOLVED" | "ALL";
        incidents: MerchantIncident[];
      };
    }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/incidents?status=${encodeURIComponent(params.status ?? "OPEN")}`,
      { headers: merchantHeaders() },
    ),
  resolveMerchantIncident: (params: { shopId: number; incidentId: number }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantIncident | { id: number; status: string } }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/incidents/${params.incidentId}/resolve`,
      {
        method: "POST",
        headers: merchantHeaders(),
      },
    ),
  proposeMerchantIncidentSlot: (params: {
    shopId: number;
    incidentId: number;
    date?: string;
    time: string;
    tableType?: string;
    people?: number;
    message?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantIncident }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/incidents/${params.incidentId}/proposal`,
      {
        method: "POST",
        headers: merchantHeaders(),
        body: JSON.stringify({
          date: params.date,
          time: params.time,
          tableType: params.tableType,
          people: params.people,
          message: params.message,
        }),
      },
    ),
  merchantDepositAdjustments: (params: { shopId: number; status?: "OPEN" | "RESOLVED" | "ALL" }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: {
        shopId: number;
        status: "OPEN" | "RESOLVED" | "ALL";
        adjustments: MerchantDepositAdjustment[];
      };
    }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments?status=${encodeURIComponent(params.status ?? "OPEN")}`,
      { headers: merchantHeaders() },
    ),
  merchantRefundSla: (params: { shopId: number; stuckMinutes?: number }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantRefundSlaSummary }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/refund-sla?stuckMinutes=${encodeURIComponent(params.stuckMinutes ?? 30)}`,
      { headers: merchantHeaders() },
    ),
  merchantRefundReport: (params: { shopId: number; stuckMinutes?: number }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantRefundOperationsReport }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/refund-report?stuckMinutes=${encodeURIComponent(params.stuckMinutes ?? 30)}`,
      { headers: merchantHeaders() },
    ),
  notifyMerchantRefundReport: (params: { shopId: number; stuckMinutes?: number }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: MerchantRefundNotificationDispatchResponse;
    }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/refund-report/notify?stuckMinutes=${encodeURIComponent(params.stuckMinutes ?? 30)}`,
      {
        method: "POST",
        headers: merchantHeaders(),
      },
    ),
  merchantRefundNotificationPolicy: (params: { shopId: number; stuckMinutes?: number; cooldownMinutes?: number }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantRefundNotificationPolicy }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/refund-report/notification-policy?stuckMinutes=${encodeURIComponent(params.stuckMinutes ?? 30)}&cooldownMinutes=${encodeURIComponent(params.cooldownMinutes ?? 120)}`,
      { headers: merchantHeaders() },
    ),
  dispatchMerchantRefundReportIfDue: (params: { shopId: number; stuckMinutes?: number; cooldownMinutes?: number }) =>
    fetchJson<{
      success: boolean;
      errorMsg?: string;
      data: MerchantRefundNotificationDispatchResponse;
    }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/refund-report/dispatch-due?stuckMinutes=${encodeURIComponent(params.stuckMinutes ?? 30)}&cooldownMinutes=${encodeURIComponent(params.cooldownMinutes ?? 120)}`,
      {
        method: "POST",
        headers: merchantHeaders(),
      },
    ),
  resolveMerchantDepositAdjustment: (params: {
    shopId: number;
    adjustmentId: number;
    handlingNote?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantDepositAdjustment }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/${params.adjustmentId}/resolve`,
      {
        method: "POST",
        headers: merchantHeaders(),
        body: JSON.stringify({ handlingNote: params.handlingNote }),
      },
    ),
  recordMerchantDepositAdjustmentSettlement: (params: {
    shopId: number;
    adjustmentId: number;
    provider?: string;
    settlementTransId: string;
    settlementNote?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantDepositAdjustment }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/${params.adjustmentId}/settlement`,
      {
        method: "POST",
        headers: merchantHeaders(),
        body: JSON.stringify({
          provider: params.provider ?? "TAPPAY",
          settlementTransId: params.settlementTransId,
          settlementNote: params.settlementNote,
        }),
      },
    ),
  requestMerchantDepositAdjustmentRefund: (params: {
    shopId: number;
    adjustmentId: number;
    settlementNote?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantDepositAdjustment }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/${params.adjustmentId}/refund/request`,
      {
        method: "POST",
        headers: merchantHeaders(),
        body: JSON.stringify({
          settlementNote: params.settlementNote,
        }),
      },
    ),
  escalateMerchantDepositAdjustmentRefund: (params: {
    shopId: number;
    adjustmentId: number;
    escalationNote?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantDepositAdjustment }>(
      `${CLIENT_JAVA_API}/api/merchant/shops/${params.shopId}/deposit-adjustments/${params.adjustmentId}/refund/escalate`,
      {
        method: "POST",
        headers: merchantHeaders(),
        body: JSON.stringify({
          escalationNote: params.escalationNote,
        }),
      },
    ),
  reconcileRefundAdjustment: (params: {
    adjustmentId: number;
    bookingCode: string;
    amount: number;
    status: "COMPLETED" | "FAILED";
    settlementTransId?: string;
    settlementNote?: string;
    eventKey?: string;
  }) =>
    fetchJson<{ success: boolean; errorMsg?: string; data: MerchantDepositAdjustment }>(
      `${CLIENT_JAVA_API}/api/payment/tappay/deposit-adjustments/${params.adjustmentId}/refund/reconcile`,
      {
        method: "POST",
        headers: merchantHeaders(),
        body: JSON.stringify({
          bookingCode: params.bookingCode,
          amount: params.amount,
          status: params.status,
          settlementTransId: params.settlementTransId,
          settlementNote: params.settlementNote,
          eventKey: params.eventKey,
        }),
      },
    ),
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
