"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

declare global {
  interface Window { TPDirect: any }
}

type Step = "idle" | "form" | "select-pay" | "card-input" | "processing" | "done";

const TAIWAN_PAY = [
  { code: 1, label: "信用卡", emoji: "💳", real: true },
  { code: 2, label: "Line Pay", emoji: "📱", real: false },
  { code: 3, label: "Apple Pay", emoji: "🍎", real: false },
  { code: 4, label: "街口支付", emoji: "🟢", real: false },
];

const TIME_SLOTS = [
  { label: "午餐 11:30", value: "11:30" },
  { label: "午餐 12:00", value: "12:00" },
  { label: "午餐 12:30", value: "12:30" },
  { label: "午餐 13:00", value: "13:00" },
  { label: "晚餐 17:30", value: "17:30" },
  { label: "晚餐 18:00", value: "18:00" },
  { label: "晚餐 18:30", value: "18:30" },
  { label: "晚餐 19:00", value: "19:00" },
  { label: "晚餐 19:30", value: "19:30" },
  { label: "晚餐 20:00", value: "20:00" },
];

const TABLE_TYPES = [
  { label: "一般座位", value: "normal", multiplier: 1.0 },
  { label: "吧台座位", value: "bar", multiplier: 0.9 },
  { label: "包廂", value: "private", multiplier: 1.2 },
];

function next14Days() {
  const days = [];
  const now = new Date();
  for (let i = 0; i < 14; i++) {
    const d = new Date(now);
    d.setDate(now.getDate() + i);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const wd = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
    days.push({
      value: `${yyyy}-${mm}-${dd}`,
      label: i === 0 ? "今天" : i === 1 ? "明天" : `${mm}/${dd}(${wd})`,
    });
  }
  return days;
}

export function BookingButton({
  shop,
}: {
  shop: { id: number; name: string; avgPrice?: number | null };
}) {
  const [step, setStep] = useState<Step>("idle");
  const [sdkReady, setSdkReady] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);

  // 訂位 form state
  const [people, setPeople] = useState(2);
  const [date, setDate] = useState(next14Days()[0].value);
  const [time, setTime] = useState("18:30");
  const [tableType, setTableType] = useState("normal");

  const basePrice = shop.avgPrice || 1280;
  const multiplier = TABLE_TYPES.find((t) => t.value === tableType)?.multiplier ?? 1;
  const totalAmount = Math.round(basePrice * people * multiplier);

  // Init TapPay SDK
  useEffect(() => {
    const tryInit = () => {
      if (typeof window !== "undefined" && window.TPDirect) {
        try {
          window.TPDirect.setupSDK(
            parseInt(process.env.NEXT_PUBLIC_TAPPAY_APP_ID!),
            process.env.NEXT_PUBLIC_TAPPAY_APP_KEY!,
            process.env.NEXT_PUBLIC_TAPPAY_ENV || "sandbox"
          );
        } catch {}
        setSdkReady(true);
        return true;
      }
      return false;
    };
    if (!tryInit()) {
      const t = setInterval(() => { if (tryInit()) clearInterval(t); }, 200);
      return () => clearInterval(t);
    }
  }, []);

  // Setup card fields when entering card-input step
  useEffect(() => {
    if (step !== "card-input" || !sdkReady) return;
    const tryMount = () => {
      const n = document.getElementById("tappay-number");
      const e = document.getElementById("tappay-expiry");
      const c = document.getElementById("tappay-ccv");
      if (!n || !e || !c) return false;
      try {
        window.TPDirect.card.setup({
          fields: {
            number: { element: "#tappay-number", placeholder: "4242 4242 4242 4242" },
            expirationDate: { element: "#tappay-expiry", placeholder: "MM / YY" },
            ccv: { element: "#tappay-ccv", placeholder: "CCV" },
          },
          styles: {
            input: { "font-size": "14px", color: "#000" },
            ":focus": { color: "#000" },
            ".invalid": { color: "#dc2626" },
          },
        });
        return true;
      } catch {
        return false;
      }
    };
    if (!tryMount()) {
      const t = setInterval(() => { if (tryMount()) clearInterval(t); }, 100);
      return () => clearInterval(t);
    }
  }, [step, sdkReady]);

  const handleCardSubmit = () => {
    setError("");
    const status = window.TPDirect.card.getTappayFieldsStatus();
    if (!status.canGetPrime) {
      setError("請完整填寫卡號資料");
      return;
    }
    // ⚠ 必須等 getPrime callback 拿到 prime 後才能切 step
    // TapPay iframe 是 overlay，card-input 若先 unmount，getPrime 讀不到值
    window.TPDirect.card.getPrime((r: any) => {
      if (r.status !== 0) {
        setError("Prime 失敗: " + r.msg);
        return;
      }
      setStep("processing");
      fetch("/api/java/api/payment/tappay/pay-by-prime", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prime: r.card.prime,
          orderId: Math.floor(Math.random() * 100000),
          amount: totalAmount,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            setResult({ ...data.data, payLabel: "信用卡" });
            setStep("done");
          } else {
            setError(data.errorMsg || "支付失敗");
            setStep("card-input");
          }
        })
        .catch((e) => {
          setError("網路錯誤: " + e.message);
          setStep("card-input");
        });
    });
  };

  const handleDemoPay = (label: string) => {
    setResult({
      rec_trade_id: "DEMO-" + Math.random().toString(36).slice(2, 10).toUpperCase(),
      payLabel: label,
      note: "demo 不串、production 才接 TapPay",
    });
    setStep("done");
  };

  const reset = () => {
    setStep("idle");
    setResult(null);
    setError("");
  };

  if (step === "idle") {
    return (
      <Button size="lg" onClick={() => setStep("form")}>
        立即訂位
      </Button>
    );
  }

  return (
    <div className="absolute right-4 bottom-16 bg-background border rounded-xl shadow-2xl p-5 w-96 z-50 max-h-[80vh] overflow-y-auto">
      {/* ── Step: form ── */}
      {step === "form" && (
        <>
          <p className="text-base font-medium mb-1">訂位資訊</p>
          <p className="text-xs text-muted-foreground mb-4">{shop.name}</p>

          {/* 人數 */}
          <div className="mb-3">
            <label className="text-xs text-muted-foreground">人數</label>
            <div className="flex gap-1.5 mt-1 flex-wrap">
              {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                <button
                  key={n}
                  onClick={() => setPeople(n)}
                  className={`px-3 py-1 rounded text-sm border transition-colors ${
                    people === n
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background hover:bg-muted"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          {/* 日期 */}
          <div className="mb-3">
            <label className="text-xs text-muted-foreground">日期</label>
            <select
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full mt-1 border rounded px-2 py-1.5 text-sm bg-background"
            >
              {next14Days().map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>

          {/* 時段 */}
          <div className="mb-3">
            <label className="text-xs text-muted-foreground">時段</label>
            <select
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="w-full mt-1 border rounded px-2 py-1.5 text-sm bg-background"
            >
              {TIME_SLOTS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* 桌型 */}
          <div className="mb-4">
            <label className="text-xs text-muted-foreground">桌型</label>
            <div className="flex gap-2 mt-1">
              {TABLE_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setTableType(t.value)}
                  className={`px-3 py-1.5 rounded text-xs border flex-1 transition-colors ${
                    tableType === t.value
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background hover:bg-muted"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* 金額小計 */}
          <div className="bg-muted/50 rounded p-3 mb-4">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>人均 × 人數 × 桌型</span>
              <span>
                ${basePrice} × {people} × {multiplier}
              </span>
            </div>
            <div className="flex justify-between items-baseline">
              <span className="text-sm">總金額</span>
              <span className="text-2xl font-bold text-primary">
                NT$ {totalAmount.toLocaleString()}
              </span>
            </div>
          </div>

          <Button onClick={() => setStep("select-pay")} className="w-full">
            下一步 · 選擇支付
          </Button>
        </>
      )}

      {/* ── Step: select-pay ── */}
      {step === "select-pay" && (
        <>
          <button
            onClick={() => setStep("form")}
            className="text-xs text-muted-foreground mb-3 hover:text-foreground"
          >
            ← 修改訂位
          </button>
          <p className="text-sm font-medium mb-1">確認訂位</p>
          <p className="text-xs text-muted-foreground mb-3">
            {shop.name} · {date} {time} · {people} 人 ·{" "}
            {TABLE_TYPES.find((t) => t.value === tableType)?.label}
          </p>
          <p className="text-lg font-bold text-primary mb-4">
            NT$ {totalAmount.toLocaleString()}
          </p>

          <p className="text-sm font-medium mb-2">選擇支付方式</p>
          <div className="space-y-2">
            {TAIWAN_PAY.map((p) => (
              <button
                key={p.code}
                onClick={() =>
                  p.real ? setStep("card-input") : handleDemoPay(p.label)
                }
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-muted text-sm flex items-center justify-between border"
              >
                <span>
                  {p.emoji} {p.label}
                </span>
                <span
                  className={`text-xs ${
                    p.real
                      ? "text-primary font-semibold"
                      : "text-muted-foreground"
                  }`}
                >
                  {p.real ? "真實串接" : "demo"}
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {/* ── Step: card-input ── */}
      {step === "card-input" && (
        <>
          <button
            onClick={() => setStep("select-pay")}
            className="text-xs text-muted-foreground mb-3 hover:text-foreground"
          >
            ← 換支付方式
          </button>
          <p className="text-sm font-medium mb-1">TapPay Sandbox 信用卡</p>
          <p className="text-xs text-muted-foreground mb-3">
            測試卡 4242 4242 4242 4242 / 任意未來日期 / CCV 123
          </p>
          <div
            id="tappay-number"
            className="border rounded px-3 py-2 mb-2"
            style={{ height: 40 }}
          />
          <div className="flex gap-2 mb-3">
            <div
              id="tappay-expiry"
              className="border rounded px-3 py-2 flex-1"
              style={{ height: 40 }}
            />
            <div
              id="tappay-ccv"
              className="border rounded px-3 py-2 w-24"
              style={{ height: 40 }}
            />
          </div>
          {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
          <Button onClick={handleCardSubmit} className="w-full">
            確認支付 NT$ {totalAmount.toLocaleString()}
          </Button>
        </>
      )}

      {/* ── Step: processing ── */}
      {step === "processing" && (
        <div className="text-center py-6">
          <p className="text-sm">處理中...</p>
          <p className="text-xs text-muted-foreground mt-2">正在與 TapPay 通訊</p>
        </div>
      )}

      {/* ── Step: done ── */}
      {step === "done" && (
        <>
          <p className="text-base font-medium text-primary mb-3">✓ 訂位完成</p>

          <div className="bg-muted/30 rounded p-3 mb-3 text-sm space-y-1.5">
            <div className="flex justify-between">
              <span className="text-muted-foreground">餐廳</span>
              <span>{shop.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">日期</span>
              <span>
                {date} {time}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">人數</span>
              <span>{people} 人</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">桌型</span>
              <span>{TABLE_TYPES.find((t) => t.value === tableType)?.label}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">金額</span>
              <span className="font-bold">NT$ {totalAmount.toLocaleString()}</span>
            </div>
          </div>

          <div className="text-xs space-y-1">
            <p className="text-muted-foreground">
              支付方式：<span className="text-foreground">{result?.payLabel}</span>
            </p>
            <p className="text-muted-foreground">交易編號：</p>
            <p className="font-mono break-all">{result?.rec_trade_id}</p>
            {result?.note && (
              <p className="text-muted-foreground italic mt-1">{result.note}</p>
            )}
          </div>
        </>
      )}

      {step !== "processing" && (
        <button
          onClick={reset}
          className="w-full text-xs text-muted-foreground mt-4 hover:text-foreground"
        >
          {step === "done" ? "關閉" : "取消"}
        </button>
      )}
    </div>
  );
}
