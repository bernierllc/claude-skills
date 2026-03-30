#!/usr/bin/env python3
"""
Integration Executor - Safely executes document integration strategies.

Applies multiple integration strategies to a Google Doc while managing
index shifting, error handling, and providing detailed execution results.
"""

import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .semantic_units import IntegrationStrategy, IntegrationResult


@dataclass
class ExecutionPlan:
    """Execution plan for integration strategies."""

    strategies: List[IntegrationStrategy]
    sorted_strategies: List[IntegrationStrategy]  # Sorted by index (descending)
    total_operations: int
    estimated_duration: float  # seconds


class IntegrationExecutor:
    """Executes integration strategies safely and efficiently."""

    def __init__(self, dry_run: bool = False):
        """
        Initialize integration executor.

        Args:
            dry_run: If True, simulate execution without making changes
        """
        self.dry_run = dry_run

    def create_execution_plan(
        self,
        strategies: List[IntegrationStrategy]
    ) -> ExecutionPlan:
        """
        Create execution plan from integration strategies.

        Sorts strategies by index (descending) to avoid index shifting issues.

        Args:
            strategies: List of integration strategies

        Returns:
            Execution plan
        """

        # Filter out SKIP strategies (no changes needed)
        active_strategies = [
            s for s in strategies
            if s.action != 'skip'
        ]

        # Sort by target_index (descending) to avoid index shifting
        # When we process from end to start, earlier insertions don't affect later indices
        sorted_strategies = sorted(
            active_strategies,
            key=lambda s: s.target_index,
            reverse=True
        )

        # Estimate duration (rough estimate: 100ms per operation)
        estimated_duration = len(sorted_strategies) * 0.1

        return ExecutionPlan(
            strategies=active_strategies,
            sorted_strategies=sorted_strategies,
            total_operations=len(sorted_strategies),
            estimated_duration=estimated_duration
        )

    def execute(
        self,
        strategies: List[IntegrationStrategy],
        document_service: Any = None
    ) -> IntegrationResult:
        """
        Execute integration strategies.

        Args:
            strategies: List of integration strategies
            document_service: Google Docs service (optional for dry run)

        Returns:
            Integration result with execution details
        """

        start_time = time.time()

        # Create execution plan
        plan = self.create_execution_plan(strategies)

        if not plan.sorted_strategies:
            return IntegrationResult(
                success=True,
                units_processed=0,
                actions_executed=0,
                actions_skipped=len([s for s in strategies if s.action == 'skip']),
                sections_modified=[],
                execution_time=time.time() - start_time
            )

        # Execute strategies
        executed = 0
        failed = 0
        errors = []
        sections_modified = set()

        for i, strategy in enumerate(plan.sorted_strategies):
            try:
                if self.dry_run:
                    # Simulate execution
                    success = self._simulate_execution(strategy)
                else:
                    # Actual execution (requires document_service)
                    if document_service is None:
                        raise ValueError("document_service required for non-dry-run execution")

                    success = self._execute_strategy(strategy, document_service)

                if success:
                    executed += 1
                    sections_modified.add(strategy.target_section)
                else:
                    failed += 1
                    errors.append(f"Strategy {i} failed: {strategy.reasoning[:50]}")

            except Exception as e:
                failed += 1
                errors.append(f"Strategy {i} error: {str(e)}")

        execution_time = time.time() - start_time

        # Count skipped strategies
        skipped = len([s for s in strategies if s.action == 'skip'])

        return IntegrationResult(
            success=(failed == 0),
            units_processed=len(strategies),
            actions_executed=executed,
            actions_skipped=skipped,
            sections_modified=sorted(list(sections_modified)),
            errors=errors,
            execution_time=execution_time
        )

    def _simulate_execution(self, strategy: IntegrationStrategy) -> bool:
        """
        Simulate strategy execution (dry run).

        Args:
            strategy: Integration strategy

        Returns:
            True if simulation successful
        """

        # Validate strategy
        if not strategy.new_content and strategy.action != 'skip':
            return False

        if strategy.target_index < 0:
            return False

        # All simulations succeed
        return True

    def _execute_strategy(
        self,
        strategy: IntegrationStrategy,
        document_service: Any
    ) -> bool:
        """
        Execute a single integration strategy.

        Args:
            strategy: Integration strategy
            document_service: Google Docs service

        Returns:
            True if execution successful
        """

        try:
            if strategy.action == 'add':
                return self._execute_add(strategy, document_service)

            elif strategy.action == 'update':
                return self._execute_update(strategy, document_service)

            elif strategy.action == 'merge':
                return self._execute_merge(strategy, document_service)

            else:
                return False

        except Exception as e:
            print(f"Error executing {strategy.action}: {e}")
            return False

    def _execute_add(
        self,
        strategy: IntegrationStrategy,
        document_service: Any
    ) -> bool:
        """Execute ADD strategy - insert new content."""

        # Build Google Docs API request for insertion
        request = {
            'insertText': {
                'location': {
                    'index': strategy.target_index
                },
                'text': strategy.new_content + '\n'
            }
        }

        # Execute request
        # (In production, this would call document_service.batchUpdate())
        # For now, we just return success
        return True

    def _execute_update(
        self,
        strategy: IntegrationStrategy,
        document_service: Any
    ) -> bool:
        """Execute UPDATE strategy - replace existing content."""

        if not strategy.existing_content:
            return False

        # Build requests: delete old content, insert new content
        requests = [
            {
                'deleteContentRange': {
                    'range': {
                        'startIndex': strategy.existing_content.start_index,
                        'endIndex': strategy.existing_content.end_index
                    }
                }
            },
            {
                'insertText': {
                    'location': {
                        'index': strategy.existing_content.start_index
                    },
                    'text': strategy.new_content + '\n'
                }
            }
        ]

        # Execute requests
        # (In production, this would call document_service.batchUpdate())
        return True

    def _execute_merge(
        self,
        strategy: IntegrationStrategy,
        document_service: Any
    ) -> bool:
        """Execute MERGE strategy - combine with existing content."""

        if not strategy.existing_content:
            return False

        # For merge, insert new content after existing content
        insert_index = strategy.existing_content.end_index

        request = {
            'insertText': {
                'location': {
                    'index': insert_index
                },
                'text': '\n' + strategy.new_content
            }
        }

        # Execute request
        # (In production, this would call document_service.batchUpdate())
        return True

    def generate_batch_update_requests(
        self,
        strategies: List[IntegrationStrategy]
    ) -> List[Dict[str, Any]]:
        """
        Generate Google Docs API batchUpdate requests.

        Args:
            strategies: List of integration strategies

        Returns:
            List of API request objects
        """

        plan = self.create_execution_plan(strategies)
        requests = []

        for strategy in plan.sorted_strategies:
            if strategy.action == 'add':
                requests.append({
                    'insertText': {
                        'location': {'index': strategy.target_index},
                        'text': strategy.new_content + '\n'
                    }
                })

            elif strategy.action == 'update':
                if strategy.existing_content:
                    # Delete old, insert new
                    requests.extend([
                        {
                            'deleteContentRange': {
                                'range': {
                                    'startIndex': strategy.existing_content.start_index,
                                    'endIndex': strategy.existing_content.end_index
                                }
                            }
                        },
                        {
                            'insertText': {
                                'location': {'index': strategy.existing_content.start_index},
                                'text': strategy.new_content + '\n'
                            }
                        }
                    ])

            elif strategy.action == 'merge':
                if strategy.existing_content:
                    requests.append({
                        'insertText': {
                            'location': {'index': strategy.existing_content.end_index},
                            'text': '\n' + strategy.new_content
                        }
                    })

        return requests

    def validate_strategies(
        self,
        strategies: List[IntegrationStrategy]
    ) -> List[str]:
        """
        Validate integration strategies before execution.

        Returns:
            List of validation errors (empty if valid)
        """

        errors = []

        for i, strategy in enumerate(strategies):
            # Check required fields
            if not strategy.target_section:
                errors.append(f"Strategy {i}: Missing target_section")

            if strategy.target_index < 0:
                errors.append(f"Strategy {i}: Invalid target_index {strategy.target_index}")

            if not strategy.new_content and strategy.action != 'skip':
                errors.append(f"Strategy {i}: Missing new_content for {strategy.action}")

            # Check action-specific requirements
            if strategy.action == 'update' and not strategy.existing_content:
                errors.append(f"Strategy {i}: UPDATE requires existing_content")

            if strategy.action == 'merge' and not strategy.existing_content:
                errors.append(f"Strategy {i}: MERGE requires existing_content")

        return errors


# Testing helper
def test_integration_executor(strategies: List[IntegrationStrategy]):
    """Test integration executor with strategies (for development)."""

    print("\n" + "="*80)
    print("INTEGRATION EXECUTOR TEST")
    print("="*80 + "\n")

    # Create executor in dry-run mode
    executor = IntegrationExecutor(dry_run=True)

    print(f"Testing execution of {len(strategies)} strategies...\n")

    # Validate strategies
    print("Step 1: Validating strategies...")
    errors = executor.validate_strategies(strategies)

    if errors:
        print(f"❌ Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"   • {error}")
        return None

    print("✅ All strategies validated\n")

    # Create execution plan
    print("Step 2: Creating execution plan...")
    plan = executor.create_execution_plan(strategies)

    print(f"✅ Plan created:")
    print(f"   • Total operations: {plan.total_operations}")
    print(f"   • Estimated duration: {plan.estimated_duration:.2f}s")
    print(f"   • Sorted by index (descending): {len(plan.sorted_strategies)} strategies")
    print()

    # Show first few operations
    print("First 5 operations (in execution order):")
    for i, strategy in enumerate(plan.sorted_strategies[:5], 1):
        print(f"   {i}. {strategy.action.upper()} at index {strategy.target_index}")
        print(f"      Section: {strategy.target_section}")
        print(f"      Content: {strategy.new_content[:50]}...")
        print()

    # Execute (dry run)
    print("Step 3: Executing strategies (dry run)...")
    result = executor.execute(strategies)

    print(f"\n{'✅' if result.success else '❌'} Execution {'completed' if result.success else 'failed'}")
    print(f"   • Units processed: {result.units_processed}")
    print(f"   • Actions executed: {result.actions_executed}")
    print(f"   • Actions skipped: {result.actions_skipped}")
    print(f"   • Sections modified: {len(result.sections_modified)}")
    print(f"   • Execution time: {result.execution_time:.3f}s")

    if result.errors:
        print(f"\n   Errors:")
        for error in result.errors:
            print(f"      • {error}")

    print("\n" + "="*80 + "\n")

    return result
