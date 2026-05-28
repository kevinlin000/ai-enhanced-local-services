import type { ComponentType } from "react";
import {
  Beef,
  Coffee,
  CupSoda,
  Drumstick,
  Fish,
  Flame,
  IceCream2,
  Leaf,
  Moon,
  Sandwich,
  ShoppingBag,
  Soup,
  Utensils,
  Star,
} from "lucide-react";
import { getSlugByTypeId as taxonomySlug } from "./taxonomy";

type Style = {
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  gradient: string;
  accentBg: string;
  label: string;
};

const MAP: Record<string, Style> = {
  // ── legacy 1xxx slugs (kept for backward compat) ──────────────────────────
  "beef-noodle": {
    icon: Beef,
    gradient: "from-orange-100 to-red-50",
    accentBg: "bg-orange-50",
    label: "牛肉麵",
  },
  "lu-wei": {
    icon: Soup,
    gradient: "from-amber-100 to-orange-50",
    accentBg: "bg-amber-50",
    label: "滷味",
  },
  "bubble-tea": {
    icon: CupSoda,
    gradient: "from-stone-100 to-amber-50",
    accentBg: "bg-stone-50",
    label: "手搖飲",
  },
  "night-market": {
    icon: Moon,
    gradient: "from-violet-100 to-pink-50",
    accentBg: "bg-violet-50",
    label: "夜市小吃",
  },
  breakfast: {
    icon: Sandwich,
    gradient: "from-yellow-100 to-orange-50",
    accentBg: "bg-yellow-50",
    label: "早餐",
  },
  bento: {
    icon: ShoppingBag,
    gradient: "from-emerald-100 to-teal-50",
    accentBg: "bg-emerald-50",
    label: "便當",
  },
  dessert: {
    icon: IceCream2,
    gradient: "from-pink-100 to-rose-50",
    accentBg: "bg-pink-50",
    label: "甜點",
  },
  // ── canonical 2xxx slugs (taxonomy.json) ─────────────────────────────────
  hotpot: {
    icon: Flame,
    gradient: "from-red-100 to-rose-50",
    accentBg: "bg-red-50",
    label: "火鍋",
  },
  chinese: {
    icon: Soup,
    gradient: "from-red-100 to-yellow-50",
    accentBg: "bg-red-50",
    label: "中式料理",
  },
  american: {
    icon: Sandwich,
    gradient: "from-green-100 to-emerald-50",
    accentBg: "bg-green-50",
    label: "美式料理",
  },
  euro: {
    icon: Utensils,
    gradient: "from-blue-100 to-indigo-50",
    accentBg: "bg-blue-50",
    label: "義法料理",
  },
  cafe: {
    icon: Coffee,
    gradient: "from-amber-100 to-stone-50",
    accentBg: "bg-amber-50",
    label: "咖啡/甜點",
  },
  yakiniku: {
    icon: Flame,
    gradient: "from-orange-100 to-amber-50",
    accentBg: "bg-orange-50",
    label: "日式燒肉",
  },
  buffet: {
    icon: Star,
    gradient: "from-purple-100 to-violet-50",
    accentBg: "bg-purple-50",
    label: "自助餐",
  },
  vegetarian: {
    icon: Leaf,
    gradient: "from-green-100 to-teal-50",
    accentBg: "bg-green-50",
    label: "素食",
  },
  izakaya: {
    icon: Drumstick,
    gradient: "from-yellow-100 to-amber-50",
    accentBg: "bg-yellow-50",
    label: "居酒屋",
  },
  japanese: {
    icon: Fish,
    gradient: "from-rose-100 to-red-50",
    accentBg: "bg-rose-50",
    label: "日式料理",
  },
  // ── aliases kept for any existing code referencing old slugs ─────────────
  korean: {
    icon: Utensils,
    gradient: "from-red-100 to-orange-50",
    accentBg: "bg-red-50",
    label: "韓式料理",
  },
  brunch: {
    icon: Sandwich,
    gradient: "from-green-100 to-emerald-50",
    accentBg: "bg-green-50",
    label: "美式料理",
  },
  "fine-dining": {
    icon: Star,
    gradient: "from-purple-100 to-violet-50",
    accentBg: "bg-purple-50",
    label: "高級餐廳",
  },
  "cafe-premium": {
    icon: Coffee,
    gradient: "from-amber-100 to-yellow-50",
    accentBg: "bg-amber-50",
    label: "甜點 / 咖啡",
  },
  european: {
    icon: Utensils,
    gradient: "from-blue-100 to-indigo-50",
    accentBg: "bg-blue-50",
    label: "義法 / 西式",
  },
  default: {
    icon: Utensils,
    gradient: "from-stone-100 to-stone-50",
    accentBg: "bg-stone-50",
    label: "餐廳",
  },
};

// legacy 1xxx only — 2xxx resolved via taxonomy.ts
const LEGACY_ID_TO_SLUG: Record<number, string> = {
  1001: "beef-noodle",
  1002: "lu-wei",
  1003: "bubble-tea",
  1004: "night-market",
  1005: "cafe",
  1006: "japanese",
  1007: "korean",
  1008: "izakaya",
  1009: "hotpot",
  1010: "breakfast",
  1011: "bento",
  1012: "dessert",
};

export function getCategoryStyle(slug: string): Style {
  return MAP[slug] ?? MAP.default;
}

export function getSlugByTypeId(typeId?: number): string | null {
  if (!typeId) return null;
  return taxonomySlug(typeId) ?? LEGACY_ID_TO_SLUG[typeId] ?? null;
}

export function getStyleByTypeId(typeId?: number): Style {
  const slug = getSlugByTypeId(typeId);
  return getCategoryStyle(slug ?? "default");
}
