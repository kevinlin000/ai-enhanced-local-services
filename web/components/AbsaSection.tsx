"use client";

import { useState } from "react";
import type { AbsaAspect, AbsaEvidence } from "@/lib/api";

const ASPECT_LABELS: Record<string, string> = {
  dishes: "菜色",
  service: "服務",
  environment: "環境",
  price: "價格",
};

const SENTIMENT_CONFIG: Record<string, { label: string; chip: string }> = {
  positive: { label: "正面", chip: "bg-green-100 text-green-800" },
  negative: { label: "負面", chip: "bg-red-100 text-red-800" },
  mixed: { label: "褒貶不一", chip: "bg-amber-100 text-amber-800" },
  neutral: { label: "中性", chip: "bg-stone-100 text-stone-600" },
};

const CONFIDENCE_CONFIG: Record<string, { label: string; chip: string }> = {
  high: { label: "高信心", chip: "bg-blue-50 text-blue-700" },
  medium: { label: "中信心", chip: "bg-sky-50 text-sky-700" },
  low: { label: "低信心", chip: "bg-gray-50 text-gray-500" },
};

function EvidenceList({ items, polarity }: { items: AbsaEvidence[]; polarity: "positive" | "negative" }) {
  const icon = polarity === "positive" ? "✓" : "✕";
  const iconClass = polarity === "positive" ? "text-green-600" : "text-red-500";
  const termChip = polarity === "positive"
    ? "bg-green-50 text-green-700 border border-green-200"
    : "bg-red-50 text-red-700 border border-red-200";

  return (
    <ul className="space-y-3">
      {items.map((ev, i) => (
        <li key={i} className="flex gap-2.5">
          <span className={`mt-0.5 text-xs font-bold shrink-0 ${iconClass}`}>{icon}</span>
          <div className="space-y-1.5">
            <p className="text-sm leading-relaxed text-foreground">{ev.claim}</p>
            {ev.concrete_terms.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {ev.concrete_terms.map((term) => (
                  <span key={term} className={`text-xs px-2 py-0.5 rounded-full ${termChip}`}>
                    {term}
                  </span>
                ))}
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function leanLabel(pos: number, neg: number): string | null {
  if (pos === 0 && neg === 0) return null;
  if (pos === 0) return "👎偏負面";
  if (neg === 0) return "👍偏正面";
  const ratio = pos / neg;
  if (ratio > 2) return "👍偏正面";
  if (ratio < 0.5) return "👎偏負面";
  return "🤝平衡";
}

function AspectCard({ aspect }: { aspect: AbsaAspect }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const sentiment = SENTIMENT_CONFIG[aspect.sentiment] ?? SENTIMENT_CONFIG.neutral;
  const confidence = CONFIDENCE_CONFIG[aspect.confidence] ?? CONFIDENCE_CONFIG.medium;
  const posCount = aspect.positive_evidence?.length ?? 0;
  const negCount = aspect.negative_evidence?.length ?? 0;
  const hasEvidence = posCount > 0 || negCount > 0;
  const lean = leanLabel(posCount, negCount);

  return (
    <div className="rounded-2xl border bg-background overflow-hidden">
      <div className="px-5 pt-5 pb-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-base font-semibold">
            {ASPECT_LABELS[aspect.aspect] ?? aspect.aspect}
          </span>
          <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${sentiment.chip}`}>
            {sentiment.label}
          </span>
          <span className={`text-xs px-2.5 py-0.5 rounded-full ${confidence.chip}`}>
            {confidence.label}
          </span>
          {hasEvidence && (
            <span className="text-xs text-muted-foreground">
              正{posCount} / 負{negCount}
            </span>
          )}
          {lean && (
            <span className="text-xs text-muted-foreground font-medium">{lean}</span>
          )}
          {aspect.mention_count != null && (
            <span className="text-xs text-muted-foreground ml-auto">
              基於 {aspect.mention_count} 則評論
            </span>
          )}
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{aspect.summary}</p>
      </div>

      {hasEvidence && (
        <>
          <div className="border-t mx-0" />
          <div className="px-5 py-3">
            <button
              type="button"
              onClick={() => setShowEvidence((v) => !v)}
              className="text-sm font-medium text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              查看根據
              <span className="text-xs">{showEvidence ? "▲" : "▼"}</span>
            </button>
          </div>

          {showEvidence && (
            <div className="px-5 pb-5 space-y-5 border-t">
              {posCount > 0 && (
                <div className="pt-4">
                  <div className="text-xs font-semibold text-green-700 mb-3 uppercase tracking-normal">
                    正面根據 ({posCount})
                  </div>
                  <EvidenceList items={aspect.positive_evidence!} polarity="positive" />
                </div>
              )}
              {negCount > 0 && (
                <div className={posCount > 0 ? "pt-2 border-t" : "pt-4"}>
                  <div className="text-xs font-semibold text-red-600 mb-3 uppercase tracking-normal">
                    負面根據 ({negCount})
                  </div>
                  <EvidenceList items={aspect.negative_evidence!} polarity="negative" />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

type Props = {
  aspects: AbsaAspect[];
  charHitRate?: number;
  semanticHitRate?: number;
};

export function AbsaSection({ aspects, charHitRate, semanticHitRate }: Props) {
  const charPct = charHitRate != null ? `${Math.round(charHitRate * 100)}%` : null;
  const semPct = semanticHitRate != null ? `${Math.round(semanticHitRate * 100)}%` : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">餐廳特色</h3>
        {(charPct || semPct) && (
          <span
            className="text-xs text-muted-foreground cursor-default"
            title="根據原始評論文字驗證 AI 描述的準確度"
          >
            準確度：字符 {charPct ?? "—"} · 語意 {semPct ?? "—"}
          </span>
        )}
      </div>
      <div className="space-y-4">
        {aspects.map((asp) => (
          <AspectCard key={asp.aspect} aspect={asp} />
        ))}
      </div>
    </div>
  );
}
