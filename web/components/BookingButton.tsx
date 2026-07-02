"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { javaApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatHoldCountdown } from "@/lib/myBookings";

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

function bookingHeaders(): HeadersInit | null {
  const token = typeof window !== "undefined"
    ? window.localStorage.getItem("bytebites_token")
    : null;
  return token ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` } : null;
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
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [step, setStep] = useState<Step>("idle");
  const [sdkReady, setSdkReady] = useState(false);
  const [error, setError] = useState("");
  const [soldOutSlot, setSoldOutSlot] = useState(false);
  const [watchMessage, setWatchMessage] = useState("");
  const [result, setResult] = useState<any>(null);
  const [policy, setPolicy] = useState<BookingPolicy | null>(null);
  const [bookingCode, setBookingCode] = useState<string | null>(null);
  const [holdExpiresAt, setHoldExpiresAt] = useState<string | null>(null);
  const [allowDemoFallback, setAllowDemoFallback] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  // 訂位 form state
  const [people, setPeople] = useState(2);
  const [date, setDate] = useState(next14Days()[0].value);
  const [time, setTime] = useState("18:30");
  const [tableType, setTableType] = useState("normal");

  const depositTotal = policy?.needsDeposit
    ? policy.depositPerPerson * people
    : 0;
  const holdExpired = Boolean(
    holdExpiresAt && new Date(holdExpiresAt).getTime() <= nowMs,
  );
  const loginRequired = mounted && !isAuthLoading && !isLoggedIn;

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

  useEffect(() => {
    if (step !== "select-pay" || !holdExpiresAt) return;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [holdExpiresAt, step]);

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
    const headers = bookingHeaders();
    if (!headers) {
      setError("請先用 LINE 登入，再建立訂位。");
      return;
    }
    setStep("processing");
    setSoldOutSlot(false);
    setWatchMessage("");
    fetch(`${JAVA_API}/api/booking/reserve`, {
      method: "POST",
      headers,
      body: JSON.stringify({ shopId: shop.id, people, date, time, tableType }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          setResult({ bookingCode: data.data.bookingCode, payLabel: "免訂金訂位" });
          setStep("done");
        } else {
          setError(data.errorMsg || "訂位失敗");
          setSoldOutSlot(Boolean((data.errorMsg || "").includes("額滿")));
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
    setSoldOutSlot(false);
    setWatchMessage("");
    const headers = bookingHeaders();
    if (!headers) {
      setError("請先用 LINE 登入，再保留座位。");
      return;
    }
    if (bookingCode) {
      setStep("select-pay");
      return;
    }
    try {
      const res = await fetch(`${JAVA_API}/api/booking/reserve`, {
        method: "POST",
        headers,
        body: JSON.stringify({ shopId: shop.id, people, date, time, tableType }),
      });
      const data = await res.json();
      if (data.success) {
        setBookingCode(data.data.bookingCode);
        setHoldExpiresAt(data.data.holdExpiresAt ?? null);
        setNowMs(Date.now());
        setStep("select-pay");
      } else {
        setError(data.errorMsg || "建立訂位失敗");
        setSoldOutSlot(Boolean((data.errorMsg || "").includes("額滿")));
      }
    } catch (e: any) {
      setError("網路錯誤: " + e.message);
    }
  };

  const handleCreateAvailabilityWatch = async () => {
    setError("");
    setWatchMessage("");
    if (!bookingHeaders()) {
      setError("請先用 LINE 登入，再設定空位通知。");
      return;
    }
    try {
      const response = await javaApi.createAvailabilityWatch({
        shopId: shop.id,
        date,
        time,
        tableType,
        people,
      });
      if (!response.success) {
        setError(response.errorMsg ?? "建立空位通知失敗");
        return;
      }
      setSoldOutSlot(false);
      setWatchMessage("已設定空位通知。若此時段釋出足夠座位，會出現在通知中心。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立空位通知失敗");
    }
  };

  // 有訂金流程：TapPay credit card
  const handleCardSubmit = () => {
    setError("");
    setAllowDemoFallback(false);
    const headers = bookingHeaders();
    if (!headers) {
      setError("請先用 LINE 登入，再完成付款。");
      return;
    }
    if (holdExpired) {
      setError("此保留已逾期，請重新建立訂位");
      return;
    }
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
        headers,
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
            setAllowDemoFallback(false);
            setStep("done");
          } else {
            setError(data.errorMsg || "支付失敗");
            setAllowDemoFallback(Boolean(data.errorMsg?.includes("TapPay sandbox IP")));
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
    setAllowDemoFallback(false);
    if (holdExpired) {
      setError("此保留已逾期，請重新建立訂位");
      return;
    }
    setStep("processing");
    try {
      const headers = bookingHeaders();
      if (!headers) {
        setError("請先用 LINE 登入，再完成付款。");
        setStep("select-pay");
        return;
      }
      const res = await fetch(`${JAVA_API}/api/booking/pay-test`, {
        method: "POST",
        headers,
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
    setHoldExpiresAt(null);
    setAllowDemoFallback(false);
    setSoldOutSlot(false);
    setWatchMessage("");
  };

  if (step === "idle") {
    return (
      <Button
        size="lg"
        onClick={() => {
          if (mounted && isAuthLoading) return;
          if (loginRequired) {
            setError("");
            setStep("form");
            return;
          }
          setStep("form");
        }}
        className="flex-1 sm:flex-none"
      >
        {loginRequired ? "登入後訂位" : "立即訂位"}
      </Button>
    );
  }

  return (
    <div className="fixed inset-x-3 bottom-3 z-50 max-h-[88dvh] overflow-y-auto rounded-2xl border bg-background p-5 shadow-2xl md:absolute md:inset-auto md:bottom-16 md:right-4 md:w-96 md:max-h-[80vh]">

      {/* ── Step: form ── */}
      {step === "form" && (
        <>
          <p className="text-base font-medium mb-1">訂位資訊</p>
          <p className="text-xs text-muted-foreground mb-4">{shop.name}</p>

          {loginRequired ? (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-950">
              <p className="font-semibold">登入後即可訂位</p>
              <p className="mt-1 text-xs leading-5 text-amber-800">
                你可以先查看完整餐廳資料；建立訂位、付款、取消與 LINE 通知需要登入。
              </p>
              <button
                type="button"
                onClick={login}
                className="mt-3 w-full rounded-md bg-emerald-700 px-3 py-2 text-sm font-bold text-white hover:bg-emerald-800"
              >
                用 LINE 登入並繼續訂位
              </button>
            </div>
          ) : null}

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
                  <p className="text-xs text-amber-700 dark:text-amber-300 mt-2">
                    下一步會先保留座位並產生訂位編號；完成付款後訂位才算完成。
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
          {soldOutSlot ? (
            <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <p className="font-semibold">此時段目前額滿。</p>
              <p className="mt-1 leading-5">可先設定空位通知；有人取消或店家釋出容量時，系統會通知你回來訂位。</p>
              <button
                type="button"
                onClick={handleCreateAvailabilityWatch}
                className="mt-2 w-full rounded-md bg-amber-700 px-3 py-2 font-semibold text-white hover:bg-amber-800"
              >
                通知我有空位
              </button>
            </div>
          ) : null}
          {watchMessage ? (
            <div className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">
              {watchMessage}
            </div>
          ) : null}

          {policy?.needsDeposit ? (
            <Button onClick={handleProceedToPay} className="w-full" disabled={isAuthLoading || (mounted && !isLoggedIn)}>
              保留座位並前往付款
            </Button>
          ) : (
            <Button
              onClick={handleNoDepositConfirm}
              className="w-full"
              disabled={!policy || isAuthLoading || (mounted && !isLoggedIn)}
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
            ← 返回修改（已保留訂位不會自動取消）
          </button>
          <p className="text-sm font-medium mb-1">確認訂位</p>
          <p className="text-xs text-muted-foreground mb-3">
            {shop.name} · {date} {time} · {people} 人
          </p>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 mb-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-amber-950">
                  已為你保留座位
                </p>
                <p className="text-xs text-amber-800 mt-1">
                  尚未付款，完成訂金支付後訂位才成立。
                </p>
              </div>
              <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-amber-800">
                {holdExpired ? "已逾期" : `剩餘 ${formatHoldCountdown(holdExpiresAt, nowMs) ?? "10:00"}`}
              </span>
            </div>
            {bookingCode ? (
              <p className="font-mono text-xs text-amber-900 mt-3 break-all">
                訂位編號：{bookingCode}
              </p>
            ) : null}
            {holdExpired ? (
              <p className="text-xs font-semibold text-red-700 mt-3">
                此保留已逾期，座位容量將釋放；請關閉後重新建立訂位。
              </p>
            ) : null}
          </div>
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
                disabled={holdExpired}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-muted text-sm flex items-center justify-between border disabled:cursor-not-allowed disabled:opacity-50"
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
          <div className="grid gap-2 mb-3 sm:grid-cols-[1fr_96px]">
            <div
              id="tappay-expiry"
              className="border rounded px-3 py-2"
              style={{ height: 40 }}
            />
            <div
              id="tappay-ccv"
              className="border rounded px-3 py-2"
              style={{ height: 40 }}
            />
          </div>
          {error && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              <p className="font-semibold">{error}</p>
              {allowDemoFallback ? (
                <div className="mt-2 rounded-md border border-red-200 bg-white/75 p-2 leading-5">
                  <p>
                    TapPay iframe 已取得 prime；目前卡在 sandbox 商家後台 IP 白名單設定。
                  </p>
                  <p className="mt-1">
                    本地展示可使用 demo 授權完成付款狀態；正式上線必須完成 TapPay 後台設定。
                  </p>
                  <button
                    type="button"
                    onClick={() => handleDemoPay("信用卡 Demo")}
                    className="mt-2 w-full rounded-md bg-red-700 px-3 py-2 font-semibold text-white hover:bg-red-800"
                  >
                    使用 demo 授權完成付款狀態
                  </button>
                </div>
              ) : null}
            </div>
          )}
          <Button onClick={handleCardSubmit} className="w-full" disabled={holdExpired}>
            {holdExpired ? "保留已逾期" : `支付訂金 NT$ ${depositTotal.toLocaleString()}`}
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
