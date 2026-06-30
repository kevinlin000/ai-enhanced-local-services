"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCheck,
  CheckCircle2,
  Clock,
  CreditCard,
  ReceiptText,
  Store,
  TicketPercent,
} from "lucide-react";
import {
  javaApi,
  type MerchantDepositAdjustment,
  type MerchantFlashDealSummary,
  type MerchantIncident,
  type MerchantRefundNotificationPolicy,
  type MerchantRefundOperationsReport,
  type MerchantRefundSlaSummary,
  type MerchantShop,
  type MerchantSlot,
} from "@/lib/api";
import {
  ADJUSTMENT_SOURCE_LABEL,
  ADJUSTMENT_TYPE_LABEL,
  BOOKING_STATUS_LABEL,
  DEFAULT_DEMO_SHOP_PRIORITY,
  INCIDENT_TYPE_LABEL,
  MERCHANT_SECTION_COPY,
  MERCHANT_SECTION_EVENT,
  MIN_BOOKING_DATE,
  REFUND_REPORT_ACTION_LABEL,
  SETTLEMENT_STATUS_LABEL,
  currency,
  demoStoryForShop,
  merchantSectionFromHash,
  refundHeadlineCopy,
  refundNotificationPolicyLabel,
  refundReasonLabel,
  refundReportTone,
  settlementTone,
  slotHealth,
  type MerchantSection,
  voucherCurrency,
} from "@/lib/merchantOps";

export default function MerchantPage() {
  const [token, setToken] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<MerchantSection>("overview");
  const [shops, setShops] = useState<MerchantShop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null);
  const [date, setDate] = useState(MIN_BOOKING_DATE);
  const [tableType, setTableType] = useState("normal");
  const [slots, setSlots] = useState<MerchantSlot[]>([]);
  const [incidents, setIncidents] = useState<MerchantIncident[]>([]);
  const [depositAdjustments, setDepositAdjustments] = useState<MerchantDepositAdjustment[]>([]);
  const [flashDeals, setFlashDeals] = useState<MerchantFlashDealSummary | null>(null);
  const [refundSla, setRefundSla] = useState<MerchantRefundSlaSummary | null>(null);
  const [refundReport, setRefundReport] = useState<MerchantRefundOperationsReport | null>(null);
  const [refundNotificationPolicy, setRefundNotificationPolicy] = useState<MerchantRefundNotificationPolicy | null>(
    null,
  );
  const [capacities, setCapacities] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [incidentLoading, setIncidentLoading] = useState(false);
  const [adjustmentLoading, setAdjustmentLoading] = useState(false);
  const [flashDealLoading, setFlashDealLoading] = useState(false);
  const [refundSlaLoading, setRefundSlaLoading] = useState(false);
  const [incidentBusyId, setIncidentBusyId] = useState<number | null>(null);
  const [adjustmentBusyId, setAdjustmentBusyId] = useState<number | null>(null);
  const [settlementRefs, setSettlementRefs] = useState<Record<number, string>>({});
  const [refundEscalationNotes, setRefundEscalationNotes] = useState<Record<number, string>>({});
  const [refundNotifyBusy, setRefundNotifyBusy] = useState(false);
  const [refundPolicyBusy, setRefundPolicyBusy] = useState(false);
  const [proposalBusyKey, setProposalBusyKey] = useState<string | null>(null);
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
  const flashDealTotals = useMemo(
    () =>
      (flashDeals?.deals ?? []).reduce(
        (acc, deal) => ({
          claimedRevenue: acc.claimedRevenue + Number(deal.payValue ?? 0) * Number(deal.orderCount ?? 0),
          remainingRevenue: acc.remainingRevenue + Number(deal.payValue ?? 0) * Number(deal.stock ?? 0),
        }),
        { claimedRevenue: 0, remainingRevenue: 0 },
      ),
    [flashDeals],
  );

  useEffect(() => {
    function syncSection(event?: Event) {
      const customHash =
        event instanceof CustomEvent && typeof event.detail === "string" ? event.detail : window.location.hash;
      setActiveSection(merchantSectionFromHash(customHash));
    }

    syncSection();
    window.addEventListener("hashchange", syncSection);
    window.addEventListener(MERCHANT_SECTION_EVENT, syncSection);
    return () => {
      window.removeEventListener("hashchange", syncSection);
      window.removeEventListener(MERCHANT_SECTION_EVENT, syncSection);
    };
  }, []);

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
        const response = await javaApi.merchantShops();
        if (!response.success) throw new Error("無法載入店家權限");
        if (cancelled) return;
        setShops(response.data);
        const preferredShop =
          DEFAULT_DEMO_SHOP_PRIORITY.map((shopId) => response.data.find((shop) => shop.id === shopId)).find(
            Boolean,
          ) ?? response.data[0] ?? null;
        setSelectedShopId(preferredShop?.id ?? null);
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
    if (!selectedShopId) {
      setFlashDeals(null);
      return;
    }
    const shopId = selectedShopId;

    let cancelled = false;
    async function loadFlashDeals() {
      setFlashDealLoading(true);
      setError(null);
      try {
        const response = await javaApi.merchantFlashDeals(shopId);
        if (!response.success) throw new Error(response.errorMsg ?? "無法載入限時餐券");
        if (!cancelled) setFlashDeals(response.data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "載入限時餐券失敗");
      } finally {
        if (!cancelled) setFlashDealLoading(false);
      }
    }

    loadFlashDeals();
    return () => {
      cancelled = true;
    };
  }, [selectedShopId]);

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

  useEffect(() => {
    if (!selectedShopId) {
      setIncidents([]);
      return;
    }
    const shopId = selectedShopId;

    let cancelled = false;
    async function loadIncidents() {
      setIncidentLoading(true);
      setError(null);
      try {
        const response = await javaApi.merchantIncidents({ shopId, status: "OPEN" });
        if (!response.success) throw new Error(response.errorMsg ?? "無法載入救場事件");
        if (!cancelled) setIncidents(response.data.incidents);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "載入救場事件失敗");
      } finally {
        if (!cancelled) setIncidentLoading(false);
      }
    }

    loadIncidents();
    return () => {
      cancelled = true;
    };
  }, [selectedShopId]);

  useEffect(() => {
    if (!selectedShopId) {
      setDepositAdjustments([]);
      setRefundSla(null);
      setRefundReport(null);
      setRefundNotificationPolicy(null);
      return;
    }
    const shopId = selectedShopId;

    let cancelled = false;
    async function loadDepositAdjustments() {
      setAdjustmentLoading(true);
      setRefundSlaLoading(true);
      setError(null);
      try {
        const [adjustmentResponse, slaResponse, reportResponse, policyResponse] = await Promise.all([
          javaApi.merchantDepositAdjustments({ shopId, status: "OPEN" }),
          javaApi.merchantRefundSla({ shopId, stuckMinutes: 30 }),
          javaApi.merchantRefundReport({ shopId, stuckMinutes: 30 }),
          javaApi.merchantRefundNotificationPolicy({ shopId, stuckMinutes: 30, cooldownMinutes: 120 }),
        ]);
        if (!adjustmentResponse.success) {
          throw new Error(adjustmentResponse.errorMsg ?? "無法載入訂金差額處理");
        }
        if (!slaResponse.success) {
          throw new Error(slaResponse.errorMsg ?? "無法載入退款提醒");
        }
        if (!reportResponse.success) {
          throw new Error(reportResponse.errorMsg ?? "無法載入退款處理摘要");
        }
        if (!policyResponse.success) {
          throw new Error(policyResponse.errorMsg ?? "無法載入營運提醒設定");
        }
        if (!cancelled) {
          setDepositAdjustments(adjustmentResponse.data.adjustments);
          setRefundSla(slaResponse.data);
          setRefundReport(reportResponse.data);
          setRefundNotificationPolicy(policyResponse.data);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "載入訂金差額處理失敗");
      } finally {
        if (!cancelled) {
          setAdjustmentLoading(false);
          setRefundSlaLoading(false);
        }
      }
    }

    loadDepositAdjustments();
    return () => {
      cancelled = true;
    };
  }, [selectedShopId]);

  async function refreshRefundSlaSummary(shopId: number) {
    setRefundSlaLoading(true);
    try {
      const [slaResponse, reportResponse, policyResponse] = await Promise.all([
        javaApi.merchantRefundSla({ shopId, stuckMinutes: 30 }),
        javaApi.merchantRefundReport({ shopId, stuckMinutes: 30 }),
        javaApi.merchantRefundNotificationPolicy({ shopId, stuckMinutes: 30, cooldownMinutes: 120 }),
      ]);
      if (!slaResponse.success) throw new Error(slaResponse.errorMsg ?? "無法載入退款提醒");
      if (!reportResponse.success) throw new Error(reportResponse.errorMsg ?? "無法載入退款處理摘要");
      if (!policyResponse.success) throw new Error(policyResponse.errorMsg ?? "無法載入營運提醒設定");
      setRefundSla(slaResponse.data);
      setRefundReport(reportResponse.data);
      setRefundNotificationPolicy(policyResponse.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "載入退款提醒失敗");
    } finally {
      setRefundSlaLoading(false);
    }
  }

  async function notifyRefundOperationsDigest() {
    if (!selectedShopId) return;
    setRefundNotifyBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.notifyMerchantRefundReport({ shopId: selectedShopId, stuckMinutes: 30 });
      if (!response.success) throw new Error(response.errorMsg ?? "退款摘要通知失敗");
      if (response.data.report) {
        setRefundReport(response.data.report);
      }
      const policyResponse = await javaApi.merchantRefundNotificationPolicy({
        shopId: selectedShopId,
        stuckMinutes: 30,
        cooldownMinutes: 120,
      });
      if (policyResponse.success) {
        setRefundNotificationPolicy(policyResponse.data);
      }
      if (response.data.skipped) {
        setMessage(
          response.data.reason === "NO_LINKED_LINE_USER"
            ? "退款摘要已產生；目前商家帳號尚未綁定 LINE，未送出推播。"
            : "目前沒有需要通知的退款異常。",
        );
      } else {
        setMessage("退款處理摘要已送出 LINE 通知。");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "退款摘要通知失敗");
    } finally {
      setRefundNotifyBusy(false);
    }
  }

  async function dispatchRefundOperationsDigestIfDue() {
    if (!selectedShopId) return;
    setRefundPolicyBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.dispatchMerchantRefundReportIfDue({
        shopId: selectedShopId,
        stuckMinutes: 30,
        cooldownMinutes: 120,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "營運提醒判斷失敗");
      if (response.data.report) setRefundReport(response.data.report);
      if (response.data.policy) setRefundNotificationPolicy(response.data.policy);
      if (response.data.skipped) {
        const reason = response.data.reason;
        setMessage(
          reason === "COOLDOWN_ACTIVE"
            ? "剛通知過營運人員，這次不重複推播。"
            : reason === "NO_LINKED_LINE_USER"
              ? "系統判定需要通知；商家帳號尚未綁定 LINE，未送出。"
              : "目前沒有需要通知的退款異常。",
        );
      } else {
        setMessage("系統判定需要通知，LINE 摘要已送出。");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "營運提醒判斷失敗");
    } finally {
      setRefundPolicyBusy(false);
    }
  }

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
      setMessage("容量已更新。新的剩餘位子會立刻影響 Web / LINE 訂位與空位通知。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setSaving(false);
    }
  }

  async function resolveIncident(incident: MerchantIncident) {
    if (!selectedShopId) return;
    setIncidentBusyId(incident.id);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.resolveMerchantIncident({
        shopId: selectedShopId,
        incidentId: incident.id,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "救場事件處理失敗");
      setIncidents((current) => current.filter((item) => item.id !== incident.id));
      setMessage("救場事件已標記為已處理；顧客端會在下次讀取訂位時看不到 open incident。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "救場事件處理失敗");
    } finally {
      setIncidentBusyId(null);
    }
  }

  async function proposeSlot(incident: MerchantIncident, slot: NonNullable<MerchantIncident["alternativeSlots"]>[number]) {
    if (!selectedShopId) return;
    const key = `${incident.id}-${slot.time}`;
    setProposalBusyKey(key);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.proposeMerchantIncidentSlot({
        shopId: selectedShopId,
        incidentId: incident.id,
        date: incident.bookingDate,
        time: slot.time,
        tableType: slot.tableType,
        people: incident.people,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "替代時段提案送出失敗");
      setIncidents((current) =>
        current.map((item) => (item.id === incident.id ? response.data : item)),
      );
      setMessage("替代時段提案已送出，等待顧客在我的訂位確認。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "替代時段提案送出失敗");
    } finally {
      setProposalBusyKey(null);
    }
  }

  async function recordDepositSettlement(adjustment: MerchantDepositAdjustment) {
    if (!selectedShopId) return;
    if (adjustment.adjustmentType === "REFUND") {
      setError("退款請先送出請求，等待金流確認完成");
      return;
    }
    const settlementTransId = (settlementRefs[adjustment.id] ?? "").trim();
    if (!settlementTransId) {
      setError("請輸入補款交易編號");
      return;
    }

    setAdjustmentBusyId(adjustment.id);
    setError(null);
    setMessage(null);
    try {
      const actionLabel = adjustment.adjustmentType === "TOP_UP" ? "補款" : "退款";
      const response = await javaApi.recordMerchantDepositAdjustmentSettlement({
        shopId: selectedShopId,
        adjustmentId: adjustment.id,
        provider: "TAPPAY",
        settlementTransId,
        settlementNote: `${actionLabel} ${currency(adjustment.deltaAmount)} 已由金流完成`,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "補款完成記錄失敗");
      setDepositAdjustments((current) =>
        current.map((item) => (item.id === adjustment.id ? response.data : item)),
      );
      setSettlementRefs((current) => {
        const next = { ...current };
        delete next[adjustment.id];
        return next;
      });
      setMessage("補款已記錄，現在可以套用改單。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "補款完成記錄失敗");
    } finally {
      setAdjustmentBusyId(null);
    }
  }

  async function requestRefundSettlement(adjustment: MerchantDepositAdjustment) {
    if (!selectedShopId) return;
    setAdjustmentBusyId(adjustment.id);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.requestMerchantDepositAdjustmentRefund({
        shopId: selectedShopId,
        adjustmentId: adjustment.id,
        settlementNote: `退款請求已建立：${currency(adjustment.deltaAmount)}`,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "退款請求建立失敗");
      setDepositAdjustments((current) =>
        current.map((item) => (item.id === adjustment.id ? response.data : item)),
      );
      await refreshRefundSlaSummary(selectedShopId);
      setMessage("退款請求已送出，等待金流確認。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "退款請求建立失敗");
    } finally {
      setAdjustmentBusyId(null);
    }
  }

  async function reconcileRefundSettlement(
    adjustment: MerchantDepositAdjustment,
    status: "COMPLETED" | "FAILED",
  ) {
    if (!selectedShopId) return;
    const settlementTransId = (settlementRefs[adjustment.id] ?? "").trim();
    if (status === "COMPLETED" && !settlementTransId) {
      setError("退款成功時請輸入退款交易編號");
      return;
    }

    setAdjustmentBusyId(adjustment.id);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.reconcileRefundAdjustment({
        adjustmentId: adjustment.id,
        bookingCode: adjustment.bookingCode,
        amount: Math.abs(Number(adjustment.deltaAmount ?? 0)),
        status,
        settlementTransId: settlementTransId || undefined,
        settlementNote:
          status === "COMPLETED"
            ? `退款完成：${currency(adjustment.deltaAmount)}`
            : `退款失敗：${currency(adjustment.deltaAmount)}`,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "退款結果記錄失敗");
      setDepositAdjustments((current) =>
        current.map((item) => (item.id === adjustment.id ? response.data : item)),
      );
      setSettlementRefs((current) => {
        const next = { ...current };
        delete next[adjustment.id];
        return next;
      });
      await refreshRefundSlaSummary(selectedShopId);
      setMessage(status === "COMPLETED" ? "退款已確認完成，現在可以套用改單。" : "退款已標記失敗，可重新送出退款請求。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "退款結果記錄失敗");
    } finally {
      setAdjustmentBusyId(null);
    }
  }

  async function escalateRefundAdjustment(adjustment: MerchantDepositAdjustment) {
    if (!selectedShopId) return;
    const note =
      (refundEscalationNotes[adjustment.id] ?? "").trim() ||
      `退款異常人工確認：${currency(adjustment.deltaAmount)}`;

    setAdjustmentBusyId(adjustment.id);
    setError(null);
    setMessage(null);
    try {
      const response = await javaApi.escalateMerchantDepositAdjustmentRefund({
        shopId: selectedShopId,
        adjustmentId: adjustment.id,
        escalationNote: note,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "退款人工確認失敗");
      setDepositAdjustments((current) =>
        current.map((item) => (item.id === adjustment.id ? response.data : item)),
      );
      setRefundEscalationNotes((current) => {
        const next = { ...current };
        delete next[adjustment.id];
        return next;
      });
      await refreshRefundSlaSummary(selectedShopId);
      setMessage("退款異常已標記為人工確認。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "退款人工確認失敗");
    } finally {
      setAdjustmentBusyId(null);
    }
  }

  async function resolveDepositAdjustment(adjustment: MerchantDepositAdjustment) {
    if (!selectedShopId) return;
    setAdjustmentBusyId(adjustment.id);
    setError(null);
    setMessage(null);
    try {
      const note =
        adjustment.adjustmentType === "TOP_UP"
          ? `補款已完成：${adjustment.settlementTransId ?? ""}`
          : `退款已完成：${adjustment.settlementTransId ?? ""}`;
      const response = await javaApi.resolveMerchantDepositAdjustment({
        shopId: selectedShopId,
        adjustmentId: adjustment.id,
        handlingNote: note,
      });
      if (!response.success) throw new Error(response.errorMsg ?? "訂金差額處理失敗");
      setDepositAdjustments((current) => current.filter((item) => item.id !== adjustment.id));
      if (adjustment.incidentId) {
        setIncidents((current) => current.filter((incident) => incident.id !== adjustment.incidentId));
      }
      await refreshRefundSlaSummary(selectedShopId);
      setMessage("訂金差額已處理，改單已套用並同步訂位狀態。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "訂金差額處理失敗");
    } finally {
      setAdjustmentBusyId(null);
    }
  }

  const refundAttentionCount = Number(refundSla?.totalAttentionCount ?? 0);
  const pendingRefundEscalationCount = Number(refundSla?.pendingEscalationCount ?? refundAttentionCount);
  const pendingRefundReportItems = (refundReport?.pendingEscalationItems ?? []).slice(0, 2);
  const escalatedRefundReportItems = (refundReport?.escalatedItems ?? []).slice(0, 2);
  const refundReportAction =
    REFUND_REPORT_ACTION_LABEL[refundReport?.recommendedAction ?? ""] ?? refundReport?.recommendedAction ?? "";
  const refundPolicyLabel = refundNotificationPolicyLabel(refundNotificationPolicy);
  const activeSectionCopy = MERCHANT_SECTION_COPY[activeSection];

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f7f6f2] text-stone-950">
      <div className="mx-auto flex max-w-[1500px] min-w-0 flex-col gap-5 px-4 py-5 lg:px-6">
        <header className="border border-stone-200 bg-white">
          <div className="grid gap-5 p-5 lg:grid-cols-[1fr_520px] lg:items-end">
            <div>
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-stone-500">
                <span>營運總覽</span>
                <span className="text-stone-300">/</span>
                <span>{activeSectionCopy.label}</span>
                <span className="text-stone-300">/</span>
                <span>{selectedShop?.district ?? "展示環境"}</span>
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-normal text-stone-950">
                {activeSectionCopy.label}
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-stone-600">
                {activeSectionCopy.description}
              </p>
            </div>

            <div className="min-w-0 border border-stone-200 bg-[#fbfaf7] p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                    <Store className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-stone-500">目前店家</p>
                    <p className="truncate text-base font-semibold">{selectedShop?.name ?? "載入中"}</p>
                  </div>
                </div>
                <span className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
                  {token ? "登入帳號" : "展示環境"}
                </span>
              </div>
              <label className="mt-3 block text-xs font-semibold text-stone-500">
                切換店家
                <select
                  value={selectedShopId ?? ""}
                  onChange={(event) => setSelectedShopId(Number(event.target.value) || null)}
                  className="mt-1 h-10 w-full rounded-lg border border-stone-200 bg-white px-3 text-sm font-semibold text-stone-900 outline-none focus:border-emerald-500"
                >
                  {shops.length === 0 ? (
                    <option value="">讀取店家中</option>
                  ) : null}
                  {shops.map((shop) => (
                    <option key={shop.id} value={shop.id}>
                      {shop.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Metric label="總容量" value={loading ? "讀取中" : totals.capacity} />
                <Metric label="已訂" value={loading ? "讀取中" : totals.booked} />
                <Metric label="剩餘" value={loading ? "讀取中" : totals.remaining} />
              </div>
            </div>
          </div>

          <div className="grid border-t border-stone-200 text-sm text-stone-600 md:grid-cols-3">
            <DemoNote title="Story 1" detail="部門聚餐、熱門時段、候位通知" />
            <DemoNote title="Story 2" detail="家庭用餐、開車抵達、停車提醒" />
            <DemoNote title="現場測試" detail="調低 19:00 容量即可模擬額滿" />
          </div>
        </header>

        <section
          className={
            activeSection === "overview"
              ? "grid min-w-0 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]"
              : "min-w-0"
          }
        >
          {activeSection === "overview" || activeSection === "shops" ? (
          <aside className={activeSection === "shops" ? "min-w-0" : "min-w-0 space-y-5"}>
            <section id="shops" className="border border-stone-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold">店家</h2>
                <span className="rounded-lg bg-stone-100 px-3 py-1 text-xs font-semibold text-stone-600">
                  {shops.length} 家
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-stone-500">
                選店後，右側工作區同步顯示事件、訂金與容量。
              </p>

              <div className="mt-4 max-h-[760px] space-y-2 overflow-y-auto pr-1">
                {shops.map((shop) => {
                  const demoStory = demoStoryForShop(shop);
                  return (
                    <button
                      key={shop.id}
                      type="button"
                      onClick={() => setSelectedShopId(shop.id)}
                      className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                        shop.id === selectedShopId
                          ? "border-emerald-600 bg-emerald-50"
                          : "border-stone-200 bg-white hover:border-stone-300"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-semibold">{shop.name}</p>
                          <p className="mt-1 text-sm text-stone-500">{shop.district ?? "未標示行政區"}</p>
                        </div>
                        <span className="rounded-md bg-stone-100 px-2 py-1 text-xs font-semibold text-stone-600">
                          可管理
                        </span>
                      </div>
                      {demoStory ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <span className="rounded-md bg-stone-950 px-2.5 py-1 text-xs font-semibold text-white">
                            {demoStory.label}
                          </span>
                          <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                            {demoStory.detail}
                          </span>
                        </div>
                      ) : null}
                    </button>
                  );
                })}
                {!loading && shops.length === 0 && (
                  <p className="rounded-lg bg-stone-50 p-4 text-sm text-stone-600">
                    展示環境目前沒有可管理店家，請先確認資料庫 migration 已套用。
                  </p>
                )}
              </div>
            </section>
          </aside>
          ) : null}

          {activeSection !== "shops" ? (
          <div className="min-w-0 space-y-5">
            {activeSection === "overview" ? (
              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <MerchantWorkCard
                  title="工作佇列"
                  description="晚到、現場等候與替代時段提案"
                  count={incidentLoading ? "讀取中" : `${incidents.length} 件`}
                  href="#incident-queue"
                  onClick={() => setActiveSection("incidents")}
                />
                <MerchantWorkCard
                  title="訂金退款"
                  description="補款、退款、人工確認"
                  count={adjustmentLoading ? "讀取中" : `${depositAdjustments.length} 件`}
                  href="#deposit-queue"
                  onClick={() => setActiveSection("deposits")}
                />
                <MerchantWorkCard
                  title="時段容量"
                  description="調整可接待人數與剩餘位子"
                  count={loading ? "讀取中" : `${totals.remaining} 位`}
                  href="#slots"
                  onClick={() => setActiveSection("slots")}
                />
                <MerchantWorkCard
                  title="限時餐券"
                  description="離峰補位、限量轉單"
                  count={flashDealLoading ? "讀取中" : `${flashDeals?.totalDeals ?? 0} 檔`}
                  href="#flash-deals"
                  onClick={() => setActiveSection("overview")}
                />
                <MerchantWorkCard
                  title="店家清單"
                  description="切換示範店家與故事標籤"
                  count={loading ? "讀取中" : `${shops.length} 家`}
                  href="#shops"
                  onClick={() => setActiveSection("shops")}
                />
              </section>
            ) : null}

            {activeSection === "overview" ? (
              <section id="flash-deals" className="rounded-lg border border-stone-200 bg-white">
                <div className="flex flex-col gap-4 border-b border-stone-200 p-5 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="rounded-lg bg-emerald-50 p-3 text-emerald-700">
                      <TicketPercent className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <h2 className="text-xl font-semibold">限時餐券</h2>
                      <p className="mt-1 break-words text-sm text-stone-500">
                        把 AI 推薦流量導到限量餐券，協助離峰補位、熱門時段轉單，並追蹤庫存與已搶營收。
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <Metric label="活動" value={flashDealLoading ? "讀取中" : flashDeals?.totalDeals ?? 0} />
                    <Metric
                      label="已搶營收"
                      value={flashDealLoading ? "讀取中" : voucherCurrency(flashDealTotals.claimedRevenue)}
                    />
                    <Metric
                      label="可售額"
                      value={flashDealLoading ? "讀取中" : voucherCurrency(flashDealTotals.remainingRevenue)}
                    />
                  </div>
                </div>

                <div className="grid gap-3 p-5">
                  {(flashDeals?.deals ?? []).map((deal) => (
                    <div
                      key={deal.dealId}
                      className="grid gap-4 rounded-lg border border-emerald-100 bg-emerald-50/40 p-4 lg:grid-cols-[1fr_160px_160px_160px]"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                            限時餐券
                          </span>
                          <span className="text-xs font-semibold text-stone-500">#{deal.dealId}</span>
                        </div>
                        <p className="mt-3 truncate text-lg font-semibold">{deal.title}</p>
                        <p className="mt-1 text-sm text-stone-600">{deal.subTitle ?? "限時活動"}</p>
                        <p className="mt-2 text-sm font-medium text-emerald-800">
                          售價 {voucherCurrency(deal.payValue)} · 面額 {voucherCurrency(deal.actualValue)}
                        </p>
                      </div>
                      <IncidentFact label="剩餘庫存" value={`${deal.stock} 張`} />
                      <IncidentFact label="已搶訂單" value={`${deal.orderCount} 筆`} />
                      <IncidentFact label="已搶營收" value={voucherCurrency(deal.payValue * deal.orderCount)} />
                    </div>
                  ))}
                  {!flashDealLoading && (flashDeals?.deals ?? []).length === 0 ? (
                    <div className="rounded-lg bg-stone-50 p-6 text-sm text-stone-500">
                      目前店家沒有進行中的限時餐券。切換到 KiKi、辛殿、刁民、鼎泰豐等 demo 店家可查看活動資料。
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            <section
              id="incident-queue"
              className={activeSection === "incidents" ? "rounded-lg border border-stone-200 bg-white" : "hidden"}
            >
              <div className="flex flex-col gap-4 border-b border-stone-200 p-5 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="rounded-lg bg-stone-100 p-3 text-stone-700">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-xl font-semibold">臨場救場</h2>
                    <p className="mt-1 break-words text-sm text-stone-500">
                      顧客晚到或現場等候過久時，店家可保留座位、提出替代時段，並同步 LINE 通知。
                    </p>
                  </div>
                </div>
                <span className="w-fit rounded-md bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700">
                  {incidentLoading ? "讀取中" : `${incidents.length} 件待處理`}
                </span>
              </div>

              <div className="grid gap-3 p-5">
                {incidents.map((incident) => (
                  <div
                    key={incident.id}
                    className="grid gap-4 rounded-lg border border-stone-200 bg-[#fffdf8] p-4 lg:grid-cols-[1fr_180px_140px]"
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-stone-950 px-2.5 py-1 text-xs font-medium text-white">
                          {INCIDENT_TYPE_LABEL[incident.incidentType] ?? incident.incidentType}
                        </span>
                        <span className="rounded-md bg-white px-2.5 py-1 text-xs font-medium text-stone-600">
                          {BOOKING_STATUS_LABEL[incident.bookingStatus] ?? incident.bookingStatus}
                        </span>
                        <span className="text-xs font-semibold text-stone-500">{incident.bookingCode}</span>
                      </div>
                      <p className="mt-3 text-lg font-semibold">{incident.title}</p>
                      <p className="mt-1 text-sm leading-6 text-stone-600">{incident.customerMessage}</p>
                      {incident.proposedChange?.status === "PENDING" ? (
                        <div className="mt-3 rounded-lg border border-emerald-100 bg-white px-3 py-2">
                          <p className="text-xs font-medium text-emerald-700">已送出顧客確認</p>
                          <p className="mt-1 text-sm font-semibold text-stone-950">
                            {incident.proposedChange.date} {incident.proposedChange.time}
                          </p>
                          {incident.proposedChange.expiresAt ? (
                            <p className="mt-1 text-xs text-stone-500">
                              有效至 {incident.proposedChange.expiresAt}
                            </p>
                          ) : null}
                          <p className="mt-1 text-xs text-stone-500">
                            等待顧客接受後，Java 才會正式改單並釋放原時段。
                          </p>
                        </div>
                      ) : incident.alternativeSlots?.length ? (
                        <div className="mt-3">
                          {incident.proposedChange?.status === "DECLINED" || incident.proposedChange?.status === "EXPIRED" ? (
                            <p className="mb-2 text-xs font-medium text-amber-700">
                              {incident.proposedChange.status === "DECLINED" ? "顧客已拒絕上一個提案" : "上一個提案已逾期"}，可重新送出替代時段。
                            </p>
                          ) : null}
                          <p className="text-xs font-medium text-stone-500">可協調替代時段</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {incident.alternativeSlots.map((slot) => (
                              <button
                                type="button"
                                key={`${incident.id}-${slot.time}`}
                                onClick={() => proposeSlot(incident, slot)}
                                disabled={proposalBusyKey === `${incident.id}-${slot.time}`}
                                className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 ring-1 ring-emerald-100 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                <Clock className="h-3.5 w-3.5" />
                                {proposalBusyKey === `${incident.id}-${slot.time}` ? "送出中" : (slot.label ?? slot.time)}
                                <span className="font-semibold text-stone-500">剩 {slot.remaining} 位</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p className="mt-3 text-xs font-semibold text-stone-500">
                          目前沒有足夠座位的同日替代時段。
                        </p>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-2 lg:grid-cols-1">
                      <IncidentFact label="訂位" value={`${incident.bookingDate} ${incident.bookingTime}`} />
                      <IncidentFact label="人數" value={`${incident.people} 人`} />
                      <IncidentFact label="預估" value={incident.adjustedTime || `${incident.delayMinutes} 分鐘`} />
                    </div>

                    <div className="flex items-center justify-start lg:justify-end">
                      <button
                        type="button"
                        onClick={() => resolveIncident(incident)}
                        disabled={incidentBusyId === incident.id}
                        className="inline-flex items-center gap-2 rounded-md bg-stone-950 px-4 py-2 text-sm font-semibold text-white hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <CheckCheck className="h-4 w-4" />
                        {incidentBusyId === incident.id ? "處理中" : "標記已處理"}
                      </button>
                    </div>
                  </div>
                ))}

                {!incidentLoading && incidents.length === 0 && (
                  <div className="rounded-lg bg-stone-50 p-6 text-sm text-stone-500">
                    目前沒有待處理救場事件。顧客在「我的訂位」建立救場通知，或對 AI 說「我塞車會晚到 20 分鐘」後會出現在這裡。
                  </div>
                )}
              </div>
            </section>

            <section
              id="deposit-queue"
              className={activeSection === "deposits" ? "rounded-lg border border-stone-200 bg-white" : "hidden"}
            >
              <div className="flex flex-col gap-4 border-b border-stone-200 p-5 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="rounded-lg bg-stone-100 p-3 text-stone-700">
                    <ReceiptText className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-xl font-semibold">訂金差額處理</h2>
                    <p className="mt-1 break-words text-sm text-stone-500">
                      已付款訂位改人數或改時段後，若訂金變多就補收，變少就退款；完成後才套用改單。
                    </p>
                  </div>
                </div>
                <span className="w-fit rounded-md bg-stone-100 px-4 py-2 text-sm font-semibold text-stone-700">
                  {adjustmentLoading ? "讀取中" : `${depositAdjustments.length} 件待處理`}
                </span>
              </div>

              {refundSlaLoading ? (
                <div className="border-b border-sky-100 bg-sky-50 px-5 py-3 text-sm font-medium text-sky-800">
                  退款提醒讀取中
                </div>
              ) : refundSla ? (
                <div
                  className={`border-b px-5 py-3 ${
                    refundAttentionCount > 0
                      ? "border-red-100 bg-red-50 text-red-800"
                      : "border-emerald-100 bg-emerald-50 text-emerald-800"
                  }`}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-2">
                      {refundAttentionCount > 0 ? (
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      ) : (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                      )}
                      <div>
                        <p className="text-sm font-semibold">
                          {refundAttentionCount > 0
                            ? `退款注意：${refundAttentionCount} 件需處理`
                            : "退款狀態正常"}
                        </p>
                        <p className="mt-1 text-xs font-semibold">
                          {refundAttentionCount > 0
                            ? `${refundSla.failedCount} 件退款失敗，${refundSla.stuckProcessingCount} 件超過 ${refundSla.stuckMinutes} 分鐘未完成，${pendingRefundEscalationCount} 件尚未人工確認。`
                            : `沒有失敗退款，也沒有超過 ${refundSla.stuckMinutes} 分鐘未完成的退款。`}
                        </p>
                      </div>
                    </div>
                    {refundSla.oldestRequestedAt ? (
                      <span className="text-xs font-medium">最早請求 {refundSla.oldestRequestedAt}</span>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {!refundSlaLoading && refundReport ? (
                <div className={`border-b px-5 py-4 ${refundReportTone(refundReport.status)}`}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex items-start gap-2">
                      {refundReport.status === "CLEAR" ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                      ) : (
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      )}
                      <div>
                        <p className="text-sm font-semibold">退款處理摘要</p>
                        <p className="mt-1 text-xs font-semibold">{refundHeadlineCopy(refundReport.headline)}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="w-fit rounded-md bg-white/80 px-3 py-1 text-xs font-semibold">
                        {refundReportAction}
                      </span>
                      {refundNotificationPolicy ? (
                        <span className="w-fit rounded-md bg-white/80 px-3 py-1 text-xs font-semibold">
                          {refundPolicyLabel}
                        </span>
                      ) : null}
                      <button
                        type="button"
                        onClick={notifyRefundOperationsDigest}
                        disabled={refundNotifyBusy}
                        className="inline-flex items-center gap-2 rounded-md bg-stone-950 px-3 py-1 text-xs font-semibold text-white hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {refundNotifyBusy ? "發送中" : "通知營運"}
                      </button>
                      <button
                        type="button"
                        onClick={dispatchRefundOperationsDigestIfDue}
                        disabled={refundPolicyBusy}
                        className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-1 text-xs font-semibold text-stone-900 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {refundPolicyBusy ? "判斷中" : "檢查是否需通知"}
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2 sm:grid-cols-4">
                    <RefundReportMetric label="待人工確認" value={refundReport.pendingEscalationCount} />
                    <RefundReportMetric label="已人工確認" value={refundReport.escalatedCount} />
                    <RefundReportMetric label="退款失敗" value={refundReport.failedCount} />
                    <RefundReportMetric label="逾時未完成" value={refundReport.stuckProcessingCount} />
                  </div>

                  {refundNotificationPolicy ? (
                    <div className="mt-3 flex flex-col gap-1 rounded-lg bg-white/80 px-3 py-2 text-xs font-semibold sm:flex-row sm:items-center sm:justify-between">
                      <span>
                        營運提醒間隔 {refundNotificationPolicy.cooldownMinutes} 分鐘；
                        {refundNotificationPolicy.shouldNotify ? "目前符合通知條件" : "目前不會重複通知"}
                      </span>
                      {refundNotificationPolicy.lastSentAt || refundNotificationPolicy.nextEligibleAt ? (
                        <span>
                          {refundNotificationPolicy.lastSentAt ? `上次 ${refundNotificationPolicy.lastSentAt}` : ""}
                          {refundNotificationPolicy.nextEligibleAt ? ` / 下次 ${refundNotificationPolicy.nextEligibleAt}` : ""}
                        </span>
                      ) : null}
                    </div>
                  ) : null}

                  {pendingRefundReportItems.length > 0 ? (
                    <div className="mt-3 grid gap-2">
                      {pendingRefundReportItems.map((item) => (
                        <div
                          key={`pending-refund-${item.id}`}
                          className="flex flex-col gap-1 rounded-lg bg-white/80 px-3 py-2 text-xs font-semibold sm:flex-row sm:items-center sm:justify-between"
                        >
                          <span className="font-semibold">{item.bookingCode}</span>
                          <span>
                            {refundReasonLabel(item.slaReason)} / {currency(item.deltaAmount)}
                            {item.settlementRequestedAt ? ` / ${item.settlementRequestedAt}` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : escalatedRefundReportItems.length > 0 ? (
                    <div className="mt-3 grid gap-2">
                      {escalatedRefundReportItems.map((item) => (
                        <div
                          key={`escalated-refund-${item.id}`}
                          className="flex flex-col gap-1 rounded-lg bg-white/80 px-3 py-2 text-xs font-semibold sm:flex-row sm:items-center sm:justify-between"
                        >
                          <span className="font-semibold">{item.bookingCode}</span>
                          <span>
                            已人工確認 {item.refundEscalatedAt}
                            {item.refundEscalationNote ? ` / ${item.refundEscalationNote}` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}

              <div className="grid gap-3 p-5">
                {depositAdjustments.map((adjustment) => {
                  const isTopUp = adjustment.adjustmentType === "TOP_UP";
                  const isRefund = adjustment.adjustmentType === "REFUND";
                  const settlementComplete = adjustment.settlementStatus === "COMPLETED";
                  const settlementPending = adjustment.settlementStatus === "PENDING";
                  const settlementProcessing = adjustment.settlementStatus === "PROCESSING";
                  const settlementFailed = adjustment.settlementStatus === "FAILED";
                  return (
                    <div
                      key={adjustment.id}
                      className="grid gap-4 rounded-lg border border-sky-100 bg-[#f7fbff] p-4 lg:grid-cols-[1fr_210px_170px]"
                    >
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                              isTopUp ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"
                            }`}
                          >
                            {ADJUSTMENT_TYPE_LABEL[adjustment.adjustmentType] ?? adjustment.adjustmentType}
                          </span>
                          <span className="rounded-md bg-white px-2.5 py-1 text-xs font-medium text-stone-600">
                            {ADJUSTMENT_SOURCE_LABEL[adjustment.source] ?? adjustment.source}
                          </span>
                          <span
                            className={`rounded-md px-2.5 py-1 text-xs font-medium ${settlementTone(adjustment.settlementStatus)}`}
                          >
                            {SETTLEMENT_STATUS_LABEL[adjustment.settlementStatus] ?? adjustment.settlementStatus}
                          </span>
                          <span className="text-xs font-semibold text-stone-500">{adjustment.bookingCode}</span>
                        </div>
                        <p className="mt-3 text-lg font-semibold">
                          {isTopUp ? "需補收" : "需退款"} {currency(adjustment.deltaAmount)}
                        </p>
                        <p className="mt-1 text-sm leading-6 text-stone-600">{adjustment.message}</p>
                        <p className="mt-2 text-xs font-semibold text-stone-500">
                          目標改單：{adjustment.proposedDate} {adjustment.proposedTime}，
                          {adjustment.proposedPeople} 人，訂金 {currency(adjustment.currentDepositTotal)} →{" "}
                          {currency(adjustment.proposedDepositTotal)}
                        </p>
                        {settlementComplete ? (
                          <p className="mt-2 text-xs font-semibold text-emerald-700">
                            金流：{adjustment.settlementProvider || "TAPPAY"} /{" "}
                            {adjustment.settlementTransId || "-"}，金額{" "}
                            {currency(adjustment.settlementAmount || adjustment.deltaAmount)}
                          </p>
                        ) : isTopUp || settlementProcessing || settlementFailed ? (
                          <label className="mt-3 flex max-w-sm flex-col gap-1 text-xs font-medium text-stone-600">
                            {isTopUp ? "補款交易編號" : "退款交易編號"}
                            <input
                              type="text"
                              value={settlementRefs[adjustment.id] ?? ""}
                              onChange={(event) =>
                                setSettlementRefs((current) => ({
                                  ...current,
                                  [adjustment.id]: event.target.value,
                                }))
                              }
                              placeholder={isTopUp ? "例如：補款交易編號" : "例如：退款交易編號"}
                              className="h-10 rounded-lg border border-sky-200 bg-white px-3 text-sm text-stone-900 outline-none focus:border-sky-500"
                            />
                          </label>
                        ) : (
                          <p className="mt-3 text-xs font-semibold text-stone-500">
                            先送出退款請求，等金流確認完成後才套用改單。
                          </p>
                        )}
                        {isRefund && (settlementProcessing || settlementFailed) ? (
                          adjustment.refundEscalatedAt ? (
                            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
                              已人工確認：{adjustment.refundEscalatedAt}
                              {adjustment.refundEscalationNote ? `，${adjustment.refundEscalationNote}` : ""}
                            </p>
                          ) : (
                            <label className="mt-3 flex max-w-sm flex-col gap-1 text-xs font-medium text-stone-600">
                              人工確認備註
                              <input
                                type="text"
                                value={refundEscalationNotes[adjustment.id] ?? ""}
                                onChange={(event) =>
                                  setRefundEscalationNotes((current) => ({
                                    ...current,
                                    [adjustment.id]: event.target.value,
                                  }))
                                }
                                placeholder="例：已通知金流客服協助處理"
                                className="h-10 rounded-lg border border-amber-200 bg-white px-3 text-sm text-stone-900 outline-none focus:border-amber-500"
                              />
                            </label>
                          )
                        ) : null}
                      </div>

                      <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
                        <IncidentFact label="目前訂位" value={`${adjustment.bookingDate} ${adjustment.bookingTime}`} />
                        <IncidentFact label="目前人數" value={`${adjustment.bookingPeople} 人`} />
                      </div>

                      <div className="flex flex-col items-start gap-2 lg:items-end lg:justify-center">
                        {settlementComplete ? (
                          <button
                            type="button"
                            onClick={() => resolveDepositAdjustment(adjustment)}
                            disabled={adjustmentBusyId === adjustment.id}
                            className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <CheckCheck className="h-4 w-4" />
                            {adjustmentBusyId === adjustment.id ? "套用中" : "套用改單"}
                          </button>
                        ) : isTopUp ? (
                          <button
                            type="button"
                            onClick={() => recordDepositSettlement(adjustment)}
                            disabled={adjustmentBusyId === adjustment.id}
                            className="inline-flex items-center gap-2 rounded-md bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <CreditCard className="h-4 w-4" />
                            {adjustmentBusyId === adjustment.id ? "記錄中" : "記錄補款完成"}
                          </button>
                        ) : isRefund && settlementPending ? (
                          <button
                            type="button"
                            onClick={() => requestRefundSettlement(adjustment)}
                            disabled={adjustmentBusyId === adjustment.id}
                            className="inline-flex items-center gap-2 rounded-md bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            <CreditCard className="h-4 w-4" />
                            {adjustmentBusyId === adjustment.id ? "建立中" : "送出退款請求"}
                          </button>
                        ) : isRefund && settlementProcessing ? (
                          <div className="flex flex-wrap justify-start gap-2 lg:justify-end">
                            <button
                              type="button"
                              onClick={() => reconcileRefundSettlement(adjustment, "COMPLETED")}
                              disabled={adjustmentBusyId === adjustment.id}
                              className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <CheckCheck className="h-4 w-4" />
                              {adjustmentBusyId === adjustment.id ? "確認中" : "退款成功"}
                            </button>
                            <button
                              type="button"
                              onClick={() => reconcileRefundSettlement(adjustment, "FAILED")}
                              disabled={adjustmentBusyId === adjustment.id}
                              className="inline-flex items-center gap-2 rounded-md border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              退款失敗
                            </button>
                          </div>
                        ) : isRefund && settlementFailed ? (
                          <div className="flex flex-wrap justify-start gap-2 lg:justify-end">
                            <button
                              type="button"
                              onClick={() => requestRefundSettlement(adjustment)}
                              disabled={adjustmentBusyId === adjustment.id}
                              className="inline-flex items-center gap-2 rounded-md bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {adjustmentBusyId === adjustment.id ? "建立中" : "重送請求"}
                            </button>
                            <button
                              type="button"
                              onClick={() => reconcileRefundSettlement(adjustment, "COMPLETED")}
                              disabled={adjustmentBusyId === adjustment.id}
                              className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              退款成功
                            </button>
                          </div>
                        ) : null}
                        {isRefund && (settlementProcessing || settlementFailed) ? (
                          adjustment.refundEscalatedAt ? (
                            <span className="rounded-md bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
                              已人工確認
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => escalateRefundAdjustment(adjustment)}
                              disabled={adjustmentBusyId === adjustment.id}
                              className="inline-flex items-center gap-2 rounded-md border border-amber-200 bg-white px-4 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <AlertTriangle className="h-4 w-4" />
                              {adjustmentBusyId === adjustment.id ? "處理中" : "人工確認"}
                            </button>
                          )
                        ) : null}
                        <span className="max-w-[190px] text-xs font-semibold text-stone-500 lg:text-right">
                          {settlementComplete
                            ? "已可安全套用改單"
                            : isTopUp
                              ? "需先完成補款"
                              : settlementFailed
                                ? "退款失敗，可重送請求"
                                : settlementProcessing
                                  ? "等待退款完成"
                                  : "需先送出退款請求"}
                        </span>
                      </div>
                    </div>
                  );
                })}

                {!adjustmentLoading && depositAdjustments.length === 0 && (
                  <div className="rounded-lg bg-stone-50 p-6 text-sm text-stone-500">
                    目前沒有待處理訂金差額。已付款訂位若改人數造成補收或退款，系統會先建立人工確認項目。
                  </div>
                )}
              </div>
            </section>

            <section
              id="slots"
              className={activeSection === "slots" ? "rounded-lg border border-stone-200 bg-white" : "hidden"}
            >
              <div className="flex flex-col gap-4 border-b border-stone-200 p-5 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2 className="text-xl font-semibold">可訂時段</h2>
                  <p className="mt-1 text-sm text-stone-500">
                    只調整可接待人數；已訂與剩餘位子由訂位流程自動計算。
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
                      className="h-11 rounded-lg border border-stone-200 px-3 text-stone-900"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm font-semibold text-stone-600">
                    桌型
                    <select
                      value={tableType}
                      onChange={(event) => setTableType(event.target.value)}
                      className="h-11 rounded-lg border border-stone-200 px-3 text-stone-900"
                    >
                      <option value="normal">一般座位</option>
                      <option value="bar">吧台</option>
                      <option value="private">包廂</option>
                    </select>
                  </label>
                </div>
              </div>

            {error && (
              <div className="mx-5 mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                {error}
              </div>
            )}
            {message && (
              <div className="mx-5 mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                {message}
              </div>
            )}

            <div className="p-5">
              {loading ? (
                <div className="rounded-lg bg-stone-50 p-8 text-center text-sm font-medium text-stone-500">
                  載入中...
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-stone-200">
                  <table className="w-full min-w-[760px] border-collapse text-sm">
                    <thead className="bg-stone-50 text-xs font-semibold uppercase tracking-normal text-stone-500">
                      <tr className="border-b border-stone-200">
                        <th className="px-4 py-3 text-left">時段</th>
                        <th className="px-4 py-3 text-right">容量</th>
                        <th className="px-4 py-3 text-right">已訂</th>
                        <th className="px-4 py-3 text-right">剩餘</th>
                        <th className="px-4 py-3 text-left">設定容量</th>
                        <th className="px-4 py-3 text-right">狀態</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-200 bg-white">
                      {slots.map((slot) => {
                        const health = slotHealth(slot);
                        const currentCapacity = capacities[slot.time] ?? slot.capacity;
                        return (
                          <tr key={`${slot.tableType}-${slot.time}`} className="hover:bg-[#fffdf8]">
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2 font-semibold text-stone-950 tabular-nums">
                                <Clock className="h-4 w-4 text-emerald-700" />
                                {slot.time}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-right font-medium tabular-nums text-stone-900">
                              {currentCapacity}
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums text-stone-600">
                              {slot.bookedCount}
                            </td>
                            <td className="px-4 py-3 text-right font-medium tabular-nums text-stone-900">
                              {slot.remaining}
                            </td>
                            <td className="px-4 py-3">
                              <label className="sr-only" htmlFor={`capacity-${slot.tableType}-${slot.time}`}>
                                設定 {slot.time} 可接待人數
                              </label>
                              <input
                                id={`capacity-${slot.tableType}-${slot.time}`}
                                type="number"
                                min={slot.bookedCount}
                                max={80}
                                value={currentCapacity}
                                onChange={(event) =>
                                  setCapacities((prev) => ({
                                    ...prev,
                                    [slot.time]: Number(event.target.value),
                                  }))
                                }
                                className="h-9 w-24 rounded-md border border-stone-200 px-3 text-sm font-medium text-stone-950"
                              />
                            </td>
                            <td className="px-4 py-3 text-right">
                              <span className={`inline-flex min-w-14 justify-center rounded-md px-3 py-1 text-xs font-semibold ${health.tone}`}>
                                {health.label}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex flex-col gap-3 border-t border-stone-200 p-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-stone-500">
                儲存後，Web / LINE 訂位與空位通知會讀同一份時段庫存。
              </p>
              <div className="flex gap-3">
                <Link
                  href="/ai"
                  className="rounded-md border border-stone-300 px-5 py-3 text-sm font-medium text-stone-700 hover:bg-stone-50"
                >
                  去測 AI 訂位
                </Link>
                <button
                  type="button"
                  onClick={saveSlots}
                  disabled={saving || !selectedShopId}
                  className="rounded-md bg-emerald-700 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? "儲存中..." : "儲存容量"}
                </button>
              </div>
            </div>
            </section>
          </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function MerchantWorkCard({
  title,
  description,
  count,
  href,
  onClick,
}: {
  title: string;
  description: string;
  count: string;
  href: string;
  onClick: () => void;
}) {
  return (
    <a
      href={href}
      onClick={onClick}
      className="rounded-lg border border-stone-200 bg-white p-5 transition hover:border-emerald-300 hover:bg-emerald-50/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-stone-950">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-stone-500">{description}</p>
        </div>
        <span className="shrink-0 rounded-lg bg-stone-100 px-3 py-1.5 text-sm font-semibold text-stone-700">
          {count}
        </span>
      </div>
    </a>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-3">
      <p className="text-xs font-medium text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-stone-950">{value}</p>
    </div>
  );
}

function RefundReportMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-h-[68px] rounded-lg bg-white/80 px-3 py-2">
      <p className="text-xs font-medium opacity-75">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function DemoNote({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="border-b border-stone-200 p-4 md:border-b-0 md:border-r last:md:border-r-0">
      <p className="font-semibold text-stone-900">{title}</p>
      <p className="mt-1 leading-6 text-stone-500">{detail}</p>
    </div>
  );
}

function IncidentFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white p-3">
      <p className="text-xs font-semibold text-stone-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-stone-950">{value}</p>
    </div>
  );
}
