"""
Event Bus for decoupled state change notification.

Replaces direct GameState mutation with observable events.
Modules subscribe to event types and react without tight coupling.
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """All game event types"""
    # Character events
    CHARACTER_CREATED = "character.created"
    CHARACTER_UPDATED = "character.updated"
    CHARACTER_DAMAGED = "character.damaged"
    CHARACTER_HEALED = "character.healed"
    CHARACTER_DIED = "character.died"

    # Monster events
    MONSTER_SPAWNED = "monster.spawned"
    MONSTER_DAMAGED = "monster.damaged"
    MONSTER_DEFEATED = "monster.defeated"

    # Combat events
    COMBAT_STARTED = "combat.started"
    COMBAT_ENDED = "combat.ended"
    TURN_ADVANCED = "combat.turn_advanced"
    INITIATIVE_SET = "combat.initiative_set"

    # Dice events
    DICE_ROLLED = "dice.rolled"

    # Spatial events
    ENTITY_PLACED = "spatial.entity_placed"
    ENTITY_MOVED = "spatial.entity_moved"
    ENTITY_REMOVED = "spatial.entity_removed"

    # Condition events
    CONDITION_ADDED = "condition.added"
    CONDITION_REMOVED = "condition.removed"

    # Session events
    SESSION_CREATED = "session.created"
    SESSION_ENDED = "session.ended"


@dataclass
class GameEvent:
    """A game event with payload and metadata"""
    event_type: EventType
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    session_id: str = ""


class EventBus:
    """
    Simple synchronous event bus for game state changes.

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.CHARACTER_DAMAGED, my_handler)
        bus.emit(GameEvent(EventType.CHARACTER_DAMAGED, {"name": "Lyra", "damage": 5}))
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[Callable[[GameEvent], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[GameEvent], None]):
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[GameEvent], None]):
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def emit(self, event: GameEvent):
        """Emit an event to all subscribed handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type.value}: {e}")

    def clear(self):
        """Remove all subscriptions."""
        self._handlers.clear()
