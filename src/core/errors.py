"""
Shared error types for the application.

All modules should raise these errors instead of generic exceptions
to enable proper error handling at the workflow level.
"""


class GameError(Exception):
    """Base error for all game-related errors."""
    pass


class EntityNotFoundError(GameError):
    """Raised when a character, monster, or entity cannot be found."""
    def __init__(self, entity_type: str, name: str):
        self.entity_type = entity_type
        self.name = name
        super().__init__(f"{entity_type} '{name}' not found")


class ActionRejectedError(GameError):
    """Raised when an action is impossible (e.g., out of range, no spell slots)."""
    def __init__(self, reason: str, alternatives: list = None):
        self.reason = reason
        self.alternatives = alternatives or []
        super().__init__(reason)


class MechanicsError(GameError):
    """Raised when mechanics execution fails."""
    pass


class SpatialError(GameError):
    """Raised when spatial operations fail."""
    pass


class WorkflowError(GameError):
    """Raised when the workflow pipeline encounters an unrecoverable error."""
    pass
