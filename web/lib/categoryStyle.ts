import type { ComponentType } from "react";
import {
  Beef,
  Coffee,
  CupSoda,
  Drumstick,
  Fish,
  Flame,
  IceCream2,
  Moon,
  Sandwich,
  ShoppingBag,
  Soup,
  Utensils,
  Star,
} from "lucide-react";

type Style = {
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  gradient: string;
  accentBg: string;
  label: string;
};

const MAP: Record<string, Style> = {
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
  cafe: {
    icon: Coffee,
    gradient: "from-amber-100 to-stone-50",
    accentBg: "bg-amber-50",
    label: "咖啡廳",
  },
  japanese: {
    icon: Fish,
    gradient: "from-rose-100 to-red-50",
    accentBg: "bg-rose-50",
    label: "日式料理",
  },
  korean: {
    icon: Utensils,
    gradient: "from-red-100 to-orange-50",
    accentBg: "bg-red-50",
    label: "韓式料理",
  },
  izakaya: {
    icon: Drumstick,
    gradient: "from-yellow-100 to-amber-50",
    accentBg: "bg-yellow-50",
    label: "居酒屋",
  },
  hotpot: {
    icon: Flame,
    gradient: "from-red-100 to-rose-50",
    accentBg: "bg-red-50",
    label: "火鍋",
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
  yakiniku: {
    icon: Flame,
    gradient: "from-orange-100 to-amber-50",
    accentBg: "bg-orange-50",
    label: "日式燒肉",
  },
  omakase: {
    icon: Fish,
    gradient: "from-slate-100 to-blue-50",
    accentBg: "bg-slate-50",
    label: "無菜單料理",
  },
  steakhouse: {
    icon: Beef,
    gradient: "from-red-100 to-orange-50",
    accentBg: "bg-red-50",
    label: "牛排館",
  },
  european: {
    icon: Utensils,
    gradient: "from-blue-100 to-indigo-50",
    accentBg: "bg-blue-50",
    label: "義法 / 西式",
  },
  chinese: {
    icon: Soup,
    gradient: "from-red-100 to-yellow-50",
    accentBg: "bg-red-50",
    label: "中式料理",
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
  default: {
    icon: Utensils,
    gradient: "from-stone-100 to-stone-50",
    accentBg: "bg-stone-50",
    label: "餐廳",
  },
};

const ID_TO_SLUG: Record<number, string> = {
  // legacy 1xxx
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
  // 2xxx
  2001: "hotpot",
  2002: "yakiniku",
  2003: "izakaya",
  2004: "japanese",
  2005: "omakase",
  2006: "steakhouse",
  2007: "european",
  2008: "chinese",
  2009: "korean",
  2010: "brunch",
  2011: "fine-dining",
  2012: "cafe-premium",
};

export function getCategoryStyle(slug: string): Style {
  return MAP[slug] ?? MAP.default;
}

export function getSlugByTypeId(typeId?: number): string | null {
  if (!typeId) return null;
  return ID_TO_SLUG[typeId] ?? null;
}

export function getStyleByTypeId(typeId?: number): Style {
  if (!typeId) return getCategoryStyle("default");
  return getCategoryStyle(ID_TO_SLUG[typeId] ?? "default");
}
