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
} from "lucide-react";

type Style = {
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  gradient: string;
  accentBg: string;
};

const MAP: Record<string, Style> = {
  "beef-noodle": {
    icon: Beef,
    gradient: "from-orange-100 to-red-50",
    accentBg: "bg-orange-50",
  },
  "lu-wei": {
    icon: Soup,
    gradient: "from-amber-100 to-orange-50",
    accentBg: "bg-amber-50",
  },
  "bubble-tea": {
    icon: CupSoda,
    gradient: "from-stone-100 to-amber-50",
    accentBg: "bg-stone-50",
  },
  "night-market": {
    icon: Moon,
    gradient: "from-violet-100 to-pink-50",
    accentBg: "bg-violet-50",
  },
  cafe: {
    icon: Coffee,
    gradient: "from-amber-100 to-stone-50",
    accentBg: "bg-amber-50",
  },
  japanese: {
    icon: Fish,
    gradient: "from-rose-100 to-red-50",
    accentBg: "bg-rose-50",
  },
  korean: {
    icon: Utensils,
    gradient: "from-red-100 to-orange-50",
    accentBg: "bg-red-50",
  },
  izakaya: {
    icon: Drumstick,
    gradient: "from-yellow-100 to-amber-50",
    accentBg: "bg-yellow-50",
  },
  hotpot: {
    icon: Flame,
    gradient: "from-red-100 to-rose-50",
    accentBg: "bg-red-50",
  },
  breakfast: {
    icon: Sandwich,
    gradient: "from-yellow-100 to-orange-50",
    accentBg: "bg-yellow-50",
  },
  bento: {
    icon: ShoppingBag,
    gradient: "from-emerald-100 to-teal-50",
    accentBg: "bg-emerald-50",
  },
  dessert: {
    icon: IceCream2,
    gradient: "from-pink-100 to-rose-50",
    accentBg: "bg-pink-50",
  },
  default: {
    icon: Utensils,
    gradient: "from-stone-100 to-stone-50",
    accentBg: "bg-stone-50",
  },
};

const ID_TO_SLUG: Record<number, string> = {
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

export function getStyleByTypeId(typeId?: number): Style {
  if (!typeId) return getCategoryStyle("default");
  return getCategoryStyle(ID_TO_SLUG[typeId] ?? "default");
}
