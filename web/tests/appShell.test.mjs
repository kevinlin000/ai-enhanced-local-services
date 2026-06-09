import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

test("app shell keeps navigation chrome quiet and workspace-like", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.doesNotMatch(source, /\b(?:font-black|font-bold|rounded-2xl|rounded-3xl|shadow-sm|shadow-lg|shadow-xl|shadow-2xl)\b/);
  assert.doesNotMatch(source, /bg-\[#(?:f7f3ec|f6f1e8|e9ddbd)\]/);
  assert.match(source, /bg-muted text-foreground/);
  assert.match(source, /text-3xl font-semibold tracking-normal/);
});

test("app shell keeps AI search as a toolbar control", () => {
  const source = readFileSync(join(root, "components/AppShell.tsx"), "utf8");

  assert.match(source, /w-\[260px\].*rounded-lg.*text-sm font-medium/s);
  assert.doesNotMatch(source, /w-\[280px\].*rounded-full.*font-bold/s);
});
