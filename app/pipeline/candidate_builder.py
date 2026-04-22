from __future__ import annotations

import logging
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Dict, List, Set

from app.models import Candidate, NormalizedOrganization
from app.scoring import canonical_match_key, display_normalized_key
from app.sources import OfficialSiteSource, RORSource, TranslitFallbackSource, WikidataSource, WikipediaSource


GENERIC_ANCHORS = {"university", "institute", "academy", "center", "centre", "laboratory", "federal", "state"}


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
        raw_candidates: List[Candidate] = []
        known_websites: List[str] = []

        ror_items = self.ror.search(org.search_text, limit=5)
        for item in ror_items:
            name = item.get("name") or ""
            website = (item.get("links") or [""])[0]
            known_websites.extend(item.get("links") or [])
            aliases = item.get("aliases") or []
            if name:
                raw_candidates.append(
                    Candidate(
                        organization_ru_raw=org.raw,
                        organization_ru_normalized=org.normalized,
                        candidate_text=name,
                        source="ror",
                        source_url=item.get("id", ""),
                        website_url=website,
                        support_signals=["ror_hit"],
                        notes=["Candidate from ROR registry"],
                        metadata={"ror_id": item.get("id", ""), "aliases": aliases, "label": name},
                    )
                )
            for alias in aliases[:2]:
                if alias and alias != name:
                    raw_candidates.append(
                        Candidate(
                            organization_ru_raw=org.raw,
                            organization_ru_normalized=org.normalized,
                            candidate_text=alias,
                            source="ror",
                            source_url=item.get("id", ""),
                            website_url=website,
                            support_signals=["ror_alias"],
                            notes=["Alias from ROR"],
                            metadata={"ror_id": item.get("id", ""), "label": name},
                        )
                    )

        wd = self.wikidata.search(org.search_text)
        if wd and wd.get("en_label"):
            raw_candidates.append(
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
                    raw_candidates.append(
                        Candidate(
                            organization_ru_raw=org.raw,
                            organization_ru_normalized=org.normalized,
                            candidate_text=wp["title"],
                            source="wikipedia",
                            source_url=wp.get("fullurl", ""),
                            support_signals=["interlanguage_link"],
                            notes=["Candidate from EN Wikipedia title"],
                            metadata={"wikipedia_url": wp.get("fullurl", "")},
                        )
                    )

        preferred_url = known_websites[0] if known_websites else ""
        if preferred_url:
            official = self.official.probe(preferred_url, known_websites=known_websites)
            if official:
                raw_candidates.append(
                    Candidate(
                        organization_ru_raw=org.raw,
                        organization_ru_normalized=org.normalized,
                        candidate_text=official["candidate_text"],
                        source="official_site",
                        source_url=official.get("source_url", ""),
                        website_url=preferred_url,
                        support_signals=["site_title_match"],
                        notes=[official.get("notes", "")],
                        metadata={"snippet": official.get("snippet", "")},
                    )
                )

        if not raw_candidates:
            raw_candidates.append(self.translit.build(org))

        aggregated = self._aggregate(raw_candidates)
        self.logger.debug(
            "Built %d raw candidates, %d aggregated for %s",
            len(raw_candidates),
            len(aggregated),
            org.raw,
        )
        return aggregated

    def _aggregate(self, candidates: List[Candidate]) -> List[Candidate]:
        buckets: Dict[str, Candidate] = {}

        for candidate in candidates:
            candidate.normalized_candidate_text = display_normalized_key(candidate.candidate_text)
            canonical = canonical_match_key(candidate.candidate_text)
            merge_key = self._find_near_key(canonical, list(buckets.keys()))
            if merge_key is None:
                key = canonical
                candidate.contributing_sources = [candidate.source]
                candidate.source_evidence = [self._to_evidence(candidate)]
                buckets[key] = candidate
                continue

            existing = buckets[merge_key]
            existing.support_signals = sorted(set(existing.support_signals + candidate.support_signals))
            existing.notes = [*existing.notes, *candidate.notes]
            existing.contributing_sources = sorted(set(existing.contributing_sources + [candidate.source]))
            existing.source_evidence.append(self._to_evidence(candidate))

            if candidate.source == "official_site" and existing.source != "official_site":
                buckets[merge_key] = replace(
                    existing,
                    source="official_site",
                    source_url=candidate.source_url or existing.source_url,
                    website_url=candidate.website_url or existing.website_url,
                )

        for cand in buckets.values():
            if len(set(cand.contributing_sources)) > 1:
                cand.support_signals.append("multi_source_support")
            self._mark_conflict(cand)

        return list(buckets.values())

    @staticmethod
    def _find_near_key(key: str, existing_keys: List[str]) -> str | None:
        if key in existing_keys:
            return key

        key_tokens = _tokens(key)
        if not key_tokens:
            return None

        for ex in existing_keys:
            ex_tokens = _tokens(ex)
            if not ex_tokens:
                continue

            jacc = _jaccard(key_tokens, ex_tokens)
            shared_anchors = _anchor_tokens(key_tokens) & _anchor_tokens(ex_tokens)
            similarity = SequenceMatcher(None, key, ex).ratio()

            if jacc >= 0.90:
                return ex
            if jacc >= 0.75 and similarity >= 0.86 and shared_anchors:
                return ex
        return None

    @staticmethod
    def _to_evidence(candidate: Candidate) -> Dict[str, str]:
        return {
            "source": candidate.source,
            "text": candidate.candidate_text,
            "url": candidate.source_url or "",
            "note": "; ".join(candidate.notes),
            "normalized": canonical_match_key(candidate.candidate_text),
            "display_normalized": display_normalized_key(candidate.candidate_text),
        }

    @staticmethod
    def _mark_conflict(candidate: Candidate) -> None:
        forms = sorted({e.get("normalized", "") for e in candidate.source_evidence if e.get("normalized")})
        if len(forms) < 2 or len(candidate.contributing_sources) < 2:
            return

        materially_different = False
        for idx, left in enumerate(forms):
            for right in forms[idx + 1 :]:
                if not left or not right:
                    continue
                similarity = SequenceMatcher(None, left, right).ratio()
                if similarity < 0.80:
                    materially_different = True
                    break
            if materially_different:
                break

        if materially_different and "source_conflict" not in candidate.support_signals:
            candidate.support_signals.append("source_conflict")


def _tokens(key: str) -> Set[str]:
    return {x for x in key.split() if x}


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _anchor_tokens(tokens: Set[str]) -> Set[str]:
    return {t for t in tokens if t not in GENERIC_ANCHORS and len(t) >= 4}
