"""Dataclass models for the pyedi compare engine."""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field


@dataclass
class MatchKeyPart:
    """One component of a (possibly multi-dimensional) match key."""

    segment: str | None = None
    field: str | None = None
    json_path: str | None = None
    normalize: str | None = None


@dataclass
class MatchKeyConfig:
    """Defines how to extract the pairing key from a document."""

    segment: str | None = None       # LEGACY — mirror of parts[0].segment
    field: str | None = None         # LEGACY — mirror of parts[0].field
    json_path: str | None = None     # LEGACY — mirror of parts[0].json_path
    normalize: str | None = None     # LEGACY — mirror of parts[0].normalize
    parts: list[MatchKeyPart] = dc_field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.parts and (self.segment or self.field or self.json_path):
            self.parts = [MatchKeyPart(
                segment=self.segment,
                field=self.field,
                json_path=self.json_path,
                normalize=self.normalize,
            )]
        elif self.parts and not (self.segment or self.field or self.json_path):
            p = self.parts[0]
            self.segment = p.segment
            self.field = p.field
            self.json_path = p.json_path
            self.normalize = p.normalize


@dataclass
class CompareProfile:
    """A self-contained comparison configuration for one transaction type."""

    name: str                                          # e.g. "810_invoice"
    description: str
    match_key: MatchKeyConfig
    segment_qualifiers: dict[str, str | None]
    rules_file: str
    trading_partner: str = ""
    transaction_type: str = ""


@dataclass
class MatchEntry:
    """A single matchable value extracted from a file."""

    file_path: str
    match_value: str
    transaction_index: int
    transaction_data: dict


@dataclass
class MatchPair:
    """A paired source and target transaction sharing the same match value."""

    source: MatchEntry | None
    target: MatchEntry | None
    match_value: str


@dataclass
class FieldRule:
    """Comparison rule for a specific (segment, field) combination."""

    segment: str
    field: str
    severity: str = "hard"                 # hard | soft | ignore
    ignore_case: bool = False
    numeric: bool = False
    conditional_qualifier: str | None = None
    amount_variance: float | None = None


@dataclass
class CompareRules:
    """Complete rule set for a profile: classification rules + ignore list."""

    classification: list[FieldRule] = dc_field(default_factory=list)
    ignore: list[dict[str, str]] = dc_field(default_factory=list)
    segment_qualifiers: dict[str, str | None] = dc_field(default_factory=dict)


@dataclass
class TieredRules:
    """Three-tier rule container: universal → transaction-type → partner."""

    universal: CompareRules = dc_field(default_factory=CompareRules)
    transaction: CompareRules = dc_field(default_factory=CompareRules)
    partner: CompareRules = dc_field(default_factory=CompareRules)


@dataclass
class ResolvedFieldRule:
    """A FieldRule annotated with the tier it came from."""

    rule: FieldRule
    tier: str  # "universal" | "transaction" | "partner" | "default"


@dataclass
class FieldDiff:
    """A single field-level difference found during comparison."""

    segment: str
    field: str
    severity: str
    source_value: str | None
    target_value: str | None
    description: str
    wildcard_fallback: bool = False


@dataclass
class DiscoveryRecord:
    """A (segment, field) combo classified by wildcard fallback — needs human review."""

    profile: str
    segment: str
    field: str
    source_value: str | None
    target_value: str | None
    suggested_severity: str = "hard"
    applied: bool = False
    discovered_at: str = ""


@dataclass
class CompareResult:
    """Result of comparing one matched pair."""

    pair: MatchPair
    status: str               # MATCH | MISMATCH | UNMATCHED
    diffs: list[FieldDiff]
    timestamp: str


@dataclass
class RunSummary:
    """Aggregate summary of a full comparison run."""

    run_id: int
    profile: str
    total_pairs: int
    matched: int
    mismatched: int
    unmatched: int
    started_at: str
    finished_at: str
    reclassified_from: int | None = None
    trading_partner: str = ""
    transaction_type: str = ""


@dataclass
class RunDiffResult:
    """Result of comparing two runs."""

    new_errors: list[dict]        # in run B but not A
    resolved_errors: list[dict]   # in run A but not B
    changed_errors: list[dict]    # same (seg,field) different severity
    unchanged_count: int
