from __future__ import annotations

import re
from typing import List

from app.models import NormalizedOrganization

ABBREV_REPLACEMENTS = {
    "фгбоу во": "федеральное государственное бюджетное образовательное учреждение высшего образования",
    "фгаоу во": "федеральное государственное автономное образовательное учреждение высшего образования",
    "фгбу": "федеральное государственное бюджетное учреждение",
    "со ран": "сибирское отделение российской академии наук",
    "ран": "российская академия наук",
    "им.": "имени",
}


def normalize_org_name(raw: str) -> NormalizedOrganization:
    original = (raw or "").strip()
    norm = re.sub(r"[«»\"“”„]", "'", original)
    norm = re.sub(r"\s+", " ", norm).strip()
    lowered = norm.lower()
    for k, v in ABBREV_REPLACEMENTS.items():
        lowered = lowered.replace(k, v)

    lowered = re.sub(r"\bфилиал\b", "филиал", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip(" ,.-")
    search = re.sub(r"[^a-zа-я0-9 ]", " ", lowered)
    search = re.sub(r"\s+", " ", search).strip()
    tokens: List[str] = search.split()
    return NormalizedOrganization(raw=original, normalized=lowered, search_text=search, tokens=tokens)
