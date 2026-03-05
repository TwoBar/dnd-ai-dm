"""
Protocol interfaces for ALL agents and services.

Every module depends ONLY on these interfaces, never on concrete classes.
This enables loose coupling and independent testability.
"""
from typing import Protocol, Dict, List, Optional, Any, runtime_checkable


@runtime_checkable
class IntentDetector(Protocol):
    """Detects player intent from natural language messages."""
    def detect(self, message: str, context: Optional[Dict] = None,
               message_history: Optional[List[Dict]] = None) -> Any: ...


@runtime_checkable
class MechanicsExecutor(Protocol):
    """Executes game mechanics (dice rolls, state changes)."""
    def process(self, user_message: str, dm_response: str,
                chat_history: List[Dict]) -> List[Dict]: ...


@runtime_checkable
class NarrativeGenerator(Protocol):
    """Generates narrative responses from the DM."""
    def chat(self, message: str, mechanics_context: str = None) -> str: ...


@runtime_checkable
class GameStateProvider(Protocol):
    """Read-only game state access."""
    @property
    def characters(self) -> List: ...

    @property
    def monsters(self) -> List: ...

    @property
    def in_combat(self) -> bool: ...

    def get_character(self, name: str) -> Optional[Any]: ...
    def get_monster(self, name: str) -> Optional[Any]: ...
    def get_initiative_order(self) -> List[tuple]: ...


@runtime_checkable
class GameStateMutator(Protocol):
    """Write access to game state - only for mechanics layer."""
    def damage_entity(self, name: str, damage: int) -> bool: ...
    def heal_entity(self, name: str, healing: int) -> bool: ...
    def add_character(self, character: Any) -> None: ...
    def add_monster(self, monster: Any) -> None: ...
    def remove_monster(self, name: str) -> None: ...
    def start_combat(self) -> None: ...
    def end_combat(self) -> None: ...


@runtime_checkable
class SpatialProvider(Protocol):
    """Spatial system access for position tracking."""
    def get_entities_near(self, location_id: str, x: float, y: float,
                          radius: float) -> List[Dict]: ...
    def get_entities_in_location(self, location_id: str,
                                  scale_filter: bool = True) -> List[Dict]: ...
    def get_entity_by_creature_id(self, creature_id: str) -> Optional[Dict]: ...
    def remove_entity(self, entity_id: str, caused_by: str = 'removal',
                      reason: Optional[str] = None) -> bool: ...


@runtime_checkable
class ReasoningEngine(Protocol):
    """Iterative reasoning loop for action validation."""
    def reason(self, initial_intent: Any, user_message: str,
               conversation_history: List[Dict], session_id: str,
               context: Optional[Dict] = None) -> Any: ...


@runtime_checkable
class WorkflowProcessor(Protocol):
    """Top-level message processing pipeline."""
    def process_message(self, user_message: str, session_id: str,
                        message_history: List[Dict]) -> Any: ...
