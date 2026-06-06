from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx


CLARIFY_RE = re.compile(r"請問|想在哪|哪一區|日期|時段|人數|預算|偏好|告訴我")


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def parse_sse_line(line: str) -> dict | None:
    if not line.startswith("data:"):
        return None
    payload = line.removeprefix("data:").strip()
    if not payload:
        return None
    return json.loads(payload)


def run_case(client: httpx.Client, base_url: str, case: dict, timeout: float) -> dict:
    answer_chunks: list[str] = []
    events: list[dict] = []
    tools: list[str] = []
    done_payload: dict = {}
    session_id = f"eval-{case['id']}-{uuid4().hex[:8]}"

    try:
        with client.stream(
            "POST",
            f"{base_url.rstrip('/')}/api/ai/agent/stream",
            json={"query": case["query"], "session_id": session_id},
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                event = parse_sse_line(line)
                if not event:
                    continue
                events.append(event)
                event_type = event.get("type")
                if event_type == "chunk":
                    answer_chunks.append(str(event.get("content", "")))
                elif event_type == "tool":
                    tools.append(str(event.get("name", "")))
                elif event_type == "done":
                    done_payload = event
                    tools.extend(str(tool) for tool in event.get("tools_used", []) if tool not in tools)
                    if event.get("answer"):
                        answer_chunks = [str(event["answer"])]
                elif event_type == "error":
                    return {
                        "id": case["id"],
                        "query": case["query"],
                        "passed": False,
                        "failures": [str(event.get("message", "stream error"))],
                        "tools": tools,
                        "answer": "".join(answer_chunks),
                        "done": done_payload,
                    }
    except Exception as exc:  # noqa: BLE001 - eval runner should report all transport failures.
        return {
            "id": case["id"],
            "query": case["query"],
            "passed": False,
            "failures": [f"request failed: {exc}"],
            "tools": tools,
            "answer": "".join(answer_chunks),
            "done": done_payload,
        }

    answer = "".join(answer_chunks)
    failures = evaluate_case(case, answer, tools, done_payload)
    return {
        "id": case["id"],
        "query": case["query"],
        "passed": not failures,
        "failures": failures,
        "tools": tools,
        "answer": answer,
        "done": done_payload,
    }


def evaluate_case(case: dict, answer: str, tools: list[str], done_payload: dict) -> list[str]:
    failures: list[str] = []
    tool_set = set(tools)

    for tool in case.get("must_use_tools", []):
        if tool not in tool_set:
            failures.append(f"missing required tool: {tool}")

    for tool in case.get("must_not_use_tools", []):
        if tool in tool_set:
            failures.append(f"forbidden tool used: {tool}")

    if terms := case.get("must_contain_any"):
        if not any(term in answer for term in terms):
            failures.append(f"answer contains none of: {terms}")

    for term in case.get("must_contain_all", []):
        if term not in answer:
            failures.append(f"answer missing required term: {term}")

    for term in case.get("must_not_contain", []):
        if term in answer:
            failures.append(f"answer contains forbidden term: {term}")

    if case.get("expect_clarifying") and not CLARIFY_RE.search(answer):
        failures.append("expected clarifying question/framing")

    if case.get("expect_table") and not ("|" in answer and answer.count("|") >= 6):
        failures.append("expected markdown-style comparison table")

    if case.get("expect_clarifying_or_recommendation"):
        recommended = done_payload.get("recommended_shop_ids") or []
        has_recommendation = bool(recommended) or any(term in answer for term in ("推薦", "整理", "選擇"))
        if not (CLARIFY_RE.search(answer) or has_recommendation):
            failures.append("expected clarifying question or recommendation")

    recommended_count = len(done_payload.get("recommended_shop_ids") or [])
    if "min_recommended_count" in case and recommended_count < int(case["min_recommended_count"]):
        failures.append(f"recommended count {recommended_count} < {case['min_recommended_count']}")
    if "max_recommended_count" in case and recommended_count > int(case["max_recommended_count"]):
        failures.append(f"recommended count {recommended_count} > {case['max_recommended_count']}")

    return failures


def write_reports(results: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for result in results if result["passed"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    (output_dir / "agent_concierge_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Agent Concierge Eval Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Passed: `{passed}/{len(results)}`",
        "",
        "| Case | Result | Tools | Failures |",
        "|---|---:|---|---|",
    ]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        failures = "; ".join(result["failures"]) or "-"
        tools = ", ".join(result["tools"]) or "-"
        lines.append(f"| `{result['id']}` | {status} | {tools} | {failures} |")
    (output_dir / "agent_concierge_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run inline-style concierge evals against the Agent SSE endpoint.")
    parser.add_argument("dataset", nargs="?", default="evals/agent_concierge_cases.jsonl")
    parser.add_argument("--base-url", default=os.getenv("AI_AGENT_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--output-dir", default="evals")
    args = parser.parse_args()

    cases = load_cases(Path(args.dataset))
    with httpx.Client() as client:
        results = [run_case(client, args.base_url, case, args.timeout) for case in cases]

    write_reports(results, Path(args.output_dir))
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['id']} tools={','.join(result['tools']) or '-'}")
        for failure in result["failures"]:
            print(f"  - {failure}")

    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
