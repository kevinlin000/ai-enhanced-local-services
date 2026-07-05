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
    # 「角色扮演」是正當餐廳主題詞（cosplay 主題店），只擋指令式的「扮演」
    r"(?<!角色)扮演",
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
    """Redact suspicious content from LLM output.

    只移除含有 blocklist 字眼的句子，保留其餘正常內容；
    整段都被移除時才退回道歉句，避免一個字眼毀掉整個回答。
    """
    if not answer:
        return answer

    def is_blocked(sentence: str) -> bool:
        lower = sentence.lower()
        return any(blocked.lower() in lower for blocked in OUTPUT_BLOCKLIST)

    sentences = re.split(r"(?<=[。！？!?\n])", answer)
    kept = [s for s in sentences if s and not is_blocked(s)]
    filtered = "".join(kept).strip()
    if not filtered:
        return "抱歉，我只能協助查詢店家資訊。"
    return filtered
