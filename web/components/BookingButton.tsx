"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

declare global {
  interface Window { TPDirect: any }
}

const JAVA_API = "/api/java";

type Step = "idle" | "form" | "select-pay" | "card-input" | "processing" | "done";

interface BookingPolicy {
  needsDeposit: boolean;
  depositPerPerson: number;
  reason: string;
}

const TAIWAN_PAY = [
  { code: 1, label: "信用卡", status: "TapPay sandbox", real: true },
  { code: 2, label: "LINE Pay", status: "demo", real: false },
  { code: 3, label: "Apple Pay", status: "demo", real: false },
  { code: 4, label: "街口支付", status: "demo", real: false },
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
  { label: "一般", value: "normal" },
  { label: "吧台", value: "bar" },
  { label: "包廂", value: "private" },
];

function bookingHeaders(): HeadersInit {
  const token = typeof window !== "undefined"
    ? window.localStorage.getItem("bytebites_token")
    : null;
  return token
    ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
    : { "Content-Type": "application/json", "X-Demo-Mode": "true" };
}

function next14Days() {
  const days = [];
  const now = new Date();
  for (let i = 1; i <= 14; i++) {   // 從明天起，不含今天
    const d = new Date(now);
    d.setDate(now.getDate() + i);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const wd = ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
    days.push({
      value: `${yyyy}-${mm}-${dd}`,
      label: i === 1 ? `明天 ${mm}/${dd}(${wd})` : `${mm}/${dd}(${wd})`,
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
  const [policy, setPolicy] = useState<BookingPolicy | null>(null);
  const [bookingCode, setBookingCode] = useState<string | null>(null);

  // 訂位 form state
  const [people, setPeople] = useState(2);
  const [date, setDate] = useState(next14Days()[0].value);
  const [time, setTime] = useState("18:30");
  const [tableType, setTableType] = useState("normal");

  const depositTotal = policy?.needsDeposit
    ? policy.depositPerPerson * people
    : 0;

  // 開啟 form 時查訂金政策（只查一次）
  useEffect(() => {
    if (step !== "form" || policy !== null) return;
    fetch(`${JAVA_API}/api/shop/${shop.id}/booking-policy`)
      .then((r) => r.json())
      .then((d) => { if (d.success) setPolicy(d.data); })
      .catch(() => {
        // 查詢失敗 → 預設免訂金，不擋主流程
        setPolicy({ needsDeposit: false, depositPerPerson: 0, reason: "免訂金" });
      });
  }, [step, shop.id, policy]);

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

  // Setup TapPay card fields when entering card-input
  useEffect(() => {
    if (step !== "card-input" || !sdkReady) return;
    const tryMount = () => {
      if (!document.getElementById("tappay-number")) return false;
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

  // 免訂金流程：直接呼叫 /api/booking/reserve
  const handleNoDepositConfirm = () => {
    setStep("processing");
    fetch(`${JAVA_API}/api/booking/reserve`, {
      method: "POST",
      headers: bookingHeaders(),
      body: JSON.stringify({ shopId: shop.id, people, date, time, tableType }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          setResult({ bookingCode: data.data.bookingCode, payLabel: "免訂金訂位" });
          setStep("done");
        } else {
          setError(data.errorMsg || "訂位失敗");
          setStep("form");
        }
      })
      .catch((e) => {
        setError("網路錯誤: " + e.message);
        setStep("form");
      });
  };

  // 有訂金流程第一步：先建訂位 DB 記錄，再進 select-pay
  const handleProceedToPay = async () => {
    setError("");
    try {
      const res = await fetch(`${JAVA_API}/api/booking/reserve`, {
        method: "POST",
        headers: bookingHeaders(),
        body: JSON.stringify({ shopId: shop.id, people, date, time, tableType }),
      });
      const data = await res.json();
      if (data.success) {
        setBookingCode(data.data.bookingCode);
        setStep("select-pay");
      } else {
        setError(data.errorMsg || "建立訂位失敗");
      }
    } catch (e: any) {
      setError("網路錯誤: " + e.message);
    }
  };

  // 有訂金流程：TapPay credit card
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
      fetch(`${JAVA_API}/api/payment/tappay/pay-by-prime`, {
        method: "POST",
        headers: bookingHeaders(),
        body: JSON.stringify({
          prime: r.card.prime,
          orderId: Math.floor(Math.random() * 100000),
          amount: depositTotal,
          bookingCode,           // 回寫 rec_trade_id 到訂位記錄
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            setResult({ ...data.data, payLabel: "信用卡訂金", depositPaid: true });
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

  // Demo 支付（LINE Pay / Apple Pay / 街口）：仍回寫後端 booking 狀態，避免 UI 與 DB 不一致。
  const handleDemoPay = async (label: string) => {
    if (!bookingCode) {
      setError("缺少訂位編號，請重新建立訂位");
      return;
    }
    setError("");
    setStep("processing");
    try {
      const res = await fetch(`${JAVA_API}/api/booking/pay-test`, {
        method: "POST",
        headers: bookingHeaders(),
        body: JSON.stringify({ bookingCode }),
      });
      const data = await res.json();
      if (data.success) {
        setResult({
          bookingCode,
          rec_trade_id: data.data.rec_trade_id,
          payLabel: `${label} 訂金`,
          depositPaid: true,
          note: `${label} demo 付款，已回寫訂位狀態；production 需接第三方授權。`,
        });
        setStep("done");
      } else {
        setError(data.errorMsg || "支付失敗");
        setStep("select-pay");
      }
    } catch (e: any) {
      setError("網路錯誤: " + e.message);
      setStep("select-pay");
    }
  };

  const reset = () => {
    setStep("idle");
    setResult(null);
    setError("");
    setPolicy(null);
    setBookingCode(null);
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

          {/* 人數 stepper */}
          <div className="mb-4">
            <label className="text-xs text-muted-foreground">人數</label>
            <div className="flex items-center gap-3 mt-1">
              <button
                onClick={() => setPeople(Math.max(1, people - 1))}
                className="w-9 h-9 rounded-full border flex items-center justify-center hover:bg-muted text-lg"
              >
                −
              </button>
              <div className="flex-1 text-center text-lg font-medium">{people} 人</div>
              <button
                onClick={() => setPeople(Math.min(12, people + 1))}
                className="w-9 h-9 rounded-full border flex items-center justify-center hover:bg-muted text-lg"
              >
                +
              </button>
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
                <option key={d.value} value={d.value}>{d.label}</option>
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
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          {/* 座位偏好 */}
          <div className="mb-4">
            <label className="text-xs text-muted-foreground">座位偏好</label>
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

          {/* 訂金 / 免訂金 banner */}
          {policy ? (
            <div
              className={`rounded p-3 mb-4 ${
                policy.needsDeposit
                  ? "bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800"
                  : "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800"
              }`}
            >
              {policy.needsDeposit ? (
                <>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1">
                    <span>{policy.reason}</span>
                    <span>NT${policy.depositPerPerson} × {people} 人</span>
                  </div>
                  <div className="flex justify-between items-baseline">
                    <span className="text-sm font-medium">訂金</span>
                    <span className="text-2xl font-bold">
                      NT$ {depositTotal.toLocaleString()}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    用餐當日全額折抵消費
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-green-700 dark:text-green-400">
                    ✓ 此餐廳免訂金
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {policy.reason}，確認即完成訂位
                  </p>
                </>
              )}
            </div>
          ) : (
            <div className="rounded p-3 mb-4 bg-muted/30 text-xs text-muted-foreground animate-pulse">
              載入訂金政策中...
            </div>
          )}

          {error && <p className="text-xs text-red-500 mb-2">{error}</p>}

          {policy?.needsDeposit ? (
            <Button onClick={handleProceedToPay} className="w-full">
              下一步 · 選擇支付
            </Button>
          ) : (
            <Button
              onClick={handleNoDepositConfirm}
              className="w-full"
              disabled={!policy}
            >
              {policy ? "確認訂位" : "載入中..."}
            </Button>
          )}
        </>
      )}

      {/* ── Step: select-pay（有訂金） ── */}
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
            {shop.name} · {date} {time} · {people} 人
          </p>
          <p className="text-lg font-bold text-primary mb-4">
            訂金 NT$ {depositTotal.toLocaleString()}
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
                <span className="font-medium">{p.label}</span>
                <span
                  className={`text-xs ${
                    p.real ? "text-primary font-semibold" : "text-muted-foreground"
                  }`}
                >
                  {p.status}
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
            支付訂金 NT$ {depositTotal.toLocaleString()}
          </Button>
        </>
      )}

      {/* ── Step: processing ── */}
      {step === "processing" && (
        <div className="text-center py-6">
          <p className="text-sm">處理中...</p>
          <p className="text-xs text-muted-foreground mt-2">請稍候</p>
        </div>
      )}

      {/* ── Step: done ── */}
      {step === "done" && (
        <>
          <p className="text-base font-medium text-primary mb-3">
            ✓ {result?.depositPaid ? "訂位 + 訂金完成" : "訂位完成"}
          </p>

          <div className="bg-muted/30 rounded p-3 mb-3 text-sm space-y-1.5">
            <div className="flex justify-between">
              <span className="text-muted-foreground">餐廳</span>
              <span>{shop.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">日期</span>
              <span>{date} {time}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">人數</span>
              <span>{people} 人</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">座位</span>
              <span>{TABLE_TYPES.find((t) => t.value === tableType)?.label}</span>
            </div>
            {result?.depositPaid && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">訂金</span>
                <span className="font-bold">NT$ {depositTotal.toLocaleString()}</span>
              </div>
            )}
          </div>

          <div className="text-xs space-y-1">
            <p className="text-muted-foreground">
              {result?.depositPaid ? "支付方式" : "訂位類型"}：
              <span className="text-foreground">{result?.payLabel}</span>
            </p>
            {result?.depositPaid && result?.rec_trade_id && (
              <>
                <p className="text-muted-foreground">交易編號：</p>
                <p className="font-mono break-all">{result.rec_trade_id}</p>
              </>
            )}
            {(result?.bookingCode || bookingCode) && (
              <>
                <p className="text-muted-foreground">訂位編號：</p>
                <p className="font-mono break-all">{result?.bookingCode ?? bookingCode}</p>
              </>
            )}
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
