"""Key alias parsing and heuristics."""

from __future__ import annotations

import re


def parse_aliases(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in (raw or "").split(","):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        left, right = piece.split("=", 1)
        left = left.strip().lower()
        right = right.strip().lower()
        if re.fullmatch(r"[a-f0-9]{6,64}", left):
            mapping[left[:8]] = right
        elif re.fullmatch(r"[a-f0-9]{6,64}", right):
            mapping[right[:8]] = left
        else:
            mapping[left[:8]] = right
    return mapping


def heuristic_label(name: str, label: str, hash_prefix: str) -> str:
    text = " ".join([name or "", label or ""]).lower()
    if any(token in text for token in ("agent0", "hermes", "luke")):
        return "luke"
    if any(token in text for token in ("helpdesk", "nimrod", "nemotron", "help")):
        return "helpdesk"
    return label or name or hash_prefix


def label_for_key(hash_value: str, name: str, label: str, aliases: dict[str, str]) -> str:
    prefix = (hash_value or "")[:8].lower()
    if prefix in aliases:
        return aliases[prefix]
    return heuristic_label(name, label, prefix)
