import type { AgentShop } from "./agentTypes";
import type { AgentStreamEvent, AgentTransaction } from "@/lib/agentStream";

type AgentDecisionPayload = {
  recommended_shop_ids?: number[];
};

type AgentToolResult = {
  shops?: AgentShop[];
  scope_note?: string | null;
  transaction?: AgentTransaction | null;
  agent_decision?: AgentDecisionPayload;
};

export type AgentFinalPayload = {
  shops?: AgentShop[];
  recommendedShopIds?: number[];
  transaction?: AgentTransaction;
  scopeNote?: string;
};

export function shopId(shop: AgentShop): number {
  return Number(shop.shop_id ?? (shop as unknown as { id?: number | string }).id);
}

export function normalizeAgentShop(shop: AgentShop): AgentShop | null {
  const id = shopId(shop);
  if (!Number.isFinite(id)) return null;
  const raw = shop as unknown as {
    avgPrice?: number | null;
    mrtStation?: string | null;
  };
  return {
    ...shop,
    shop_id: id,
    mrt_station: shop.mrt_station ?? raw.mrtStation ?? null,
    avg_price: shop.avg_price ?? raw.avgPrice ?? null,
    price_per_person:
      shop.price_per_person ??
      (raw.avgPrice != null ? `NT$ ${raw.avgPrice}` : null),
  };
}

export function selectRecommendedShops(
  shops: AgentShop[] | undefined,
  recommendedShopIds: number[] | undefined,
): AgentShop[] | undefined {
  const normalized = shops
    ?.map(normalizeAgentShop)
    .filter((shop): shop is AgentShop => Boolean(shop));
  if (!normalized || normalized.length === 0) return undefined;
  if (!recommendedShopIds?.length) return normalized.slice(0, 3);
  const byId = new Map(normalized.map((shop) => [shopId(shop), shop]));
  const selected = recommendedShopIds
    .map((id) => byId.get(Number(id)))
    .filter((shop): shop is AgentShop => Boolean(shop));
  if (selected.length === 0) return normalized.slice(0, 3);
  const selectedIds = new Set(selected.map(shopId));
  const filled = [
    ...selected,
    ...normalized.filter((shop) => !selectedIds.has(shopId(shop))),
  ];
  return filled.slice(0, Math.min(3, normalized.length));
}

function toolResultFromEvent(event: AgentStreamEvent): AgentToolResult | undefined {
  if (!("tool_result" in event) || !event.tool_result || typeof event.tool_result !== "object") {
    return undefined;
  }
  return event.tool_result as AgentToolResult;
}

export function agentFinalPayloadFromEvent(event: AgentStreamEvent): AgentFinalPayload {
  const toolResult = toolResultFromEvent(event);
  const recommendedShopIds =
    ("recommended_shop_ids" in event ? event.recommended_shop_ids : undefined) ??
    toolResult?.agent_decision?.recommended_shop_ids;
  const shops = selectRecommendedShops(toolResult?.shops, recommendedShopIds);
  const transaction =
    ("transaction" in event ? event.transaction ?? undefined : undefined) ??
    toolResult?.transaction ??
    undefined;
  const scopeNote =
    ("scope_note" in event ? event.scope_note ?? undefined : undefined) ??
    toolResult?.scope_note ??
    undefined;

  return {
    shops,
    recommendedShopIds,
    transaction,
    scopeNote,
  };
}
