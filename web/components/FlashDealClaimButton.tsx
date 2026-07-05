"use client";

import Link from "next/link";
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
        if (result.errorMsg?.includes("不能重複下單")) {
          setMessage("已搶過餐券，本次不會重複扣庫存");
          return;
        }
        setError(result.errorMsg ?? "餐券搶購失敗，請稍後再試");
        return;
      }
      // 訂單由 MQ 非同步落庫，稍後才會出現在「我的餐券」
      setMessage("已搶到餐券，訂單建立中");
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
          {" · "}
          <Link href="/my-vouchers" className="font-medium underline underline-offset-2 hover:text-emerald-700">
            到「我的餐券」查看
          </Link>
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
