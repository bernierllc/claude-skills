#!/usr/bin/env python3
"""
Content Templates - Pre-configured templates for different content types.

Provides optimized decomposition and integration strategies for specific
content types like meeting notes, feature specs, API docs, etc.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ContentTemplate:
    """Template configuration for a content type."""

    name: str
    description: str
    expected_unit_types: List[str]
    section_mappings: Dict[str, List[str]]  # unit_type -> preferred sections
    formatting_rules: Dict[str, Any]
    priority_boosts: Dict[str, float]  # unit_type -> priority multiplier


class ContentTemplates:
    """Pre-configured templates for common content types."""

    @staticmethod
    def get_template(content_type: str) -> Optional[ContentTemplate]:
        """
        Get template for content type.

        Args:
            content_type: Type of content (meeting_notes, feature_spec, etc.)

        Returns:
            ContentTemplate or None if not found
        """

        templates = {
            'meeting_notes': ContentTemplates.meeting_notes_template(),
            'feature_spec': ContentTemplates.feature_spec_template(),
            'sprint_planning': ContentTemplates.sprint_planning_template(),
            'technical_spec': ContentTemplates.technical_spec_template(),
            'roadmap_update': ContentTemplates.roadmap_update_template(),
            'status_update': ContentTemplates.status_update_template(),
        }

        return templates.get(content_type)

    @staticmethod
    def meeting_notes_template() -> ContentTemplate:
        """Template for meeting notes."""

        return ContentTemplate(
            name='meeting_notes',
            description='Product/project meeting notes with decisions, action items, and timelines',
            expected_unit_types=[
                'timeline', 'feature', 'decision', 'risk', 'metric',
                'action_item', 'team_assignment'
            ],
            section_mappings={
                'timeline': [
                    'development roadmap', 'roadmap', 'timeline', 'schedule',
                    'milestones', 'project timeline'
                ],
                'feature': [
                    'features', 'core features', 'functionality', 'capabilities',
                    'requirements'
                ],
                'decision': [
                    'decisions', 'key decisions', 'outcomes', 'resolutions',
                    'agreements'
                ],
                'risk': [
                    'risks', 'technical risks', 'challenges', 'concerns',
                    'blockers', 'dependencies'
                ],
                'metric': [
                    'business impact', 'metrics', 'kpis', 'roi', 'impact',
                    'success metrics'
                ],
                'action_item': [
                    'next steps', 'action items', 'tasks', 'todos',
                    'follow-up', 'upcoming tasks'
                ],
                'team_assignment': [
                    'team', 'project team', 'roles', 'responsibilities',
                    'assignments', 'ownership'
                ]
            },
            formatting_rules={
                'timeline': {'format': 'bullet', 'prefix': '•'},
                'feature': {'format': 'bullet', 'prefix': '•'},
                'decision': {'format': 'bullet', 'prefix': '✓'},
                'action_item': {'format': 'bullet', 'prefix': '→'},
                'risk': {'format': 'bullet', 'prefix': 'Risk:'},
                'team_assignment': {'format': 'bullet', 'prefix': '•'},
                'metric': {'format': 'bullet', 'prefix': '•'}
            },
            priority_boosts={
                'action_item': 1.2,  # Action items are most important
                'decision': 1.15,
                'timeline': 1.1,
                'risk': 1.1
            }
        )

    @staticmethod
    def feature_spec_template() -> ContentTemplate:
        """Template for feature specifications."""

        return ContentTemplate(
            name='feature_spec',
            description='Detailed feature specification with requirements and technical details',
            expected_unit_types=[
                'requirement', 'feature', 'technical_detail', 'dependency',
                'metric', 'risk'
            ],
            section_mappings={
                'requirement': [
                    'requirements', 'functional requirements', 'specifications',
                    'product requirements'
                ],
                'feature': [
                    'features', 'functionality', 'capabilities', 'user stories'
                ],
                'technical_detail': [
                    'technical architecture', 'architecture', 'implementation',
                    'technical approach', 'system design'
                ],
                'dependency': [
                    'dependencies', 'prerequisites', 'constraints',
                    'external dependencies'
                ],
                'metric': [
                    'success metrics', 'acceptance criteria', 'kpis',
                    'performance requirements'
                ],
                'risk': [
                    'technical risks', 'risks', 'challenges', 'considerations'
                ]
            },
            formatting_rules={
                'requirement': {'format': 'bullet', 'prefix': '•'},
                'feature': {'format': 'bullet', 'prefix': '•'},
                'technical_detail': {'format': 'paragraph'},
                'dependency': {'format': 'bullet', 'prefix': '•'},
                'metric': {'format': 'bullet', 'prefix': '•'}
            },
            priority_boosts={
                'requirement': 1.2,
                'technical_detail': 1.15
            }
        )

    @staticmethod
    def sprint_planning_template() -> ContentTemplate:
        """Template for sprint planning notes."""

        return ContentTemplate(
            name='sprint_planning',
            description='Sprint planning with goals, tasks, and team assignments',
            expected_unit_types=[
                'timeline', 'action_item', 'team_assignment', 'metric',
                'feature', 'risk'
            ],
            section_mappings={
                'timeline': [
                    'sprint goals', 'timeline', 'schedule', 'sprint schedule'
                ],
                'action_item': [
                    'sprint backlog', 'tasks', 'user stories', 'work items'
                ],
                'team_assignment': [
                    'team capacity', 'assignments', 'team', 'ownership'
                ],
                'metric': [
                    'sprint goals', 'success criteria', 'velocity',
                    'capacity planning'
                ],
                'feature': [
                    'features', 'user stories', 'epics', 'deliverables'
                ],
                'risk': [
                    'risks', 'blockers', 'dependencies', 'impediments'
                ]
            },
            formatting_rules={
                'action_item': {'format': 'bullet', 'prefix': '•'},
                'team_assignment': {'format': 'bullet', 'prefix': '•'},
                'timeline': {'format': 'bullet', 'prefix': '•'}
            },
            priority_boosts={
                'action_item': 1.3,
                'team_assignment': 1.2
            }
        )

    @staticmethod
    def technical_spec_template() -> ContentTemplate:
        """Template for technical specifications."""

        return ContentTemplate(
            name='technical_spec',
            description='Technical specification with architecture and implementation details',
            expected_unit_types=[
                'technical_detail', 'requirement', 'dependency', 'risk',
                'decision'
            ],
            section_mappings={
                'technical_detail': [
                    'architecture', 'technical design', 'implementation',
                    'system architecture', 'technical approach'
                ],
                'requirement': [
                    'technical requirements', 'requirements', 'constraints',
                    'specifications'
                ],
                'dependency': [
                    'dependencies', 'external systems', 'integrations',
                    'prerequisites'
                ],
                'risk': [
                    'technical risks', 'challenges', 'considerations',
                    'tradeoffs'
                ],
                'decision': [
                    'architectural decisions', 'technical decisions',
                    'design choices'
                ]
            },
            formatting_rules={
                'technical_detail': {'format': 'paragraph'},
                'requirement': {'format': 'bullet', 'prefix': '•'},
                'dependency': {'format': 'bullet', 'prefix': '•'},
                'decision': {'format': 'bullet', 'prefix': '✓'}
            },
            priority_boosts={
                'technical_detail': 1.3,
                'decision': 1.2
            }
        )

    @staticmethod
    def roadmap_update_template() -> ContentTemplate:
        """Template for roadmap updates."""

        return ContentTemplate(
            name='roadmap_update',
            description='Product roadmap update with timelines and milestones',
            expected_unit_types=[
                'timeline', 'feature', 'metric', 'dependency', 'decision'
            ],
            section_mappings={
                'timeline': [
                    'roadmap', 'timeline', 'milestones', 'schedule',
                    'delivery timeline', 'release schedule'
                ],
                'feature': [
                    'planned features', 'upcoming features', 'features',
                    'deliverables'
                ],
                'metric': [
                    'goals', 'objectives', 'targets', 'success metrics'
                ],
                'dependency': [
                    'dependencies', 'prerequisites', 'blockers'
                ],
                'decision': [
                    'decisions', 'prioritization', 'strategic decisions'
                ]
            },
            formatting_rules={
                'timeline': {'format': 'bullet', 'prefix': '•'},
                'feature': {'format': 'bullet', 'prefix': '•'},
                'metric': {'format': 'bullet', 'prefix': '•'}
            },
            priority_boosts={
                'timeline': 1.3,
                'decision': 1.2
            }
        )

    @staticmethod
    def status_update_template() -> ContentTemplate:
        """Template for project status updates."""

        return ContentTemplate(
            name='status_update',
            description='Project status update with progress and blockers',
            expected_unit_types=[
                'metric', 'action_item', 'risk', 'decision', 'timeline'
            ],
            section_mappings={
                'metric': [
                    'progress', 'metrics', 'status', 'achievements',
                    'completed work'
                ],
                'action_item': [
                    'next steps', 'upcoming work', 'action items',
                    'planned activities'
                ],
                'risk': [
                    'blockers', 'risks', 'issues', 'challenges',
                    'concerns'
                ],
                'decision': [
                    'decisions needed', 'open questions', 'decisions made'
                ],
                'timeline': [
                    'schedule', 'timeline', 'upcoming milestones'
                ]
            },
            formatting_rules={
                'metric': {'format': 'bullet', 'prefix': '•'},
                'action_item': {'format': 'bullet', 'prefix': '→'},
                'risk': {'format': 'bullet', 'prefix': 'Blocker:'}
            },
            priority_boosts={
                'risk': 1.3,
                'action_item': 1.2
            }
        )

    @staticmethod
    def list_available_templates() -> List[Dict[str, str]]:
        """
        List all available templates.

        Returns:
            List of template info dictionaries
        """

        templates = [
            ContentTemplates.meeting_notes_template(),
            ContentTemplates.feature_spec_template(),
            ContentTemplates.sprint_planning_template(),
            ContentTemplates.technical_spec_template(),
            ContentTemplates.roadmap_update_template(),
            ContentTemplates.status_update_template(),
        ]

        return [
            {
                'name': t.name,
                'description': t.description,
                'expected_units': ', '.join(t.expected_unit_types)
            }
            for t in templates
        ]

    @staticmethod
    def auto_detect_template(content: str) -> Optional[str]:
        """
        Auto-detect content type from content.

        Args:
            content: Raw content string

        Returns:
            Template name or None
        """

        content_lower = content.lower()

        # Check for meeting notes indicators
        meeting_indicators = [
            'meeting notes', 'meeting summary', 'attendees:',
            'action items:', 'decisions made', 'next steps:'
        ]
        if any(ind in content_lower for ind in meeting_indicators):
            return 'meeting_notes'

        # Check for feature spec indicators
        spec_indicators = [
            'feature spec', 'requirements:', 'user story',
            'acceptance criteria', 'functional requirements'
        ]
        if any(ind in content_lower for ind in spec_indicators):
            return 'feature_spec'

        # Check for sprint planning indicators
        sprint_indicators = [
            'sprint planning', 'sprint goal', 'sprint backlog',
            'velocity', 'story points'
        ]
        if any(ind in content_lower for ind in sprint_indicators):
            return 'sprint_planning'

        # Check for technical spec indicators
        tech_indicators = [
            'technical spec', 'architecture', 'system design',
            'implementation plan', 'technical approach'
        ]
        if any(ind in content_lower for ind in tech_indicators):
            return 'technical_spec'

        # Check for roadmap indicators
        roadmap_indicators = [
            'roadmap', 'product roadmap', 'release schedule',
            'quarterly plan', 'milestones'
        ]
        if any(ind in content_lower for ind in roadmap_indicators):
            return 'roadmap_update'

        # Check for status update indicators
        status_indicators = [
            'status update', 'weekly update', 'progress report',
            'project status', 'blockers:'
        ]
        if any(ind in content_lower for ind in status_indicators):
            return 'status_update'

        # Default to meeting notes if unclear
        return 'meeting_notes'


# Helper function
def get_template_info(template_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed info about a template."""

    template = ContentTemplates.get_template(template_name)

    if not template:
        return None

    return {
        'name': template.name,
        'description': template.description,
        'expected_units': template.expected_unit_types,
        'section_mappings': template.section_mappings,
        'formatting_rules': template.formatting_rules,
        'priority_boosts': template.priority_boosts
    }
