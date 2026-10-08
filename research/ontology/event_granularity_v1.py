"""Conservative event-granularity overlay for MingGui trajectory research.

NON-DESTRUCTIVE: preserve the original (domain,event_type) and raw source records.
These tags separate changes in life state from recurring creative/public output.
Tags are NOT claims of moral importance, event quality, causal importance,
or reliable historical observation.

Unrecognized types stay UNKNOWN and remain retained for review.
"""
from __future__ import annotations

from enum import Enum
from typing import Mapping


class Granularity(str, Enum):
    LIFE_TRANSITION = "life_transition"
    ACHIEVEMENT = "achievement"
    REPEATED_OUTPUT = "repeated_output"
    UNKNOWN = "unclassified"


TRANSITION_TYPES = frozenset({
    "career.position.start",
    "career.position.end",
    "career.team.start",
    "career.team.end",
    "career.role_start",
    "career.appointment",
    "career.retirement",
    "career.employer.start",
    "career.employer.end",
    "career.occupation.start",
    "career.occupation.end",
    "relationship.marriage",
    "relationship.divorce",
    "relationship.spouse.start",
    "relationship.spouse.end",
    "family.child_birth",
    "education.complete",
    "education.affiliation.start",
    "education.affiliation.end",
    "organization.member.start",
    "organization.member.end",
    "organization.found",
    "creation.organization_founded",
    "migration.cross_region",
    "recognition.election",
})

REPEATED_OUTPUT_TYPES = frozenset({
    "creation.music_release_group",
    "creation.scholar_work",
    "creation.release",
    "creation.notable_work",
    "creation.publication",
    "performance.music_event",
})

ACHIEVEMENT_TYPES = frozenset({
    "recognition.award",
})

# Do not guess a tag for an unseen ontology type without manual review.
assert not (TRANSITION_TYPES & REPEATED_OUTPUT_TYPES)
assert not (TRANSITION_TYPES & ACHIEVEMENT_TYPES)
assert not (REPEATED_OUTPUT_TYPES & ACHIEVEMENT_TYPES)


def classify(domain: str | None, event_type: str | None) -> Granularity:
    e = (event_type or "").strip().lower()
    if e in TRANSITION_TYPES:
        return Granularity.LIFE_TRANSITION
    if e in REPEATED_OUTPUT_TYPES:
        return Granularity.REPEATED_OUTPUT
    if e in ACHIEVEMENT_TYPES:
        return Granularity.ACHIEVEMENT
    return Granularity.UNKNOWN


def enrich(record: Mapping) -> dict:
    """Add granularity without dropping, normalizing or rewriting source facts."""
    r = dict(record)
    r["model_granularity_v1"] = classify(
        r.get("domain"), r.get("event_type")
    ).value
    return r
