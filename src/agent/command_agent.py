"""
Command Agent - Re-export facade.

The implementation has moved to agent/command/ package.
This file maintains backward compatibility for existing imports.
"""
from agent.command.command_agent import CommandAgent

__all__ = ['CommandAgent']
