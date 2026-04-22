from __future__ import annotations

import logging
from typing import List

from app.models import Candidate, NormalizedOrganization
from app.sources import OfficialSiteSource, RORSource, TranslitFallbackSource, WikidataSource, WikipediaSource


class CandidateBuilder:
    def __init__(
        self,
        ror: RORSource,
        official: OfficialSiteSource,
        wikidata: WikidataSource,
        wikipedia: WikipediaSource,
        translit: TranslitFallbackSource,
        logger: logging.Logger,
    ) -> None:
        self.ror = ror
        self.official = official
        self.wikidata = wikidata
        self.wikipedia = wikipedia
        self.translit = translit
        self.logger = logger

    def build(self, org: NormalizedOrganization) -> List[Candidate]:
        candidates: List[Candidate] = []
        website_url = ""

        ror_item = self.ror.search(org.search_text)
        if ror_item:
            name = ror_item.get("name") or ""
            website_url = (ror_item.get("links") or [""])[0]
            if name:
                candidates.append(
                    Candidate(
                        organization_ru_raw=org.raw,
                        organization_ru_normalized=org.normalized,
                        candidate_text=name,
                        source="ror",
                        source_url=ror_item.get("id", ""),
                        website_url=website_url,
                        support_signals=["ror_hit"],
                        notes=["Candidate from ROR registry"],
                        metadata={"ror_id": ror_item.get("id", "")},
                    )
                )

        wd = self.wikidata.search(org.search_text)
        if wd and wd.get("en_label"):
            candidates.append(
                Candidate(
                    organization_ru_raw=org.raw,
                    organization_ru_normalized=org.normalized,
                    candidate_text=wd["en_label"],
                    source="wikidata",
                    source_url=wd.get("wikidata_url"),
                    support_signals=["wikidata_en_label"],
                    notes=["EN label from Wikidata"],
                    metadata={"wikidata_url": wd.get("wikidata_url", "")},
                )
            )
            if wd.get("enwiki_title"):
                wp = self.wikipedia.from_en_title(wd["enwiki_title"])
                if wp:
                    candidates.append(
                        Candidate(
                            organization_ru_raw=org.raw,
                            organization_ru_normalized=org.normalized,
                            candidate_text=wp["title"],
                            source="wikipedia",
                            source_url=wp.get("fullurl", ""),
                            support_signals=["interlanguage_link"],
                            notes=["Candidate from EN Wikipedia title"],
                        )
                    )

        if website_url:
            official = self.official.probe(website_url)
            if official:
                candidates.append(
                    Candidate(
                        organization_ru_raw=org.raw,
                        organization_ru_normalized=org.normalized,
                        candidate_text=official["candidate_text"],
                        source="official_site",
                        source_url=official.get("source_url", ""),
                        website_url=website_url,
                        support_signals=["site_title_match"],
                        notes=[official.get("notes", "")],
                    )
                )

        if not candidates:
            candidates.append(self.translit.build(org))

        self.logger.debug("Built %d candidates for %s", len(candidates), org.raw)
        return candidates
