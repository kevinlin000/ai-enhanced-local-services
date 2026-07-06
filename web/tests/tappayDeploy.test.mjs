import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const repo = join(import.meta.dirname, "..", "..");

test("AWS web build requires TapPay public SDK credentials", () => {
  const dockerfile = readFileSync(join(repo, "web/Dockerfile"), "utf8");
  const compose = readFileSync(join(repo, "deploy/aws/docker-compose.prod.yml"), "utf8");
  const envExample = readFileSync(join(repo, "deploy/aws/.env.prod.example"), "utf8");

  for (const key of [
    "NEXT_PUBLIC_TAPPAY_APP_ID",
    "NEXT_PUBLIC_TAPPAY_APP_KEY",
    "NEXT_PUBLIC_TAPPAY_ENV",
  ]) {
    assert.match(dockerfile, new RegExp(`ARG ${key}`));
    assert.ok(compose.includes(key + ": ${" + key + ":?required}"));
    assert.match(envExample, new RegExp(`^${key}=`, "m"));
  }

  const webService = compose.slice(compose.indexOf("  web:"), compose.indexOf("volumes:"));
  assert.doesNotMatch(webService, /TAPPAY_PARTNER_KEY|TAPPAY_MERCHANT_CREDITCARD/);
});
