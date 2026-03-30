#!/usr/bin/env python3
"""
Content Integrator - Production API for intelligent content integration.

Main entry point for integrating content into Google Docs with semantic
understanding, intelligent strategies, and beautiful diff previews.

This is the NEW system that replaces block-based smart_insert() with
line-by-line content integration.
"""

from typing import Dict, Any, Optional, List
import time

from .semantic_units import IntegrationResult
from .content_decomposer import ContentDecomposer
from .semantic_matcher import SemanticMatcher
from .integration_strategy import StrategyDeterminer
from .diff_generator import DiffGenerator
from .integration_executor import IntegrationExecutor
from .content_templates import ContentTemplates


class ContentIntegrator:
    """
    Intelligent content integration for Google Docs.

    Transforms raw content (meeting notes, feature specs, etc.) into
    precise document updates with semantic understanding.
    """

    def __init__(
        self,
        document_service: Any = None,
        show_preview: bool = True,
        dry_run: bool = False
    ):
        """
        Initialize content integrator.

        Args:
            document_service: Google Docs API service (optional for dry run)
            show_preview: Whether to show diff preview before execution
            dry_run: If True, validate and preview but don't execute changes
        """
        self.document_service = document_service
        self.show_preview = show_preview
        self.dry_run = dry_run

        # Initialize components
        self.decomposer = ContentDecomposer()
        self.matcher = SemanticMatcher()
        self.strategy_determiner = StrategyDeterminer()
        self.diff_generator = DiffGenerator()
        self.executor = IntegrationExecutor(dry_run=dry_run)

    def integrate_content(
        self,
        content: str,
        document_sections: List[Dict[str, Any]],
        content_type: Optional[str] = None
    ) -> IntegrationResult:
        """
        Integrate content into document with intelligent strategies.

        This is the main API method that replaces smart_insert().

        Args:
            content: Raw content to integrate (meeting notes, specs, etc.)
            document_sections: Document sections with structure
            content_type: Optional content type hint (auto-detected if None)

        Returns:
            IntegrationResult with execution details

        Example:
            >>> integrator = ContentIntegrator(doc_service)
            >>> result = integrator.integrate_content(
            ...     meeting_notes,
            ...     doc_sections,
            ...     content_type='meeting_notes'
            ... )
            >>> print(f"Applied {result.actions_executed} changes")
        """

        start_time = time.time()

        try:
            # Step 1: Auto-detect content type if not provided
            if content_type is None:
                content_type = ContentTemplates.auto_detect_template(content)
                print(f"📝 Auto-detected content type: {content_type}")

            # Step 2: Decompose content into semantic units
            print(f"\n🔍 Decomposing content...")
            units = self.decomposer.decompose(content, content_type)
            print(f"✅ Extracted {len(units)} semantic units")

            if not units:
                return IntegrationResult(
                    success=True,
                    units_processed=0,
                    actions_executed=0,
                    actions_skipped=0,
                    sections_modified=[],
                    execution_time=time.time() - start_time
                )

            # Step 3: Match units to document sections
            print(f"\n🎯 Matching units to sections...")
            match_results = self.matcher.match_all_units(units, document_sections)
            matched_pairs = [
                (unit, matches[0])
                for unit, matches in match_results
                if matches
            ]
            print(f"✅ Matched {len(matched_pairs)}/{len(units)} units")

            if not matched_pairs:
                return IntegrationResult(
                    success=True,
                    units_processed=len(units),
                    actions_executed=0,
                    actions_skipped=len(units),
                    sections_modified=[],
                    execution_time=time.time() - start_time
                )

            # Step 4: Determine integration strategies
            print(f"\n💡 Determining integration strategies...")
            strategies = self.strategy_determiner.determine_strategies_for_all(matched_pairs)
            strategy_summary = self.strategy_determiner.get_strategy_summary(strategies)

            print(f"✅ Generated {len(strategies)} strategies:")
            print(f"   • ADD: {strategy_summary['actions']['add']}")
            print(f"   • UPDATE: {strategy_summary['actions']['update']}")
            print(f"   • MERGE: {strategy_summary['actions']['merge']}")
            print(f"   • SKIP: {strategy_summary['actions']['skip']}")

            # Step 5: Show diff preview if enabled
            if self.show_preview:
                print(f"\n🔍 Generating preview...\n")
                diff_entries = self.diff_generator.generate_diff(strategies)
                preview = self.diff_generator.generate_interactive_preview(diff_entries)
                print(preview)

                # Ask for confirmation (in real usage, this would be interactive)
                if not self.dry_run and self.document_service:
                    print("Preview generated. Proceeding with execution...\n")

            # Step 6: Execute integration strategies
            print(f"⚙️  Executing integration...")
            result = self.executor.execute(strategies, self.document_service)

            if result.success:
                print(f"\n✅ Integration complete!")
                print(f"   • {result.actions_executed} changes applied")
                print(f"   • {len(result.sections_modified)} sections modified")
            else:
                print(f"\n❌ Integration failed:")
                for error in result.errors:
                    print(f"   • {error}")

            return result

        except Exception as e:
            return IntegrationResult(
                success=False,
                units_processed=0,
                actions_executed=0,
                actions_skipped=0,
                sections_modified=[],
                errors=[f"Integration error: {str(e)}"],
                execution_time=time.time() - start_time
            )

    def preview_integration(
        self,
        content: str,
        document_sections: List[Dict[str, Any]],
        content_type: Optional[str] = None
    ) -> str:
        """
        Preview integration without executing changes.

        Args:
            content: Raw content to integrate
            document_sections: Document sections
            content_type: Optional content type hint

        Returns:
            Formatted preview string
        """

        # Temporarily enable preview and dry-run
        old_preview = self.show_preview
        old_dry_run = self.dry_run

        self.show_preview = True
        self.dry_run = True

        # Run integration (dry run)
        result = self.integrate_content(content, document_sections, content_type)

        # Restore settings
        self.show_preview = old_preview
        self.dry_run = old_dry_run

        return f"Preview complete: {result.actions_executed} changes would be applied"

    def get_integration_plan(
        self,
        content: str,
        document_sections: List[Dict[str, Any]],
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get integration plan without executing or previewing.

        Returns structured plan for programmatic use.

        Args:
            content: Raw content to integrate
            document_sections: Document sections
            content_type: Optional content type hint

        Returns:
            Dictionary with plan details
        """

        # Decompose
        if content_type is None:
            content_type = ContentTemplates.auto_detect_template(content)

        units = self.decomposer.decompose(content, content_type)

        # Match
        match_results = self.matcher.match_all_units(units, document_sections)
        matched_pairs = [
            (unit, matches[0])
            for unit, matches in match_results
            if matches
        ]

        # Determine strategies
        strategies = self.strategy_determiner.determine_strategies_for_all(matched_pairs)
        strategy_summary = self.strategy_determiner.get_strategy_summary(strategies)

        # Generate diff
        diff_entries = self.diff_generator.generate_diff(strategies)
        diff_summary = self.diff_generator.get_diff_summary(diff_entries)

        return {
            'content_type': content_type,
            'units_extracted': len(units),
            'units_matched': len(matched_pairs),
            'strategies': strategy_summary,
            'diff_summary': diff_summary,
            'estimated_changes': len([s for s in strategies if s.action != 'skip'])
        }


# Convenience functions for simple usage

def integrate_meeting_notes(
    meeting_notes: str,
    document_sections: List[Dict[str, Any]],
    document_service: Any = None,
    dry_run: bool = False
) -> IntegrationResult:
    """
    Integrate meeting notes into document.

    Convenience function for the most common use case.

    Args:
        meeting_notes: Raw meeting notes text
        document_sections: Document sections
        document_service: Google Docs API service
        dry_run: If True, preview without executing

    Returns:
        IntegrationResult
    """

    integrator = ContentIntegrator(
        document_service=document_service,
        show_preview=True,
        dry_run=dry_run
    )

    return integrator.integrate_content(
        meeting_notes,
        document_sections,
        content_type='meeting_notes'
    )


def preview_integration(
    content: str,
    document_sections: List[Dict[str, Any]],
    content_type: Optional[str] = None
) -> str:
    """
    Preview integration without making changes.

    Args:
        content: Raw content
        document_sections: Document sections
        content_type: Optional content type

    Returns:
        Preview string
    """

    integrator = ContentIntegrator(dry_run=True, show_preview=True)
    return integrator.preview_integration(content, document_sections, content_type)


def get_integration_plan(
    content: str,
    document_sections: List[Dict[str, Any]],
    content_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get integration plan for programmatic use.

    Args:
        content: Raw content
        document_sections: Document sections
        content_type: Optional content type

    Returns:
        Plan dictionary
    """

    integrator = ContentIntegrator(dry_run=True, show_preview=False)
    return integrator.get_integration_plan(content, document_sections, content_type)
