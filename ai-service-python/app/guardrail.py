"""Lightweight prompt injection defense and output filter."""
import re


INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|above|all)\s+(instructions?|prompts?|rules?)",
    r"忽略\s*(上述|之前|前面|所有)\s*(指[令示]|規則|提示)",
    r"forget\s+(everything|all|previous)",
    r"忘記\s*(前面|之前|所有)",
    r"system\s*prompt",
    r"system\s*:",
    r"you\s+are\s+now\s+",
    r"你現在是",
    r"pretend\s+(you|to)",
    r"假裝你是",
    r"act\s+as\s+",
    r"扮演",
    r"jailbreak",
    r"DAN\s+mode",
    r"<\s*\|.*?\|\s*>",
]

OUTPUT_BLOCKLIST = [
    "system prompt",
    "system instruction",
    "system_instruction",
    "我是一個",
    "I am an AI",
    "ignore previous",
]


class GuardrailViolation(Exception):
    pass


def check_input(query: str) -> None:
    """Raise GuardrailViolation if query looks malicious."""
    if not query or not query.strip():
        raise GuardrailViolation("empty query")
    if len(query) > 500:
        raise GuardrailViolation("query too long")

    lower = query.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            raise GuardrailViolation(f"injection pattern detected: {pattern}")


def filter_output(answer: str) -> str:
    """Redact suspicious content from LLM output."""
    if not answer:
        return answer

    lower = answer.lower()
    for blocked in OUTPUT_BLOCKLIST:
        if blocked.lower() in lower:
            return "抱歉，我只能協助查詢店家資訊。"

    return answer
