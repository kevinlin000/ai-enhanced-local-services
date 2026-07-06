import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("demo guide exposes the operational demo route without date labels", () => {
  const page = readFileSync(join(root, "app/demo/page.tsx"), "utf8");
  const shell = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.match(shell, /Demo 導覽/);
  assert.match(page, /五分鐘看懂 ByteBites/);
  assert.match(page, /\/my-bookings/);
  assert.match(page, /\/merchant/);
  assert.match(page, /\/notifications/);
  assert.doesNotMatch(page, /6\/12|6-12|新增/);
});

test("public pages speak to visitors, not to the presenter", () => {
  // /demo 與 /showcase 是公開頁面：不得出現對作者的排練指令
  // （「錄影」「上台」）或把觀眾寫進文案（「面試官」「教授」「觀眾」）。
  for (const file of ["app/demo/page.tsx", "app/showcase/page.tsx"]) {
    const source = readFileSync(join(root, file), "utf8");
    assert.doesNotMatch(source, /錄影|上台|面試官|教授|觀眾|報告時/, file);
  }
});

test("showcase metrics stay tied to verifiable numbers", () => {
  const source = readFileSync(join(root, "app/showcase/page.tsx"), "utf8");
  // 599 家店與測試總數要跟 README / footer 一致；出現湊數型 metric 視為回歸
  assert.match(source, /599/);
  assert.match(source, /341/);
  assert.match(source, /15\/15/);
  assert.doesNotMatch(source, /500\+/);
});
