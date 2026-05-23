"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { javaApi } from "@/lib/api";

const TAIWAN_PAY = [
  { code: 1, label: "信用卡", emoji: "💳" },
  { code: 2, label: "Line Pay", emoji: "📱" },
  { code: 3, label: "Apple Pay", emoji: "🍎" },
  { code: 4, label: "街口支付", emoji: "🟢" },
];

type Step = "idle" | "select-pay" | "processing" | "done";

interface PayResult {
  status: string;
  rec_trade_id: string;
  label: string;
  amount: number;
}

export function BookingButton({ shopName }: { shopName: string }) {
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<PayResult | null>(null);

  async function handlePay(payType: number) {
    setStep("processing");
    const r = await javaApi.tappayMockCallback({
      orderId: Math.floor(Math.random() * 100000),
      payType,
      amount: 1280,
    });
    setResult(r?.data ?? null);
    setStep("done");
  }

  if (step === "idle") {
    return (
      <Button
        size="lg"
        className="bg-primary hover:bg-primary/90"
        onClick={() => setStep("select-pay")}
      >
        立即訂位
      </Button>
    );
  }

  if (step === "select-pay") {
    return (
      <div className="absolute right-4 bottom-16 bg-background border rounded-xl shadow-lg p-4 w-64 z-40">
        <p className="text-sm font-medium mb-3">選擇支付方式</p>
        <div className="space-y-2">
          {TAIWAN_PAY.map((p) => (
            <button
              key={p.code}
              onClick={() => handlePay(p.code)}
              className="w-full text-left px-3 py-2 rounded-lg hover:bg-muted text-sm flex items-center gap-2"
            >
              <span>{p.emoji}</span> {p.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setStep("idle")}
          className="w-full text-xs text-muted-foreground mt-3"
        >
          取消
        </button>
      </div>
    );
  }

  if (step === "processing") {
    return (
      <Button size="lg" disabled>
        處理中...
      </Button>
    );
  }

  return (
    <div className="absolute right-4 bottom-16 bg-background border rounded-xl shadow-lg p-4 w-72 z-40">
      <p className="text-sm font-medium text-primary mb-2">✓ 訂位成功</p>
      <p className="text-xs text-muted-foreground">交易編號</p>
      <p className="font-mono text-xs">{result?.rec_trade_id}</p>
      <p className="text-xs text-muted-foreground mt-2">支付方式</p>
      <p className="text-sm">{result?.label}</p>
      <button
        onClick={() => {
          setStep("idle");
          setResult(null);
        }}
        className="w-full text-xs text-muted-foreground mt-3"
      >
        關閉
      </button>
    </div>
  );
}
