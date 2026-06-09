import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const root = join(import.meta.dirname, "..");

function loadCompiledAgentModules() {
  const workdir = mkdtempSync(join(tmpdir(), "bytebites-web-agent-"));
  const outDir = join(workdir, "out");
  const configPath = join(workdir, "tsconfig.json");
  writeFileSync(
    configPath,
    JSON.stringify(
      {
        compilerOptions: {
          target: "ES2020",
          module: "CommonJS",
          moduleResolution: "Node",
          strict: true,
          skipLibCheck: true,
          esModuleInterop: true,
          jsx: "react-jsx",
          baseUrl: root,
          paths: {
            "@/*": ["./*"],
          },
          rootDir: root,
          outDir,
        },
        files: [
          join(root, "lib/agentTypes.ts"),
          join(root, "lib/agentResponse.ts"),
          join(root, "lib/agentMessages.ts"),
          join(root, "lib/agentStream.ts"),
        ],
      },
      null,
      2,
    ),
  );

  try {
    execFileSync(process.execPath, [join(root, "node_modules/typescript/bin/tsc"), "--project", configPath], {
      cwd: root,
      stdio: "pipe",
    });
    const requireFromOut = createRequire(join(outDir, "index.cjs"));
    return {
      modules: {
        agentMessages: requireFromOut("./lib/agentMessages.js"),
        agentResponse: requireFromOut("./lib/agentResponse.js"),
      },
      cleanup: () => rmSync(workdir, { recursive: true, force: true }),
    };
  } catch (error) {
    rmSync(workdir, { recursive: true, force: true });
    throw error;
  }
}

test("agent final payload keeps selected shops, transaction, and scope note", () => {
  const { modules, cleanup } = loadCompiledAgentModules();
  try {
    const { agentFinalPayloadFromEvent } = modules.agentResponse;
    const transaction = {
      kind: "booking",
      success: true,
      status: "PENDING_PAYMENT",
      booking_code: "BK-20260609-001",
      shop_id: 2002,
      shop_name: "測試餐廳 B",
    };

    const payload = agentFinalPayloadFromEvent({
      type: "agent_end",
      answer: "推薦完成",
      recommended_shop_ids: [2002, 2001, 9999],
      scope_note: "中山區符合條件較少，我先擴大到台北漢堡店。",
      transaction,
      tool_result: {
        shops: [
          { shop_id: 2001, name: "測試餐廳 A", district: "中山", avgPrice: 500, mrtStation: "中山" },
          { shop_id: 2002, name: "測試餐廳 B", district: "大安", ai_summary: "適合約會。" },
          { shop_id: 2003, name: "測試餐廳 C", district: "信義" },
        ],
      },
    });

    assert.deepEqual(payload.recommendedShopIds, [2002, 2001, 9999]);
    assert.deepEqual(
      payload.shops.map((shop) => shop.shop_id),
      [2002, 2001, 2003],
    );
    assert.equal(payload.shops[1].mrt_station, "中山");
    assert.equal(payload.shops[1].price_per_person, "NT$ 500");
    assert.equal(payload.transaction, transaction);
    assert.equal(payload.scopeNote, "中山區符合條件較少，我先擴大到台北漢堡店。");
  } finally {
    cleanup();
  }
});

test("agent message model applies stream lifecycle and ignores duplicate done", () => {
  const { modules, cleanup } = loadCompiledAgentModules();
  try {
    const { applyAgentStreamEventToMessage } = modules.agentMessages;
    let message = { role: "ai", content: "", toolsUsed: [] };

    message = applyAgentStreamEventToMessage(message, {
      type: "tool_execution_start",
      name: "semantic_shop_search",
    });
    message = applyAgentStreamEventToMessage(message, {
      type: "message_update",
      content: "先幫你整理推薦。",
    });
    message = applyAgentStreamEventToMessage(message, {
      type: "agent_end",
      answer: "推薦完成",
      tools_used: ["semantic_shop_search"],
      tool_result: {
        scope_note: "附近符合條件較少，已擴大搜尋。",
        transaction: {
          kind: "booking",
          success: true,
          status: "PAID",
          booking_code: "BK-20260609-002",
        },
        agent_decision: { recommended_shop_ids: [3002, 3001] },
        shops: [
          { shop_id: 3001, name: "測試餐廳 A", district: "中山" },
          { shop_id: 3002, name: "測試餐廳 B", district: "大安" },
          { shop_id: 3003, name: "測試餐廳 C", district: "信義" },
        ],
      },
    });

    assert.equal(message.content, "推薦完成");
    assert.equal(message.done, true);
    assert.equal(message.hasShops, true);
    assert.equal(message.scopeNote, "附近符合條件較少，已擴大搜尋。");
    assert.equal(message.transaction.status, "PAID");
    assert.deepEqual(
      message.shops.map((shop) => shop.shop_id),
      [3002, 3001, 3003],
    );
    assert.deepEqual(message.toolsUsed, ["semantic_shop_search"]);
    assert.deepEqual(message.toolSteps, [
      { name: "semantic_shop_search", label: "比對餐廳資料", status: "active" },
    ]);

    const afterDuplicateDone = applyAgentStreamEventToMessage(message, {
      type: "done",
      answer: "重複 done 不應覆蓋",
      tool_result: { shops: [] },
    });

    assert.equal(afterDuplicateDone.content, "推薦完成");
    assert.equal(afterDuplicateDone, message);
  } finally {
    cleanup();
  }
});
