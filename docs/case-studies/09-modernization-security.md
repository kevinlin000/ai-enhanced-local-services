# Case Study 09: 從代碼體檢到 Spring Boot 3 — 先把地基補好

**TL;DR** 一開始我也想直接做 AI 功能，但 code review 抓出安全、框架、硬編碼與死代碼問題。最後先做安全修補、Java 17、Spring Boot 3、Jakarta migration 與設定外部化。這篇記錄為什麼「不炫的地基工程」是後面 AI/LINE/付款能成立的前提。

**Tech:** Spring Boot / Java 17 / Spring Security / Redis / Flyway / code review  
**Repo:** `backend-java/`

## 1. 起點：功能很多，但風險也很多

早期後端已經有登入、店家、優惠券、秒殺、社群等功能。它能支撐產品化改造，但如果要變成 ByteBites，就必須先回答：

```text
這個系統能不能承受後面訂位、付款、LINE identity 的複雜度？
```

Code review 抓到幾個高風險問題：

- 秒殺 Lua 結果未判斷，庫存不足也可能回成功。
- logout 只清 ThreadLocal，Redis token 仍有效。
- 刪圖 endpoint 有 path traversal 風險。
- SMS code 直接寫 log。
- DB credential 硬編碼。
- Java / Spring Boot 版本偏舊。
- `javax.*` migration blocker。

## 2. 第一個抉擇：先修地基，不急著做 AI

這裡有一個產品誘惑：AI 功能最容易展示，安全和框架升級最不容易被看見。

但如果先做 AI，後面會遇到：

- 登入身份不可信。
- token lifecycle 不可信。
- 部署環境不可攜。
- 訂位/付款狀態建立在舊攔截器和硬編碼設定上。

所以我先處理：

- Java 17。
- Spring Boot 3.2。
- `javax` -> `jakarta`。
- Spring Security 正規化。
- DB / Redis / LINE 設定外部化。
- Flyway migration discipline。

## 3. 安全修補不是為了 checklist

例如 logout bug 表面上只是小問題，但如果後面加 LINE Login，使用者以為登出成功，token 卻仍可用，這會直接破壞信任。

path traversal 也是一樣。即使 demo 不會有人攻擊，公開 repo 裡保留這種問題，會讓評審對工程成熟度打折。

## 4. Spring Boot 3 的代價

升 Boot 3 不是改版本號而已：

- Java 17 是最低門檻。
- Servlet API 從 `javax.servlet` 變成 `jakarta.servlet`。
- 舊 starter 需要檢查相容性。
- Security config 要回到新寫法。
- 測試與 Flyway 都要重跑。

這不是功能 commit，但它讓專案從「能跑」走向「能繼續長」。

## 5. 結果

後續功能能建立在更乾淨的基礎上：

- LINE Login 不再靠手刻攔截器。
- JWT / Security / CORS 有清楚邊界。
- MySQL schema 變更由 Flyway 管理。
- Docker Compose 可以啟動 infra。
- 測試能以 Spring Boot 3 環境跑。

## 6. 我學到的事

**頂級作品不只展示亮點，也要能解釋地基。** 教授不一定會逐行看 security fix，但能聽出你有沒有工程判斷。

**先修平台，後面才不會每一步都踩雷。** AI、LINE、付款都是高耦合功能，地基不穩會放大所有問題。

**不炫的 commit 很重要。** 真正的工程成長常發生在沒截圖的地方。

## English Version

# Case Study 09: From Code Review to Spring Boot 3 — Fixing the Foundation First

The project started with many backend features, but the initial code review found serious risks: ignored Lua seckill results, ineffective logout, path traversal, SMS codes in logs, hardcoded credentials, outdated Java/Spring versions, and Jakarta migration blockers.

The tempting path was to build AI features first because they demo well. The better engineering choice was to fix the foundation: Java 17, Spring Boot 3.2, Spring Security, externalized configuration, and Flyway discipline.

This work was not glamorous, but it made later LINE Login, booking, payment, CORS, deployment, and testing work possible. The lesson: a serious AI product still needs serious backend hygiene.
