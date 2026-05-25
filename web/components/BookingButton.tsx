"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

declare global {
  interface Window { TPDirect: any }
}

const JAVA_API = process.env.NEXT_PUBLIC_JAVA_API || "http://localhost:8081";

// Module-level flag：存活於 React StrictMode unmount/remount 之外。
// StrictMode dev 模式強制 unmount+remount，useRef 每次 remount 歸零，
// module-level 變數不受影響，保證 card.setup 只跑一次。
let _tappayCardSetupDone = false;

type Step = "idle" | "select-pay" | "card-input" | "processing" | "done";

const TAIWAN_PAY = [
  { code: 1, label: "信用卡", emoji: "💳", real: true },
  { code: 2, label: "Line Pay", emoji: "📱", real: false },
  { code: 3, label: "Apple Pay", emoji: "🍎", real: false },
  { code: 4, label: "街口支付", emoji: "🟢", real: false },
];

export function BookingButton({ shopName }: { shopName: string }) {
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [sdkReady, setSdkReady] = useState(false);

  // Init TapPay SDK
  useEffect(() => {
    const tryInit = () => {
      if (typeof window !== "undefined" && window.TPDirect) {
        window.TPDirect.setupSDK(
          parseInt(process.env.NEXT_PUBLIC_TAPPAY_APP_ID!),
          process.env.NEXT_PUBLIC_TAPPAY_APP_KEY!,
          process.env.NEXT_PUBLIC_TAPPAY_ENV || "sandbox"
        );
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

  // Setup card fields when entering card-input
  // 用 module-level _tappayCardSetupDone 防止 React 18 StrictMode unmount/remount 導致雙次 setup
  // （useRef 在 StrictMode remount 後重置為 false；module-level 不受影響）
  useEffect(() => {
    if (step !== "card-input" || !sdkReady) return;

    const tryMount = () => {
      // 雙重防護：module-level flag + DOM iframe 存在性檢查
      if (_tappayCardSetupDone) return true;
      const n = document.getElementById("tappay-number");
      const e = document.getElementById("tappay-expiry");
      const c = document.getElementById("tappay-ccv");
      if (!n || !e || !c) return false;
      // 如果 iframe 已存在（第二次 setup 防護）
      if (n.querySelector("iframe")) {
        _tappayCardSetupDone = true;
        return true;
      }

      try {
        window.TPDirect.card.setup({
          fields: {
            number: { element: "#tappay-number", placeholder: "4242 4242 4242 4242" },
            expirationDate: { element: "#tappay-expiry", placeholder: "MM / YY" },
            ccv: { element: "#tappay-ccv", placeholder: "CCV" }
          },
          styles: {
            input: { "font-size": "14px", "color": "#000" },
            ":focus": { "color": "#000" },
            ".invalid": { "color": "#dc2626" }
          }
        });
        _tappayCardSetupDone = true;
        console.log("[TapPay] card setup done");
        return true;
      } catch (err) {
        console.error("[TapPay] setup error", err);
        return false;
      }
    };

    if (!tryMount()) {
      const interval = setInterval(() => {
        if (tryMount()) clearInterval(interval);
      }, 100);
      return () => clearInterval(interval);
    }
  }, [step, sdkReady]);

  const handleCardSubmit = () => {
    setError("");
    const status = window.TPDirect.card.getTappayFieldsStatus();
    if (!status.canGetPrime) {
      setError("請完整填寫卡號資料");
      return;
    }
    // ⚠ 不能在 getPrime 之前 setStep("processing")：
    // TapPay iframe 是 overlay 方式，card-input div unmount 後 getPrime 讀不到值
    // 必須等 getPrime callback 拿到 prime 後才能切 step
    window.TPDirect.card.getPrime((r: any) => {
      if (r.status !== 0) {
        setError("Prime 失敗: " + r.msg);
        return; // 留在 card-input，不切 step
      }
      setStep("processing"); // prime 到手後才切，避免 DOM unmount
      // HTTPS dev 環境下用 /api/java proxy（Next.js rewrite → Java 8081）
      // 使用 relative URL，瀏覽器自動帶上 origin，無 mixed content
      fetch("/api/java/api/payment/tappay/pay-by-prime", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prime: r.card.prime,
          orderId: Math.floor(Math.random() * 100000),
          amount: 1280
        })
      })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setResult({ ...data.data, payLabel: "信用卡" });
          setStep("done");
        } else {
          setError(data.errorMsg || "支付失敗");
          _tappayCardSetupDone = false; // 重置讓欄位重新 mount + setup
          setStep("card-input");
        }
      })
      .catch(e => {
        setError("網路錯誤: " + e.message);
        _tappayCardSetupDone = false; // 重置讓欄位重新 mount + setup
        setStep("card-input");
      });
    });
  };

  const handleDemoPay = (code: number, label: string) => {
    setResult({
      rec_trade_id: "DEMO-" + Math.random().toString(36).slice(2, 10).toUpperCase(),
      payLabel: label,
      note: "demo 不串、production 才接 TapPay"
    });
    setStep("done");
  };

  const reset = () => {
    _tappayCardSetupDone = false; // 重置，讓下次開啟可以重新 setup
    setStep("idle");
    setResult(null);
    setError("");
  };

  if (step === "idle") {
    return <Button size="lg" onClick={() => setStep("select-pay")}>立即訂位</Button>;
  }

  return (
    <div className="absolute right-4 bottom-16 bg-background border rounded-xl shadow-lg p-4 w-80 z-50">
      {step === "select-pay" && (
        <>
          <p className="text-sm font-medium mb-3">選擇支付方式</p>
          <div className="space-y-2">
            {TAIWAN_PAY.map(p => (
              <button
                key={p.code}
                onClick={() => p.real ? setStep("card-input") : handleDemoPay(p.code, p.label)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-muted text-sm flex items-center justify-between"
              >
                <span>{p.emoji} {p.label}</span>
                <span className={`text-xs ${p.real ? "text-primary font-semibold" : "text-muted-foreground"}`}>
                  {p.real ? "真實串接" : "demo"}
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {step === "card-input" && (
        <>
          <p className="text-sm font-medium mb-1">TapPay Sandbox 信用卡</p>
          <p className="text-xs text-muted-foreground mb-3">測試卡 4242 4242 4242 4242 / 任意未來日期 / CCV 123</p>
          <div id="tappay-number" className="border rounded px-3 py-2 mb-2" style={{ height: 40 }} />
          <div className="flex gap-2 mb-3">
            <div id="tappay-expiry" className="border rounded px-3 py-2 flex-1" style={{ height: 40 }} />
            <div id="tappay-ccv" className="border rounded px-3 py-2 w-24" style={{ height: 40 }} />
          </div>
          {error && <p className="text-xs text-red-500 mb-2">{error}</p>}
          <Button onClick={handleCardSubmit} className="w-full">確認支付 NT$ 1,280</Button>
        </>
      )}

      {step === "processing" && <p className="text-sm">處理中...</p>}

      {step === "done" && (
        <>
          <p className="text-sm font-medium text-primary mb-2">✓ {result?.note ? "示意完成" : "支付成功"}</p>
          <p className="text-xs text-muted-foreground">支付方式</p>
          <p className="text-sm mb-2">{result?.payLabel}</p>
          <p className="text-xs text-muted-foreground">交易編號</p>
          <p className="font-mono text-xs mb-2">{result?.rec_trade_id}</p>
          {result?.note && <p className="text-xs text-muted-foreground italic">{result.note}</p>}
        </>
      )}

      <button onClick={reset} className="w-full text-xs text-muted-foreground mt-3">
        關閉
      </button>
    </div>
  );
}
