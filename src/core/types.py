"""
Shared types used across the codebase.

Re-exports from their canonical locations for convenience.
New code can import from core.types for a single entry point.
"""

# Re-export Intent types from their canonical location
from agent.intent_agent import ActionType, SkillType, Intent

# Re-export workflow types from their canonical location
from game.workflow.context import WorkflowContext, WorkflowResult, WorkflowState

__all__ = [
    'ActionType', 'SkillType', 'Intent',
    'WorkflowContext', 'WorkflowResult', 'WorkflowState',
]
