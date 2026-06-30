"use client";

import { useState } from "react";
import { Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { javaApi } from "@/lib/api";

type Props = {
  dealId: number;
};

export function FlashDealClaimButton({ dealId }: Props) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function claim() {
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      const result = await javaApi.claimFlashDeal(dealId);
      if (!result.success) {
        setError(result.errorMsg ?? "餐券搶購失敗，請稍後再試");
        return;
      }
      const orderId = result.data?.orderId;
      setMessage(orderId ? `已搶到餐券，訂單 ${orderId} 建立中` : "已搶到餐券，訂單建立中");
    } catch (err) {
      setError(err instanceof Error ? err.message : "餐券搶購失敗，請稍後再試");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 space-y-2">
      <Button className="w-full" onClick={claim} disabled={loading}>
        <Zap className="mr-2 h-4 w-4" />
        {loading ? "搶購中..." : "立即搶餐券"}
      </Button>
      {message ? (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}
    </div>
  );
}
