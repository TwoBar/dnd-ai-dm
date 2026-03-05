"""
Workflow package - split from the original monolithic workflow.py.

Re-exports all public names so existing imports continue to work:
    from game.workflow import WorkflowOrchestrator, WorkflowContext, WorkflowResult
"""

from game.workflow.orchestrator import WorkflowOrchestrator
from game.workflow.context import WorkflowContext, WorkflowResult, WorkflowState
from game.workflow.formatters import format_mechanics_summary
from game.workflow.map_builder import build_map_state

__all__ = [
    'WorkflowOrchestrator',
    'WorkflowContext',
    'WorkflowResult',
    'WorkflowState',
    'format_mechanics_summary',
    'build_map_state',
]
