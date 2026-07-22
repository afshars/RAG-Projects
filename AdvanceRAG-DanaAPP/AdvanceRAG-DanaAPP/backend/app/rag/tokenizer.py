import re

TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.split(text.lower()) if len(t) > 1]
