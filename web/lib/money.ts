export function formatCurrencyAbs(value: number) {
  return `NT$ ${Math.abs(Number(value ?? 0)).toLocaleString("zh-TW")}`;
}
