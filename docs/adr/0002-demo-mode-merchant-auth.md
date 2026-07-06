# ADR 0002：Demo 模式下商家與訂位 API 免認證，由 strict-mode 開關把守

## 狀態

已採納（Accepted）

## 背景

消費者端已有完整認證（LINE Login + JWT，Bearer header 與 HttpOnly cookie 雙軌）。
商家端（`/api/merchant/**`）沒有商家帳號模型：沒有 merchant user、沒有 shop 擁有權
對應表。要做真正的商家認證，需要 merchant onboarding（帳號、綁店、角色）——這是
一個完整的業務功能，不是加一個 filter 就能補的。

本專案的定位是面試作品與課程專題，demo 需要在無登入摩擦下展示商家後台
（incident queue、替代時段、押金退款）。

## 決策

- Demo 模式（`bytebites.security.strict-mode=false`，預設）下，
  `/api/merchant/**`、`/api/booking/**`、`/api/payment/**` 等展示路由免認證。
- `SecurityConfig.protectedDemoRoutes()` 明確列舉這批路由；
  `ProductionSecurityGuard` 在啟動時驗證：strict mode 關閉時不得作為 production 部署
  （並檢查 JWT secret 不是 dev 預設值）。
- strict mode 開啟後，同一批路由立即要求認證——切換是一個設定值，不是改 code。
- 商家 onboarding（帳號模型 + shop 擁有權）列為 v2 功能；在那之前前端
  `merchant/page.tsx` 固定以 demo 商家身分操作（`merchantToken = null`）。
- hmdp 遺留的免認證寫入端點（`/upload/**` 上傳/刪檔、`POST /voucher` 建券）
  已從 permitAll 移除：demo 不依賴它們，攻擊面白白開著。

## 後果

- 拿到 demo 網址的人可以操作商家後台與建立訂位——demo 期間可接受，
  但 ngrok 網址不應公開張貼；demo 結束即關閉 tunnel。
- 部署到任何長期環境前，必須開 strict mode 並完成 merchant onboarding。
- 面試敘事：安全邊界是「設計好的開關」而不是「還沒做」——
  `ProductionSecurityGuard` 的啟動驗證是證據。

---

## English Summary

**Decision**: In demo mode (`bytebites.security.strict-mode=false`, the default), merchant/booking/payment routes are intentionally unauthenticated because no merchant account model (onboarding, shop ownership, roles) exists yet — that is a full v2 feature, not a missing filter. The boundary is an engineered switch: enabling strict mode immediately requires authentication on the same route set, and `ProductionSecurityGuard` refuses to start with a production-like configuration while strict mode is off (or while the JWT secret is a dev default). Legacy unauthenticated write endpoints inherited from the upstream tutorial project (`/upload/**`, `POST /voucher`) were verified unused and removed from `permitAll`.

**Consequences**: anyone with the demo URL can operate the merchant console during a demo window — acceptable for showcasing, never for long-lived deployments. Before any persistent environment, enable strict mode and ship merchant onboarding.
