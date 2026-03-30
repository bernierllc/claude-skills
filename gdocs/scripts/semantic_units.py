#!/usr/bin/env python3
"""
Semantic Units - Data structures for content integration.

Represents discrete pieces of information extracted from source content
and how they should be integrated into documents.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any, List
from enum import Enum


# Type definitions
UnitType = Literal[
    'timeline',           # Dates, milestones, schedules
    'feature',            # Product features, capabilities
    'decision',           # Decisions made, approvals
    'risk',               # Risks, challenges, concerns
    'metric',             # Measurements, KPIs, ROI
    'action_item',        # Tasks, action items, todos
    'team_assignment',    # Role assignments, team members
    'technical_detail',   # Implementation details, architecture
    'requirement',        # Requirements, specifications
    'business_impact',    # Business value, outcomes
    'dependency',         # Dependencies, prerequisites
    'resource',           # Budget, resources, tools
]

IntegrationAction = Literal[
    'add',      # Add new content (doesn't exist)
    'update',   # Replace existing content (outdated)
    'merge',    # Combine with existing content (complementary)
    'skip'      # Don't add (duplicate or irrelevant)
]


@dataclass
class SemanticUnit:
    """
    A discrete piece of information extracted from source content.

    Represents one fact, decision, timeline item, etc. that needs to
    be integrated into the target document.
    """

    type: UnitType
    content: str
    priority: int  # 1-5, where 5 is highest priority
    source_line: int  # Line number in original content
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate after initialization."""
        if not 1 <= self.priority <= 5:
            raise ValueError(f"Priority must be 1-5, got {self.priority}")

        if not self.content.strip():
            raise ValueError("Content cannot be empty")

    def __str__(self) -> str:
        """Human-readable representation."""
        content_preview = self.content[:60] + "..." if len(self.content) > 60 else self.content
        return f"{self.type.upper()}: {content_preview} (priority: {self.priority})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'type': self.type,
            'content': self.content,
            'priority': self.priority,
            'source_line': self.source_line,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SemanticUnit':
        """Create from dictionary."""
        return cls(
            type=data['type'],
            content=data['content'],
            priority=data['priority'],
            source_line=data['source_line'],
            metadata=data.get('metadata', {})
        )


@dataclass
class MatchedSection:
    """A document section that matches a semantic unit."""

    section_name: str
    section: Dict[str, Any]  # Full section data from document
    confidence: float  # 0.0-1.0
    reasoning: str

    def __post_init__(self):
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class ExistingContent:
    """Existing content in document that relates to a semantic unit."""

    match_type: Literal['exact', 'partial', 'semantic']
    content: str
    start_index: int
    end_index: int
    confidence: float
    reasoning: str

    def __post_init__(self):
        """Validate indices and confidence."""
        if self.start_index < 0:
            raise ValueError(f"start_index cannot be negative: {self.start_index}")
        if self.end_index <= self.start_index:
            raise ValueError(f"end_index must be > start_index: {self.end_index} <= {self.start_index}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")

    @property
    def length(self) -> int:
        """Length of matched content."""
        return self.end_index - self.start_index


@dataclass
class IntegrationStrategy:
    """
    Complete strategy for integrating one semantic unit into document.

    Describes exactly how a unit should be integrated: where, how, and why.
    """

    unit: SemanticUnit
    action: IntegrationAction
    target_section: str
    target_index: int
    existing_content: Optional[ExistingContent]
    new_content: str
    confidence: float
    reasoning: str

    # Optional formatting instructions
    formatting: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate strategy."""
        if self.target_index < 0:
            raise ValueError(f"target_index cannot be negative: {self.target_index}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")

        # Validate action logic
        if self.action == 'update' and self.existing_content is None:
            raise ValueError("UPDATE action requires existing_content")
        if self.action == 'skip' and self.existing_content is None:
            raise ValueError("SKIP action requires existing_content (showing what's skipped)")

    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"{self.action.upper()} in '{self.target_section}' "
            f"(confidence: {self.confidence:.0%}): {self.unit.content[:50]}..."
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'unit': self.unit.to_dict(),
            'action': self.action,
            'target_section': self.target_section,
            'target_index': self.target_index,
            'existing_content': {
                'match_type': self.existing_content.match_type,
                'content': self.existing_content.content,
                'start_index': self.existing_content.start_index,
                'end_index': self.existing_content.end_index,
                'confidence': self.existing_content.confidence,
                'reasoning': self.existing_content.reasoning
            } if self.existing_content else None,
            'new_content': self.new_content,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'formatting': self.formatting
        }


@dataclass
class IntegrationResult:
    """Result of executing integration strategies."""

    success: bool
    units_processed: int
    actions_executed: int
    actions_skipped: int
    sections_modified: List[str]
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0

    def __str__(self) -> str:
        """Human-readable summary."""
        if self.success:
            return (
                f"✅ Integration successful: "
                f"{self.actions_executed} changes in {len(self.sections_modified)} sections "
                f"({self.actions_skipped} skipped) "
                f"[{self.execution_time:.2f}s]"
            )
        else:
            return (
                f"❌ Integration failed: {len(self.errors)} errors "
                f"({self.actions_executed} changes succeeded before failure)"
            )


# Helper functions

def create_timeline_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create a timeline semantic unit."""
    return SemanticUnit(
        type='timeline',
        content=content,
        priority=4,  # Timelines are high priority
        source_line=source_line,
        metadata=metadata
    )


def create_feature_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create a feature semantic unit."""
    return SemanticUnit(
        type='feature',
        content=content,
        priority=3,  # Features are medium-high priority
        source_line=source_line,
        metadata=metadata
    )


def create_decision_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create a decision semantic unit."""
    return SemanticUnit(
        type='decision',
        content=content,
        priority=4,  # Decisions are high priority
        source_line=source_line,
        metadata=metadata
    )


def create_metric_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create a metric semantic unit."""
    return SemanticUnit(
        type='metric',
        content=content,
        priority=3,  # Metrics are medium-high priority
        source_line=source_line,
        metadata=metadata
    )


def create_risk_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create a risk semantic unit."""
    return SemanticUnit(
        type='risk',
        content=content,
        priority=4,  # Risks are high priority
        source_line=source_line,
        metadata=metadata
    )


def create_action_item_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create an action item semantic unit."""
    return SemanticUnit(
        type='action_item',
        content=content,
        priority=5,  # Action items are highest priority
        source_line=source_line,
        metadata=metadata
    )


def create_team_assignment_unit(content: str, source_line: int, **metadata) -> SemanticUnit:
    """Create a team assignment semantic unit."""
    return SemanticUnit(
        type='team_assignment',
        content=content,
        priority=3,  # Team assignments are medium-high priority
        source_line=source_line,
        metadata=metadata
    )


# Validation utilities

def validate_units(units: List[SemanticUnit]) -> List[str]:
    """
    Validate a list of semantic units.

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []

    for i, unit in enumerate(units):
        try:
            # Validate priority
            if not 1 <= unit.priority <= 5:
                errors.append(f"Unit {i}: Invalid priority {unit.priority}")

            # Validate content
            if not unit.content.strip():
                errors.append(f"Unit {i}: Empty content")

            # Validate type
            valid_types = [
                'timeline', 'feature', 'decision', 'risk', 'metric',
                'action_item', 'team_assignment', 'technical_detail',
                'requirement', 'business_impact', 'dependency', 'resource'
            ]
            if unit.type not in valid_types:
                errors.append(f"Unit {i}: Invalid type '{unit.type}'")

        except Exception as e:
            errors.append(f"Unit {i}: {str(e)}")

    return errors


def validate_strategies(strategies: List[IntegrationStrategy]) -> List[str]:
    """
    Validate a list of integration strategies.

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []

    for i, strategy in enumerate(strategies):
        try:
            # Validate action logic
            if strategy.action == 'update' and strategy.existing_content is None:
                errors.append(f"Strategy {i}: UPDATE requires existing_content")

            if strategy.action == 'skip' and strategy.existing_content is None:
                errors.append(f"Strategy {i}: SKIP requires existing_content")

            # Validate indices
            if strategy.target_index < 0:
                errors.append(f"Strategy {i}: Invalid target_index {strategy.target_index}")

            # Validate confidence
            if not 0.0 <= strategy.confidence <= 1.0:
                errors.append(f"Strategy {i}: Invalid confidence {strategy.confidence}")

        except Exception as e:
            errors.append(f"Strategy {i}: {str(e)}")

    return errors
