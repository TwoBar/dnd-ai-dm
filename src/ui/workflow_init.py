"""
Workflow Initialization - Re-export facade.

The implementation has moved to factory/workflow_factory.py.
This file maintains backward compatibility for existing imports.
"""
from factory.workflow_factory import (
    create_learning_workflow as initialize_workflow,
    get_workflow_stats,
    shutdown_workflow,
)

__all__ = ['initialize_workflow', 'get_workflow_stats', 'shutdown_workflow']
