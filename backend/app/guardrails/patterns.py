import re

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bignore\s+(all\s+|any\s+)?(previous|prior|above)\s+(instructions|prompts?|context)", re.I),
    re.compile(r"\bdisregard\s+(the\s+)?(above|previous|prior|earlier)\b", re.I),
    re.compile(r"\b(you are|act)\s+(now\s+)?(as\s+)?(an?\s+)?(dan|unfiltered|jailbroken|developer mode)\b", re.I),
    re.compile(r"\b(print|reveal|repeat|show|leak)\s+(me\s+)?(your\s+|the\s+)?(system\s+)?prompt\b", re.I),
    re.compile(r"\b(ignore|bypass|override)\s+(your\s+)?(guidelines|rules|safety|instructions)\b", re.I),
    re.compile(r"</?(system|instructions?)>", re.I),
]

PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}
