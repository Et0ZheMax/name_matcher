from __future__ import annotations

import re

from app.config import AppConfig
from app.models import Candidate, PubmedValidation
from app.scoring import apply_pubmed_boost
from app.sources import PubMedSource


class CandidateValidator:
    def __init__(self, pubmed: PubMedSource, config: AppConfig) -> None:
        self.pubmed = pubmed
        self.config = config

    def validate_with_pubmed(self, candidate: Candidate, alias: str = "") -> tuple[Candidate, PubmedValidation]:
        exact = f'"{candidate.candidate_text}"[Affiliation]'
        broad = exact if not alias else f'{exact} OR "{alias}"[Affiliation]'

        exact_res = self.pubmed.query_count(exact, retmax=5)
        broad_res = self.pubmed.query_count(broad, retmax=5)
        pmids = [str(x) for x in exact_res.get("ids", [])[:5]]
        summaries = self.pubmed.fetch_summaries(pmids)
        affiliations = self.pubmed.fetch_affiliations(pmids)

        similar_summary = self._is_similar_in_texts(candidate.candidate_text, summaries)
        similar_affiliation = self._is_similar_in_texts(candidate.candidate_text, affiliations)

        boosted = apply_pubmed_boost(
            candidate,
            self.config.scoring,
            int(exact_res.get("count", 0)),
            similar_summary,
            affiliation_match=similar_affiliation,
        )
        status = "validated" if exact_res.get("count", 0) else "not_validated"
        notes = []
        notes.append("Affiliation text aligned" if similar_affiliation else "No close affiliation phrase")
        notes.append("Title/summary overlap present" if similar_summary else "No strong summary overlap")

        pub = PubmedValidation(
            pubmed_exact_query=exact,
            pubmed_exact_count=int(exact_res.get("count", 0)),
            pubmed_broad_query=broad,
            pubmed_broad_count=int(broad_res.get("count", 0)),
            pubmed_validation_status=status,
            pubmed_validation_notes="; ".join(notes),
            pubmed_pmids=pmids,
        )
        return boosted, pub

    @staticmethod
    def _is_similar_in_texts(candidate_text: str, texts: list[str]) -> bool:
        cand_tokens = set(re.findall(r"[a-z]+", candidate_text.lower()))
        if not cand_tokens:
            return False
        for text in texts:
            tokens = set(re.findall(r"[a-z]+", (text or "").lower()))
            overlap = len(cand_tokens & tokens)
            if overlap >= max(2, len(cand_tokens) // 3):
                return True
        return False
