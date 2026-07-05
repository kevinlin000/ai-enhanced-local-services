"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CalendarDays, Store, TicketPercent } from "lucide-react";
import { javaApi, type MyVoucherOrder } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// tb_voucher_order.status：1 已搶到未付款、2 已付款、3 已核銷、4 已取消、5 退款中、6 已退款
const STATUS_LABELS: Record<number, { label: string; className: string }> = {
  1: { label: "已搶到", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  2: { label: "已付款", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  3: { label: "已使用", className: "bg-zinc-100 text-zinc-500 border-zinc-200" },
  4: { label: "已取消", className: "bg-zinc-100 text-zinc-500 border-zinc-200" },
  5: { label: "退款中", className: "bg-amber-50 text-amber-700 border-amber-200" },
  6: { label: "已退款", className: "bg-zinc-100 text-zinc-500 border-zinc-200" },
};

// pay_value / actual_value 以「分」儲存
const formatCurrency = (amount?: number) =>
  amount ? `NT$ ${(amount / 100).toLocaleString()}` : "—";

const formatDateTime = (value?: string | null) => {
  if (!value) return "—";
  return value.slice(0, 16).replace("T", " ");
};

export default function MyVouchersPage() {
  const { isLoggedIn, isAuthLoading, login, mounted } = useAuth();
  const [items, setItems] = useState<MyVoucherOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!mounted) return;
    if (isAuthLoading) return;
    if (!isLoggedIn) {
      setItems([]);
      setError("");
      setLoading(false);
      return;
    }
    javaApi.myVoucherOrders()
      .then((response) => {
        if (response.success) {
          setItems(response.data ?? []);
          setError("");
        } else {
          setError(response.errorMsg ?? "讀取餐券失敗");
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "讀取餐券失敗"))
      .finally(() => setLoading(false));
  }, [isAuthLoading, isLoggedIn, mounted]);

  return (
    <main className="bb-premium-page min-h-screen px-4 py-8 text-foreground md:px-8">
      <section className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-5 border-b bb-accent-rule pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="bb-page-kicker">ByteBites vouchers</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-normal md:text-4xl">我的餐券</h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground md:text-base">
              限時餐券搶購成功後會集中在這裡。用餐前出示餐券內容，即可折抵對應方案。
            </p>
          </div>
          <Link
            href="/shops"
            className="inline-flex w-fit rounded-lg border border-[rgb(167_137_67_/_0.22)] bg-[rgb(255_253_248_/_0.72)] px-4 py-2 text-sm font-medium hover:bg-white"
          >
            繼續探索
          </Link>
        </div>

        <div className="py-6">
          {mounted && !isAuthLoading && !isLoggedIn ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-10 text-center">
              <TicketPercent className="mx-auto h-10 w-10 text-amber-700" />
              <h2 className="mt-4 text-xl font-medium text-amber-950">請先用 LINE 登入</h2>
              <p className="mt-2 text-sm leading-6 text-amber-800">
                餐券會綁定 LINE 帳號；登入後才能查看已搶到的限時餐券。
              </p>
              <button
                type="button"
                onClick={login}
                className="mt-6 inline-flex rounded-lg bg-emerald-700 px-5 py-3 text-sm font-medium text-white hover:bg-emerald-800"
              >
                用 LINE 登入
              </button>
            </div>
          ) : loading ? (
            <div className="rounded-lg border border-dashed p-10 text-center text-zinc-500">
              讀取餐券中...
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
              {error}
            </div>
          ) : items.length === 0 ? (
            <div className="bb-empty-state rounded-lg p-10 text-center">
              <TicketPercent className="mx-auto h-10 w-10 text-zinc-300" />
              <h2 className="mt-4 text-xl font-medium">還沒有餐券</h2>
              <p className="mt-2 text-sm text-zinc-500">
                到店家詳情頁的「限時餐券」區搶購，成功後會出現在這裡。
              </p>
              <Link
                href="/shops"
                className="mt-6 inline-flex rounded-lg bg-emerald-700 px-5 py-3 text-sm font-medium text-white hover:bg-emerald-800"
              >
                去探索餐廳
              </Link>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {items.map((order) => {
                const status = STATUS_LABELS[order.status] ?? {
                  label: `狀態 ${order.status}`,
                  className: "bg-zinc-100 text-zinc-500 border-zinc-200",
                };
                const saving = Math.max((order.actualValue ?? 0) - (order.payValue ?? 0), 0);
                return (
                  <article key={order.id} className="bb-premium-surface rounded-lg p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-medium">{order.title ?? `餐券 #${order.voucherId}`}</h2>
                        {order.subTitle ? (
                          <p className="mt-1 text-sm text-muted-foreground">{order.subTitle}</p>
                        ) : null}
                      </div>
                      <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-medium ${status.className}`}>
                        {status.label}
                      </span>
                    </div>

                    {order.shopId ? (
                      <Link
                        href={`/shops/${order.shopId}`}
                        className="mt-3 inline-flex items-center gap-1.5 text-sm text-emerald-800 hover:text-emerald-700"
                      >
                        <Store className="h-3.5 w-3.5" />
                        {order.shopName ?? `店家 #${order.shopId}`}
                      </Link>
                    ) : null}

                    <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                      <div className="rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-[rgb(255_253_248_/_0.72)] p-3">
                        <p className="text-xs text-zinc-400">餐券價</p>
                        <p className="mt-1 font-medium">{formatCurrency(order.payValue)}</p>
                      </div>
                      <div className="rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-[rgb(255_253_248_/_0.72)] p-3">
                        <p className="text-xs text-zinc-400">原價值</p>
                        <p className="mt-1 font-medium">{formatCurrency(order.actualValue)}</p>
                      </div>
                      <div className="rounded-lg border border-[rgb(222_216_203_/_0.82)] bg-[rgb(255_253_248_/_0.72)] p-3">
                        <p className="text-xs text-zinc-400">現省</p>
                        <p className="mt-1 font-medium text-emerald-700">{formatCurrency(saving)}</p>
                      </div>
                    </div>

                    {order.rules ? (
                      <p className="mt-3 text-xs leading-5 text-zinc-500">使用規則：{order.rules}</p>
                    ) : null}
                    <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-zinc-400">
                      <CalendarDays className="h-3.5 w-3.5" />
                      搶購於 {formatDateTime(order.createTime)}
                    </p>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
