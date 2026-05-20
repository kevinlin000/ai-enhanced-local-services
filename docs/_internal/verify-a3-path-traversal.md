# 驗證報告：A3 路徑穿越防禦（commit 0de9676）

## 關鍵機制說明

- 使用 `toRealPath()`：解析符號連結 + 規範化路徑，但要求檔案**必須存在**，不存在則拋 `NoSuchFileException`。
- `targetPath.startsWith(rootPath)` 使用 `Path` 物件比對，按路徑組件比較，不存在字串前綴混淆問題（`/upload` ≠ `/uploads`）。

## Payload 逐項判斷

| # | Payload | 判斷結果 | 原因 |
|---|---------|---------|------|
| 1 | `../../../etc/passwd` | **擋住** | `toRealPath()` 解析成實際路徑；若存在則 `startsWith` 失敗回 `非法檔名`；若不存在則 `NoSuchFileException` → `檔案不存在`。 |
| 2 | `..\\..\\windows\\system32\\config` | **擋住（Linux/Mac）** | 反斜線是合法檔名字元而非路徑分隔符，組合出不存在的路徑 → `NoSuchFileException`。此行為依賴例外，非主動攔截。Windows 環境下 `toRealPath()` 解析後 `startsWith` 亦可擋住。 |
| 3 | `/etc/passwd` | **擋住** | Java `Paths.get(DIR, "/etc/passwd")` 做字串拼接（非 `resolve()`），結果為 `DIR//etc/passwd` → 規範化為 `DIR/etc/passwd`，在根目錄內；該路徑不存在 → `NoSuchFileException`。 |
| 4 | `normal.jpg` | **通過（正常）** | `toRealPath()` 成功，`startsWith` 通過，非目錄，允許刪除。 |
| 5 | `./normal.jpg` | **通過（正常）** | `toRealPath()` 規範化 `.` 後等同 `normal.jpg`，行為同上。 |
| 6 | `subdir/../../../etc/passwd` | **擋住** | `toRealPath()` 解析 `..` 後得到根目錄外路徑；若存在則 `startsWith` 失敗；若不存在則 `NoSuchFileException`。 |
| 7 | `""` 或 `null` | **擋住** | 空字串：`Paths.get(DIR, "")` = `DIR`，`toRealPath()` 成功，`isDirectory()` → true → `非法檔名`。`null`：Spring `@RequestParam` 預設 `required=true`，null 參數在框架層即被攔截，不會進入方法。 |

## 額外檢查

- **`toRealPath()` vs `toAbsolutePath().normalize()`**：`toRealPath()` 解析符號連結（符號連結逃脫攻擊無效），`toAbsolutePath().normalize()` 不解析符號連結（可能被繞過）；目前使用 `toRealPath()`，防禦更嚴。
- **上傳根目錄不存在**：`rootPath = Paths.get(DIR).toRealPath()` 拋 `NoSuchFileException`，被 catch 回傳 `檔案不存在`，不會 crash，但錯誤訊息略有誤導。
- **`startsWith()` 物件比對**：確認為 `Path` 物件比對，無字串前綴混淆風險（`/upload` 不會前綴匹配 `/uploads`）。

## 結論：通過
