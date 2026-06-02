"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { CalendarDays, CheckCircle2, Clock, Store, UsersRound } from "lucide-react";
import { javaApi, type MerchantShop, type MerchantSlot } from "@/lib/api";

function addDaysIso(days: number) {
  const value = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .formatToParts(value)
    .reduce<Record<string, string>>((acc, part) => {
      acc[part.type] = part.value;
      return acc;
    }, {});
  const year = parts.year;
  const month = parts.month;
  const day = parts.day;
  return `${year}-${month}-${day}`;
}

const MIN_BOOKING_DATE = addDaysIso(1);

function slotHealth(slot: MerchantSlot) {
  if (slot.capacity === 0) return { label: "關閉", tone: "bg-stone-100 text-stone-600" };
  if (slot.remaining === 0) return { label: "額滿", tone: "bg-red-50 text-red-700" };
  if (slot.remaining <= 2) return { label: "快滿", tone: "bg-amber-50 text-amber-700" };
  return { label: "開放", tone: "bg-emerald-50 text-emerald-700" };
}

export default function MerchantPage() {
  const [token, setToken] = useState<string | null>(null);
  const [shops, setShops] = useState<MerchantShop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null);
  const [date, setDate] = useState(MIN_BOOKING_DATE);
  const [tableType, setTableType] = useState("normal");
  const [slots, setSlots] = useState<MerchantSlot[]>([]);
  const [capacities, setCapacities] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedShop = shops.find((shop) => shop.id === selectedShopId) ?? null;
  const totals = useMemo(
    () =>
      slots.reduce(
        (acc, slot) => ({
          capacity: acc.capacity + Number(slot.capacity ?? 0),
          booked: acc.booked + Number(slot.bookedCount ?? 0),
          remaining: acc.remaining + Number(slot.remaining ?? 0),
        }),
        { capacity: 0, booked: 0, remaining: 0 },
      ),
    [slots],
  );

  useEffect(() => {
    // Merchant onboarding is not implemented yet; force demo merchant ownership.
    // This avoids a consumer LINE token accidentally calling merchant APIs as a non-merchant.
    const merchantToken = null;
    setToken(merchantToken);

    let cancelled = false;
    async function loadShops() {
      setLoading(true);
      setError(null);
      try {
        const response = await javaApi.merchantShops(merchantToken);
        if (!response.success) throw new Error("無法載入店家權限");
        if (cancelled) return;
        setShops(response.data);
        setSelectedShopId(response.data[0]?.id ?? null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "載入店家失敗");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadShops();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedShopId) return;
    const shopId = selectedShopId;

    let cancelled = false;
    async function loadSlots() {
      setLoading(true);
      setError(null);
      setMessage(null);
      try {
        const response = await javaApi.merchantSlots({
          shopId,
          date,
          tableType,
          token,
        });
        if (!response.success) throw new Error("無法載入時段");
        if (cancelled) return;
        setSlots(response.data.slots);
        setCapacities(
          Object.fromEntries(response.data.slots.map((slot) => [slot.time, Number(slot.capacity ?? 0)])),
        );
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "載入時段失敗");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSlots();
    return () => {
      cancelled = true;
    };
  }, [selectedShopId, date, tableType, token]);

  async function saveSlots() {
    if (!selectedShopId) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.updateMerchantSlots({
        shopId: selectedShopId,
        date,
        tableType,
        token,
        slots: slots.map((slot) => ({
          time: slot.time,
          capacity: Number(capacities[slot.time] ?? slot.capacity),
        })),
      });
      if (!response.success) throw new Error(response.errorMsg ?? "儲存失敗");
      setSlots(response.data.slots);
      setCapacities(
        Object.fromEntries(response.data.slots.map((slot) => [slot.time, Number(slot.capacity ?? 0)])),
      );
      setMessage("容量已更新。之後 Agent 訂位會用這份庫存判斷是否有位。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f1e8] text-stone-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-8 lg:px-8">
        <header className="overflow-hidden rounded-[32px] border border-emerald-900/10 bg-[#092d21] text-white shadow-2xl">
          <div className="grid gap-8 p-8 lg:grid-cols-[1.1fr_0.9fr] lg:p-10">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-emerald-200">
                ByteBites Merchant Console
              </p>
              <h1 className="mt-4 max-w-3xl text-4xl font-black tracking-tight lg:text-6xl">
                管理店家真實可訂容量，而不是假裝有位。
              </h1>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-emerald-50/85">
                店家在這裡設定每個時段的 capacity。使用者或 Agent 建立訂位時，後端會用交易鎖檢查
                remaining，避免超訂。
              </p>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-white/10 p-6 backdrop-blur">
              <div className="flex items-center gap-3">
                <Store className="h-6 w-6 text-emerald-200" />
                <div>
                  <p className="text-sm text-emerald-100/75">目前店家</p>
                  <p className="text-xl font-bold">{selectedShop?.name ?? "載入中"}</p>
                </div>
              </div>
              <div className="mt-6 grid grid-cols-3 gap-3">
                <Metric label="總容量" value={totals.capacity} />
                <Metric label="已訂" value={totals.booked} />
                <Metric label="剩餘" value={totals.remaining} />
              </div>
              <p className="mt-5 text-sm leading-6 text-emerald-50/75">
                Demo mode 使用 `user_id=1001` 的 merchant ownership。登入後會改用 JWT 對應的店家權限。
              </p>
            </div>
          </div>
        </header>

        <section className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <aside className="rounded-[28px] border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-black">管理範圍</h2>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
                {token ? "登入帳號" : "Demo"}
              </span>
            </div>

            <div className="mt-5 space-y-3">
              {shops.map((shop) => (
                <button
                  key={shop.id}
                  type="button"
                  onClick={() => setSelectedShopId(shop.id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    shop.id === selectedShopId
                      ? "border-emerald-600 bg-emerald-50 shadow-sm"
                      : "border-stone-200 bg-white hover:border-stone-300"
                  }`}
                >
                  <p className="font-black">{shop.name}</p>
                  <p className="mt-1 text-sm text-stone-500">{shop.district ?? "未標示行政區"}</p>
                  <p className="mt-2 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">
                    {shop.role}
                  </p>
                </button>
              ))}
              {!loading && shops.length === 0 && (
                <p className="rounded-2xl bg-stone-50 p-4 text-sm text-stone-600">
                  目前帳號沒有可管理店家。
                </p>
              )}
            </div>
          </aside>

          <section className="rounded-[28px] border border-stone-200 bg-white shadow-sm">
            <div className="flex flex-col gap-4 border-b border-stone-200 p-5 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-2xl font-black">時段容量</h2>
                <p className="mt-1 text-sm text-stone-500">
                  只修改 capacity；booked / remaining 由訂位交易自動計算。
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <label className="flex flex-col gap-1 text-sm font-semibold text-stone-600">
                  日期
                  <input
                    type="date"
                    min={MIN_BOOKING_DATE}
                    value={date}
                    onChange={(event) => setDate(event.target.value)}
                    className="h-11 rounded-xl border border-stone-200 px-3 text-stone-900"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm font-semibold text-stone-600">
                  桌型
                  <select
                    value={tableType}
                    onChange={(event) => setTableType(event.target.value)}
                    className="h-11 rounded-xl border border-stone-200 px-3 text-stone-900"
                  >
                    <option value="normal">一般座位</option>
                    <option value="bar">吧台</option>
                    <option value="private">包廂</option>
                  </select>
                </label>
              </div>
            </div>

            {error && (
              <div className="mx-5 mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                {error}
              </div>
            )}
            {message && (
              <div className="mx-5 mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                {message}
              </div>
            )}

            <div className="grid gap-3 p-5">
              {slots.map((slot) => {
                const health = slotHealth(slot);
                return (
                  <div
                    key={`${slot.tableType}-${slot.time}`}
                    className="grid gap-4 rounded-2xl border border-stone-200 bg-[#fffdf8] p-4 lg:grid-cols-[120px_1fr_160px_120px]"
                  >
                    <div className="flex items-center gap-3">
                      <Clock className="h-5 w-5 text-emerald-700" />
                      <span className="text-lg font-black">{slot.time}</span>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <MiniStat icon={<UsersRound className="h-4 w-4" />} label="容量" value={capacities[slot.time] ?? slot.capacity} />
                      <MiniStat icon={<CheckCircle2 className="h-4 w-4" />} label="已訂" value={slot.bookedCount} />
                      <MiniStat icon={<CalendarDays className="h-4 w-4" />} label="剩餘" value={slot.remaining} />
                    </div>

                    <label className="flex flex-col gap-1 text-sm font-semibold text-stone-600">
                      設定 capacity
                      <input
                        type="number"
                        min={slot.bookedCount}
                        max={80}
                        value={capacities[slot.time] ?? slot.capacity}
                        onChange={(event) =>
                          setCapacities((prev) => ({
                            ...prev,
                            [slot.time]: Number(event.target.value),
                          }))
                        }
                        className="h-11 rounded-xl border border-stone-200 px-3 text-stone-950"
                      />
                    </label>

                    <div className="flex items-center justify-start lg:justify-end">
                      <span className={`rounded-full px-4 py-2 text-sm font-black ${health.tone}`}>
                        {health.label}
                      </span>
                    </div>
                  </div>
                );
              })}
              {loading && <div className="rounded-2xl bg-stone-50 p-8 text-center text-stone-500">載入中...</div>}
            </div>

            <div className="flex flex-col gap-3 border-t border-stone-200 p-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-stone-500">
                儲存後，AI Agent 和手動訂位會共用同一份 slot inventory。
              </p>
              <div className="flex gap-3">
                <Link
                  href="/ai"
                  className="rounded-full border border-stone-300 px-5 py-3 text-sm font-bold text-stone-700 hover:bg-stone-50"
                >
                  去測 Agent 訂位
                </Link>
                <button
                  type="button"
                  onClick={saveSlots}
                  disabled={saving || !selectedShopId}
                  className="rounded-full bg-emerald-700 px-6 py-3 text-sm font-black text-white shadow-sm hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? "儲存中..." : "儲存容量"}
                </button>
              </div>
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl bg-white/10 p-4">
      <p className="text-xs font-semibold text-emerald-100/70">{label}</p>
      <p className="mt-2 text-3xl font-black">{value}</p>
    </div>
  );
}

function MiniStat({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-xl bg-white p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-stone-500">
        {icon}
        {label}
      </div>
      <p className="mt-1 text-xl font-black">{value}</p>
    </div>
  );
}
