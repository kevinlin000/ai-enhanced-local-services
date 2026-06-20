export type AgentPrivateAiOffer = {
  id?: number;
  shopId?: number;
  shopName?: string;
  offerCode: string;
  title: string;
  description?: string | null;
  triggerReason?: string | null;
  offerType?: string | null;
  discountPercent?: number | null;
  minPeople?: number | null;
  validUntil?: string | null;
  status?: string | null;
};

export type AgentShop = {
  shop_id: number;
  name: string;
  district?: string | null;
  mrt_station?: string | null;
  avg_price?: number | null;
  price_per_person?: string | null;
  booking_difficulty?: string | null;
  atmosphere_tags?: string[] | null;
  signature_dishes?: string[] | null;
  ai_summary?: string | null;
  hot_seat_vouchers?: { id: number; title: string }[] | null;
  private_ai_offers?: AgentPrivateAiOffer[] | null;
  private_ai_offer_reason?: string | null;
};
