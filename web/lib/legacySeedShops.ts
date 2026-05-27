const LEGACY_SEED_SHOP_IDS = new Set<number>([
  10001, 10002, 10003, 10004, 10005,
  10006, 10007, 10008, 10009, 10010,
  10011, 10012, 10013, 10014, 10015,
  10016, 10017, 10018, 10019, 10020,
  10021, 10022, 10023, 10024, 10025,
]);

export function isLegacySeedShop(shopId: number) {
  return LEGACY_SEED_SHOP_IDS.has(shopId);
}

export function getLegacySeedShopIds() {
  return [...LEGACY_SEED_SHOP_IDS];
}
