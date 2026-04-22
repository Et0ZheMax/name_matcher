from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class NormalizedOrganization:
    raw: str
    normalized: str
    search_text: str
    tokens: List[str] = field(default_factory=list)


@dataclass(slots=True)
class Candidate:
    organization_ru_raw: str
    organization_ru_normalized: str
    candidate_text: str
    source: str
    source_url: Optional[str] = None
    website_url: Optional[str] = None
    support_signals: List[str] = field(default_factory=list)
    score: int = 0
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PubmedValidation:
    pubmed_exact_query: str = ""
    pubmed_exact_count: int = 0
    pubmed_broad_query: str = ""
    pubmed_broad_count: int = 0
    pubmed_validation_status: str = "not_checked"
    pubmed_validation_notes: str = ""


@dataclass(slots=True)
class ResolvedOrganization:
    organization_ru_raw: str
    organization_ru_normalized: str
    organization_en_final: str
    final_status: str
    final_confidence: float
    source_primary: str = ""
    source_url_primary: str = ""
    source_secondary: str = ""
    website_url: str = ""
    ror_id: str = ""
    wikipedia_url: str = ""
    wikidata_url: str = ""
    notes: str = ""
    pubmed: PubmedValidation = field(default_factory=PubmedValidation)


@dataclass(slots=True)
class PipelineResult:
    organizations: List[ResolvedOrganization]
    original_rows_enriched: List[Dict[str, Any]]
    manual_review: List[ResolvedOrganization]
    candidates_debug: List[Candidate]
