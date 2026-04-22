from __future__ import annotations

import logging
from typing import List

from app.config import AppConfig
from app.models import Candidate, ResolvedOrganization
from app.scoring import score_candidates, status_from_score


class Resolver:
    def __init__(self, config: AppConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger

    def resolve(self, candidates: List[Candidate]) -> tuple[Candidate, str, List[Candidate]]:
        ranked = score_candidates(candidates, self.config.scoring)
        best = ranked[0]
        status = status_from_score(best, self.config.scoring)
        if self.logger:
            self.logger.info(
                "Selected candidate='%s' score=%s status=%s sources=%s",
                best.candidate_text,
                best.score,
                status,
                ",".join(best.contributing_sources or [best.source]),
            )
        return best, status, ranked

    @staticmethod
    def build_resolved(best: Candidate, status: str) -> ResolvedOrganization:
        secondary = [s for s in (best.contributing_sources or [best.source]) if s != best.source]
        return ResolvedOrganization(
            organization_ru_raw=best.organization_ru_raw,
            organization_ru_normalized=best.organization_ru_normalized,
            organization_en_final=best.candidate_text,
            final_status=status,
            final_confidence=best.confidence,
            source_primary=best.source,
            source_url_primary=best.source_url or "",
            source_secondary=", ".join(secondary),
            website_url=best.website_url or "",
            ror_id=best.metadata.get("ror_id", ""),
            wikipedia_url=best.metadata.get("wikipedia_url", ""),
            wikidata_url=best.metadata.get("wikidata_url", ""),
            notes="; ".join(best.notes),
        )
