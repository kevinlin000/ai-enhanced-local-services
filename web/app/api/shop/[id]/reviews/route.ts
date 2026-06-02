import { NextRequest } from "next/server";
import { getShopReviewInsights } from "@/lib/reviewInsights";

export const runtime = "nodejs";

export async function GET(
  _: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const shopId = parseInt(id, 10);
  if (isNaN(shopId)) {
    return Response.json({ error: "invalid id" }, { status: 400 });
  }

  const insights = await getShopReviewInsights(shopId);
  if (!insights) {
    return Response.json({ error: "not found" }, { status: 404 });
  }

  return Response.json(insights);
}
