import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("app shell keeps navigation chrome quiet and workspace-like", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.doesNotMatch(source, /\b(?:font-black|font-bold|rounded-2xl|rounded-3xl|shadow-sm|shadow-lg|shadow-xl|shadow-2xl)\b/);
  assert.doesNotMatch(source, /\b(?:soon|disabled)\b/i);
  assert.doesNotMatch(source, /後續加入|敬請期待|待開放|即將推出|即將上線/);
  assert.doesNotMatch(source, /bg-\[#(?:f7f3ec|f6f1e8|e9ddbd)\]/);
  assert.match(source, /bb-premium-page/);
  assert.match(source, /bb-shell-active/);
  assert.match(source, /text-3xl font-semibold tracking-normal/);
});

test("app shell keeps AI search as a toolbar control", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.match(source, /w-\[260px\].*rounded-lg.*text-sm font-medium/s);
  assert.doesNotMatch(source, /w-\[280px\].*rounded-full.*font-bold/s);
});

test("merchant shell exposes flash deals as primary operations nav", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.match(source, /label:\s*"限時餐券"[\s\S]*href:\s*"\/merchant#flash-deals"/);
  assert.match(source, /TicketPercent/);
});

test("app shell constrains remote profile photos", () => {
  const shell = readFileSync(join(root, "components/AppShell.tsx"), "utf8");
  const css = readFileSync(join(root, "app/globals.css"), "utf8");

  assert.match(shell, /bb-shell-avatar/);
  assert.match(shell, /style=\{\{ width:\s*48,\s*height:\s*48,\s*maxWidth:\s*48,\s*maxHeight:\s*48 \}\}/);
  assert.match(shell, /width=\{48\}/);
  assert.match(shell, /height=\{48\}/);
  assert.match(shell, /bb-shell-avatar-image/);
  assert.match(shell, /objectFit:\s*"cover"/);
  assert.match(css, /\.bb-shell-avatar\s*\{[^}]*inline-size:\s*3rem;[^}]*block-size:\s*3rem;/s);
  assert.match(css, /\.bb-shell-avatar-image\s*\{[^}]*object-fit:\s*cover;/s);
});
