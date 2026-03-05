"""
Command agent package - split from the monolithic command_agent.py.

Re-exports for backward compatibility.
"""
from agent.command.command_agent import CommandAgent

__all__ = ['CommandAgent']
