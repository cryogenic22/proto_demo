"""
Procedure Mapper for ProtoExtract Pipeline
==========================================
Loads proto_demo's procedure_mapping.csv and provides fuzzy matching
for procedure name normalization and CPT code lookup.

Replaces our 75-procedure vocabulary with proto_demo's 260 canonical
procedures / 840 aliases covering 15 therapeutic categories.

Usage:
    from procedure_mapper import ProcedureMapper

    mapper = ProcedureMapper("path/to/procedure_mapping.csv")
    result = mapper.match("12-lead ECG")
    # result.canonical_name = "Electrocardiogram (12-lead)"
    # result.cpt_code = "93000"
    # result.category = "Cardiac"
    # result.confidence = 0.95
"""

import csv
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ProcedureEntry:
    """A canonical procedure with its aliases and metadata."""
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    cpt_code: str = ""
    category: str = ""
    subcategory: str = ""
    typical_cost_usd: float = 0.0
    requires_fasting: bool = False
    duration_minutes: int = 0

    @property
    def all_names(self) -> List[str]:
        """All searchable names including canonical and aliases."""
        return [self.canonical_name] + self.aliases


@dataclass
class MatchResult:
    """Result of a procedure matching attempt."""
    query: str
    canonical_name: str
    matched_alias: str
    cpt_code: str
    category: str
    confidence: float
    match_type: str       # "exact", "alias_exact", "fuzzy", "token"
    procedure: Optional[ProcedureEntry] = None


class ProcedureMapper:
    """
    Maps extracted procedure names to canonical procedure vocabulary.

    Matching strategy (in order of priority):
        1. Exact match against canonical names
        2. Exact match against aliases
        3. Fuzzy match (normalized Levenshtein)
        4. Token-based match (bag-of-words overlap)
        5. Abbreviation expansion

    The vocabulary is loaded from proto_demo's procedure_mapping.csv.
    """

    # Common abbreviations in clinical protocols
    ABBREVIATIONS = {
        "ecg": "electrocardiogram",
        "ekg": "electrocardiogram",
        "bp": "blood pressure",
        "hr": "heart rate",
        "bmi": "body mass index",
        "cbc": "complete blood count",
        "cmp": "comprehensive metabolic panel",
        "bmp": "basic metabolic panel",
        "ua": "urinalysis",
        "ct": "computed tomography",
        "mri": "magnetic resonance imaging",
        "pet": "positron emission tomography",
        "us": "ultrasound",
        "xr": "x-ray",
        "pfts": "pulmonary function tests",
        "pft": "pulmonary function test",
        "lfts": "liver function tests",
        "lft": "liver function test",
        "hba1c": "hemoglobin a1c",
        "a1c": "hemoglobin a1c",
        "inr": "international normalized ratio",
        "pt": "prothrombin time",
        "aptt": "activated partial thromboplastin time",
        "esr": "erythrocyte sedimentation rate",
        "crp": "c-reactive protein",
        "gfr": "glomerular filtration rate",
        "egfr": "estimated glomerular filtration rate",
        "dexa": "dual-energy x-ray absorptiometry",
        "echo": "echocardiogram",
        "holter": "holter monitor",
        "aes": "adverse events",
        "sae": "serious adverse event",
        "pk": "pharmacokinetic",
        "pd": "pharmacodynamic",
        "conmeds": "concomitant medications",
    }

    def __init__(
        self,
        csv_path: str = None,
        fuzzy_threshold: float = 0.75,
        token_threshold: float = 0.60,
    ):
        self.fuzzy_threshold = fuzzy_threshold
        self.token_threshold = token_threshold
        self.procedures: List[ProcedureEntry] = []
        self._name_index: Dict[str, ProcedureEntry] = {}
        self._token_index: Dict[str, Set[int]] = defaultdict(set)

        if csv_path:
            self.load_csv(csv_path)
        else:
            self._load_default_vocabulary()

    def load_csv(self, path: str):
        """
        Load procedure vocabulary from proto_demo CSV.

        Expected CSV columns:
            canonical_name, aliases (pipe-separated), cpt_code, category,
            subcategory, typical_cost_usd, requires_fasting, duration_minutes
        """
        self.procedures = []
        self._name_index = {}

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                aliases = [
                    a.strip()
                    for a in row.get("aliases", "").split("|")
                    if a.strip()
                ]
                entry = ProcedureEntry(
                    canonical_name=row["canonical_name"].strip(),
                    aliases=aliases,
                    cpt_code=row.get("cpt_code", "").strip(),
                    category=row.get("category", "").strip(),
                    subcategory=row.get("subcategory", "").strip(),
                    typical_cost_usd=float(row.get("typical_cost_usd", 0) or 0),
                    requires_fasting=row.get("requires_fasting", "").lower() == "true",
                    duration_minutes=int(row.get("duration_minutes", 0) or 0),
                )
                self.procedures.append(entry)

        self._build_indices()
        logger.info(
            f"Loaded {len(self.procedures)} procedures with "
            f"{sum(len(p.aliases) for p in self.procedures)} aliases"
        )

    def _load_default_vocabulary(self):
        """Load a minimal default vocabulary for testing."""
        defaults = [
            ProcedureEntry("Complete Blood Count", ["CBC", "blood count", "full blood count"], "85025", "Laboratory"),
            ProcedureEntry("Comprehensive Metabolic Panel", ["CMP", "metabolic panel", "chem-14"], "80053", "Laboratory"),
            ProcedureEntry("Urinalysis", ["UA", "urine analysis", "urine test"], "81001", "Laboratory"),
            ProcedureEntry("Electrocardiogram (12-lead)", ["ECG", "EKG", "12-lead ECG", "12 lead ECG"], "93000", "Cardiac"),
            ProcedureEntry("Echocardiogram", ["Echo", "cardiac ultrasound", "cardiac echo"], "93306", "Cardiac"),
            ProcedureEntry("Vital Signs", ["vitals", "VS", "blood pressure and heart rate"], "99000", "General"),
            ProcedureEntry("Physical Examination", ["PE", "physical exam", "complete physical"], "99213", "General"),
            ProcedureEntry("Informed Consent", ["consent", "ICF", "informed consent form"], "", "Administrative"),
            ProcedureEntry("Adverse Event Assessment", ["AE assessment", "safety assessment", "AEs"], "", "Safety"),
            ProcedureEntry("Concomitant Medications", ["con meds", "conmeds", "concurrent medications"], "", "Safety"),
        ]
        self.procedures = defaults
        self._build_indices()

    def _build_indices(self):
        """Build lookup indices for fast matching."""
        self._name_index = {}
        self._token_index = defaultdict(set)

        for i, proc in enumerate(self.procedures):
            for name in proc.all_names:
                normalized = self._normalize(name)
                self._name_index[normalized] = proc

                # Token index
                for token in self._tokenize(name):
                    self._token_index[token].add(i)

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for matching."""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Tokenize text into a set of normalized words."""
        normalized = ProcedureMapper._normalize(text)
        return {t for t in normalized.split() if len(t) > 1}

    def _expand_abbreviations(self, text: str) -> str:
        """Expand known abbreviations in the query."""
        words = text.lower().split()
        expanded = []
        for word in words:
            clean = re.sub(r'[^\w]', '', word)
            if clean in self.ABBREVIATIONS:
                expanded.append(self.ABBREVIATIONS[clean])
            else:
                expanded.append(word)
        return " ".join(expanded)

    @staticmethod
    def _levenshtein_similarity(s1: str, s2: str) -> float:
        """Compute normalized similarity (1 - normalized edit distance)."""
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        m, n = len(s1), len(s2)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                temp = dp[j]
                dp[j] = prev if s1[i-1] == s2[j-1] else 1 + min(dp[j], dp[j-1], prev)
                prev = temp
        return 1.0 - dp[n] / max(m, n)

    def _token_overlap(self, query_tokens: Set[str], proc_tokens: Set[str]) -> float:
        """Compute Jaccard-like token overlap score."""
        if not query_tokens or not proc_tokens:
            return 0.0
        intersection = query_tokens & proc_tokens
        union = query_tokens | proc_tokens
        return len(intersection) / len(union)

    def match(self, query: str) -> Optional[MatchResult]:
        """
        Match a procedure name to the canonical vocabulary.

        Args:
            query: Extracted procedure name from the SoA table

        Returns:
            MatchResult if a match is found, None if no match above threshold
        """
        if not query or not query.strip():
            return None

        original_query = query.strip()
        normalized_query = self._normalize(query)

        # 1. Exact match on canonical or alias
        if normalized_query in self._name_index:
            proc = self._name_index[normalized_query]
            matched_name = normalized_query
            for name in proc.all_names:
                if self._normalize(name) == normalized_query:
                    matched_name = name
                    break
            is_canonical = self._normalize(proc.canonical_name) == normalized_query
            return MatchResult(
                query=original_query,
                canonical_name=proc.canonical_name,
                matched_alias=matched_name,
                cpt_code=proc.cpt_code,
                category=proc.category,
                confidence=1.0,
                match_type="exact" if is_canonical else "alias_exact",
                procedure=proc,
            )

        # 2. Try with abbreviation expansion
        expanded = self._expand_abbreviations(query)
        expanded_norm = self._normalize(expanded)
        if expanded_norm != normalized_query and expanded_norm in self._name_index:
            proc = self._name_index[expanded_norm]
            return MatchResult(
                query=original_query,
                canonical_name=proc.canonical_name,
                matched_alias=expanded,
                cpt_code=proc.cpt_code,
                category=proc.category,
                confidence=0.95,
                match_type="abbreviation",
                procedure=proc,
            )

        # 3. Fuzzy match against all names
        best_fuzzy = None
        best_fuzzy_score = 0.0

        for proc in self.procedures:
            for name in proc.all_names:
                sim = self._levenshtein_similarity(normalized_query, self._normalize(name))
                if sim > best_fuzzy_score:
                    best_fuzzy_score = sim
                    best_fuzzy = (proc, name, sim)

        if best_fuzzy and best_fuzzy_score >= self.fuzzy_threshold:
            proc, matched, score = best_fuzzy
            return MatchResult(
                query=original_query,
                canonical_name=proc.canonical_name,
                matched_alias=matched,
                cpt_code=proc.cpt_code,
                category=proc.category,
                confidence=round(score, 3),
                match_type="fuzzy",
                procedure=proc,
            )

        # 4. Token-based match
        query_tokens = self._tokenize(query) | self._tokenize(expanded)
        best_token = None
        best_token_score = 0.0

        # Use token index to narrow candidates
        candidate_indices = set()
        for token in query_tokens:
            candidate_indices.update(self._token_index.get(token, set()))

        for idx in candidate_indices:
            proc = self.procedures[idx]
            for name in proc.all_names:
                proc_tokens = self._tokenize(name)
                overlap = self._token_overlap(query_tokens, proc_tokens)
                if overlap > best_token_score:
                    best_token_score = overlap
                    best_token = (proc, name, overlap)

        if best_token and best_token_score >= self.token_threshold:
            proc, matched, score = best_token
            return MatchResult(
                query=original_query,
                canonical_name=proc.canonical_name,
                matched_alias=matched,
                cpt_code=proc.cpt_code,
                category=proc.category,
                confidence=round(score * 0.9, 3),  # Slight penalty for token match
                match_type="token",
                procedure=proc,
            )

        return None

    def match_batch(self, queries: List[str]) -> List[Optional[MatchResult]]:
        """Match a batch of procedure names."""
        return [self.match(q) for q in queries]

    def get_categories(self) -> Dict[str, int]:
        """Get procedure counts by category."""
        counts = defaultdict(int)
        for proc in self.procedures:
            counts[proc.category] += 1
        return dict(sorted(counts.items()))

    def get_unmatched_report(
        self, queries: List[str]
    ) -> Dict[str, List[str]]:
        """
        Generate a report of matched and unmatched procedure names.
        Useful for identifying vocabulary gaps.
        """
        matched = []
        unmatched = []

        for q in queries:
            result = self.match(q)
            if result:
                matched.append(f"{q} -> {result.canonical_name} ({result.match_type}, {result.confidence:.2f})")
            else:
                unmatched.append(q)

        return {
            "matched": matched,
            "unmatched": unmatched,
            "match_rate": len(matched) / max(len(queries), 1),
        }


# ── CLI usage ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Procedure Mapper for SoA tables")
    parser.add_argument("--csv", help="Path to procedure_mapping.csv")
    parser.add_argument("--query", help="Single procedure name to match")
    parser.add_argument("--batch", help="Path to JSON file with list of procedure names")
    parser.add_argument("--report", action="store_true", help="Generate match report")
    args = parser.parse_args()

    mapper = ProcedureMapper(csv_path=args.csv)
    print(f"Loaded {len(mapper.procedures)} procedures")
    print(f"Categories: {mapper.get_categories()}")

    if args.query:
        result = mapper.match(args.query)
        if result:
            print(f"\nMatch: {result.canonical_name}")
            print(f"  Alias: {result.matched_alias}")
            print(f"  CPT: {result.cpt_code}")
            print(f"  Category: {result.category}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  Type: {result.match_type}")
        else:
            print(f"\nNo match found for: {args.query}")

    if args.batch:
        with open(args.batch) as f:
            queries = json.load(f)
        if args.report:
            report = mapper.get_unmatched_report(queries)
            print(f"\nMatch rate: {report['match_rate']:.1%}")
            print(f"Matched: {len(report['matched'])}")
            print(f"Unmatched: {len(report['unmatched'])}")
            for u in report["unmatched"]:
                print(f"  - {u}")
        else:
            results = mapper.match_batch(queries)
            for q, r in zip(queries, results):
                status = f"{r.canonical_name} ({r.confidence:.2f})" if r else "NO MATCH"
                print(f"  {q} -> {status}")
