from __future__ import annotations

import re

from app.models import Candidate, PubmedValidation
from app.scoring import apply_pubmed_boost
from app.sources import PubMedSource
from app.config import AppConfig


class CandidateValidator:
    def __init__(self, pubmed: PubMedSource, config: AppConfig) -> None:
        self.pubmed = pubmed
        self.config = config

    def validate_with_pubmed(self, candidate: Candidate, alias: str = "") -> tuple[Candidate, PubmedValidation]:
        exact = f'"{candidate.candidate_text}"[Affiliation]'
        broad = exact if not alias else f'{exact} OR "{alias}"[Affiliation]'

        exact_res = self.pubmed.query_count(exact)
        broad_res = self.pubmed.query_count(broad)
        summaries = self.pubmed.fetch_summaries(exact_res.get("ids", []))
        similar = self._is_similar_in_summaries(candidate.candidate_text, summaries)

        boosted = apply_pubmed_boost(candidate, self.config.scoring, int(exact_res.get("count", 0)), similar)
        status = "validated" if exact_res.get("count", 0) else "not_validated"
        notes = "Affiliation-like evidence in titles" if similar else "No close textual evidence"

        pub = PubmedValidation(
            pubmed_exact_query=exact,
            pubmed_exact_count=int(exact_res.get("count", 0)),
            pubmed_broad_query=broad,
            pubmed_broad_count=int(broad_res.get("count", 0)),
            pubmed_validation_status=status,
            pubmed_validation_notes=notes,
        )
        return boosted, pub

    @staticmethod
    def _is_similar_in_summaries(candidate_text: str, summaries: list[str]) -> bool:
        cand_tokens = set(re.findall(r"[a-z]+", candidate_text.lower()))
        if not cand_tokens:
            return False
        for text in summaries:
            tokens = set(re.findall(r"[a-z]+", text.lower()))
            overlap = len(cand_tokens & tokens)
            if overlap >= max(2, len(cand_tokens) // 3):
                return True
        return False
