from __future__ import annotations

import re
from typing import List, Tuple

from app.models import NormalizedOrganization

ABBREV_REPLACEMENTS = {
    "фгбоу во": "федеральное государственное бюджетное образовательное учреждение высшего образования",
    "фгаоу во": "федеральное государственное автономное образовательное учреждение высшего образования",
    "фгбу": "федеральное государственное бюджетное учреждение",
    "фгбну": "федеральное государственное бюджетное научное учреждение",
    "со ран": "сибирское отделение российской академии наук",
    "ран": "российская академия наук",
    "им.": "имени",
    "им ": "имени ",
}

SERVICE_PATTERNS: list[Tuple[str, str]] = [
    (r"\bфилиал\b", "branch"),
    (r"\bимени\s+[а-яё\-\.\s]+", "named_after"),
    (r"\bфедеральное\s+государственное\s+бюджетное\s+образовательное\s+учреждение\s+высшего\s+образования\b", "federal_edu_form"),
    (r"\bфедеральное\s+государственное\s+автономное\s+образовательное\s+учреждение\s+высшего\s+образования\b", "federal_edu_form"),
    (r"\bфедеральное\s+государственное\s+бюджетное\s+учреждение\b", "federal_institution_form"),
    (r"\bсибирское\s+отделение\s+российской\s+академии\s+наук\b", "ran_branch"),
    (r"\bроссийской\s+академии\s+наук\b", "ran"),
]


def normalize_org_name(raw: str) -> NormalizedOrganization:
    original = (raw or "").strip()
    norm = re.sub(r"[«»\"“”„]", "'", original)
    norm = re.sub(r"\s+", " ", norm).strip()
    lowered = norm.lower()
    for k, v in ABBREV_REPLACEMENTS.items():
        lowered = lowered.replace(k, v)

    lowered = re.sub(r"\s+", " ", lowered).strip(" ,.-")
    lowered = re.sub(r"\bи\s+о\b", "", lowered)
    lowered = re.sub(r"\(.*?\)", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip(" ,.-")

    service_parts: List[str] = []
    core_text = lowered
    for pattern, marker in SERVICE_PATTERNS:
        if re.search(pattern, core_text):
            service_parts.append(marker)
            core_text = re.sub(pattern, " ", core_text)

    core_text = re.sub(r"\s+", " ", core_text).strip(" ,.-")

    search_base = core_text or lowered
    search = re.sub(r"[^a-zа-я0-9 ]", " ", search_base)
    search = re.sub(r"\s+", " ", search).strip()
    tokens: List[str] = search.split()

    return NormalizedOrganization(
        raw=original,
        normalized=lowered,
        search_text=search,
        tokens=tokens,
        service_parts=service_parts,
        core_text=core_text,
    )
