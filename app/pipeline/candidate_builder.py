from __future__ import annotations

import logging
import re
from dataclasses import replace
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set

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
        self._last_source_trace: List[Dict[str, Any]] = []

    def build(self, org: NormalizedOrganization) -> List[Candidate]:
        self._last_source_trace = []
        raw_candidates: List[Candidate] = []
        known_websites: List[str] = []
        source_success = {"ror": False, "wikidata": False, "wikipedia": False, "official_site": False}

        self.logger.debug(
            "Org normalized=%s core_text=%s service_parts=%s",
            org.normalized,
            org.core_text,
            ",".join(org.service_parts) or "-",
        )

        queries = self._build_queries(org)
        self.logger.debug("Source query cascade for %s: %s", org.raw, " | ".join(queries))

        for query in queries:
            ror_items = self.ror.search(query, limit=5)
            self._trace(
                org=org,
                source="ror",
                query=query,
                found_candidate=(ror_items[0].get("name", "") if ror_items else ""),
                accepted=bool(ror_items),
                reason=("matched organization records" if ror_items else "no records returned"),
            )
            for item in ror_items:
                name = item.get("name") or ""
                website = (item.get("links") or [""])[0]
                known_websites.extend(item.get("links") or [])
                aliases = item.get("aliases") or []
                if name:
                    source_success["ror"] = True
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
                        source_success["ror"] = True
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
            if source_success["ror"]:
                break

        wd = None
        for query in queries:
            wd = self.wikidata.search(query)
            self._trace(
                org=org,
                source="wikidata",
                query=query,
                found_candidate=(wd.get("en_label", "") if wd else ""),
                accepted=bool(wd and wd.get("en_label")),
                reason=("has en_label" if wd and wd.get("en_label") else "no suitable entity/en_label"),
            )
            if wd and wd.get("en_label"):
                source_success["wikidata"] = True
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
                break

        wiki_hit = False
        if wd and wd.get("enwiki_title"):
            wp = self.wikipedia.from_en_title(wd["enwiki_title"])
            self._trace(
                org=org,
                source="wikipedia",
                query=f"enwiki:{wd['enwiki_title']}",
                found_candidate=(wp.get("title", "") if wp else ""),
                accepted=bool(wp),
                reason=("resolved EN page title from Wikidata sitelink" if wp else "enwiki sitelink did not resolve"),
            )
            if wp:
                source_success["wikipedia"] = True
                wiki_hit = True
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

        if not wiki_hit:
            for query in queries:
                ru_page = self.wikipedia.search_ru(query)
                if not ru_page:
                    self._trace(
                        org=org,
                        source="wikipedia",
                        query=query,
                        found_candidate="",
                        accepted=False,
                        reason="ruwiki page not found",
                    )
                    continue

                intl = self.wikipedia.get_ru_international_name(ru_page.get("title", ""))
                accepted = bool(intl)
                self._trace(
                    org=org,
                    source="wikipedia_infobox",
                    query=f"{query} -> {ru_page.get('title','')}",
                    found_candidate=intl or "",
                    accepted=accepted,
                    reason=("accepted field 'Международное название/International name'" if accepted else "infobox field missing"),
                )
                if accepted:
                    source_success["wikipedia"] = True
                    raw_candidates.append(
                        Candidate(
                            organization_ru_raw=org.raw,
                            organization_ru_normalized=org.normalized,
                            candidate_text=intl or "",
                            source="wikipedia_infobox",
                            source_url=ru_page.get("fullurl", ""),
                            support_signals=["wikipedia_infobox_international_name"],
                            notes=["International name extracted from RU Wikipedia infobox"],
                            metadata={"wikipedia_url": ru_page.get("fullurl", "")},
                        )
                    )
                    break

        preferred_url = known_websites[0] if known_websites else ""
        if preferred_url:
            official = self.official.probe(preferred_url, known_websites=known_websites)
            self._trace(
                org=org,
                source="official_site",
                query=preferred_url,
                found_candidate=(official.get("candidate_text", "") if official else ""),
                accepted=bool(official and official.get("candidate_text")),
                reason=("accepted strong EN field from page" if official else "no strong EN evidence"),
            )
            if official:
                source_success["official_site"] = True
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
        else:
            self._trace(
                org=org,
                source="official_site",
                query="",
                found_candidate="",
                accepted=False,
                reason="skipped: no known website from upstream sources",
            )

        if not raw_candidates:
            reason = (
                "fallback used because ROR/Wikidata/Wikipedia/official_site produced no accepted candidates"
                if not any(source_success.values())
                else "fallback used because all upstream candidates rejected by aggregation/filters"
            )
            self._trace(
                org=org,
                source="translit_fallback",
                query=org.normalized,
                found_candidate="",
                accepted=True,
                reason=reason,
            )
            raw_candidates.append(self.translit.build(org))

        aggregated = self._aggregate(raw_candidates)
        self.logger.debug(
            "Built %d raw candidates, %d aggregated for %s",
            len(raw_candidates),
            len(aggregated),
            org.raw,
        )
        return aggregated

    def consume_source_trace(self) -> List[Dict[str, Any]]:
        items = self._last_source_trace
        self._last_source_trace = []
        return items

    def _build_queries(self, org: NormalizedOrganization) -> List[str]:
        compact_core = self._compact_core_query(org)
        parts = [
            org.search_text,
            self._sanitize_query(org.raw),
            self._sanitize_query(org.core_text),
            self._append_ran_variant(org.core_text),
            compact_core,
            self._append_ran_variant(compact_core),
            self._short_form(org, compact_core),
        ]
        seen = set()
        queries: List[str] = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                queries.append(p)
        return queries or [org.search_text]

    @staticmethod
    def _sanitize_query(text: str) -> str:
        query = re.sub(r"[^a-zа-я0-9 ]", " ", (text or "").lower())
        return re.sub(r"\s+", " ", query).strip()

    def _append_ran_variant(self, core_text: str) -> str:
        sanitized = self._sanitize_query(core_text)
        if not sanitized:
            return ""
        if "ран" in sanitized or "российской академии наук" in sanitized:
            return sanitized
        return f"{sanitized} ран".strip()

    @staticmethod
    def _short_form(org: NormalizedOrganization, compact_core: str) -> str:
        core_words = [w for w in compact_core.split() if len(w) > 2]
        words = core_words or [w for w in org.tokens if len(w) > 2]
        if len(words) >= 4:
            return " ".join(words[:4])
        return " ".join(words)

    def _compact_core_query(self, org: NormalizedOrganization) -> str:
        stop = {
            "федеральное",
            "государственное",
            "бюджетное",
            "автономное",
            "научное",
            "образовательное",
            "учреждение",
            "высшего",
            "образования",
            "российская",
            "российской",
            "академия",
            "наук",
        }
        words = [w for w in self._sanitize_query(org.core_text).split() if w and w not in stop]
        return " ".join(words)

    def _trace(self, org: NormalizedOrganization, source: str, query: str, found_candidate: str, accepted: bool, reason: str) -> None:
        entry: Dict[str, Any] = {
            "organization": org.raw,
            "organization_normalized": org.normalized,
            "source": source,
            "query": query,
            "found_candidate": found_candidate,
            "accepted": "accepted" if accepted else "rejected",
            "reason": reason,
        }
        self._last_source_trace.append(entry)
        self.logger.debug(
            "TRACE source=%s query='%s' candidate='%s' decision=%s reason=%s",
            source,
            query,
            found_candidate or "-",
            entry["accepted"],
            reason,
        )

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
