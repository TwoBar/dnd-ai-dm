"""Game state manager - Tracks combat, characters, dice rolls"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class Character:
    """Player character"""
    name: str
    class_name: str
    level: int
    hp: int
    max_hp: int
    ac: int
    initiative: Optional[int] = None
    conditions: List[str] = field(default_factory=list)
    race: Optional[str] = None
    ability_scores: Optional[Dict[str, int]] = None
    background: Optional[str] = None
    is_draft: bool = False
    spell_slots: Optional[Dict[int, int]] = None
    spells_known: Optional[List[str]] = None

    def to_display(self) -> str:
        """Format for display"""
        conditions_str = f" [{', '.join(self.conditions)}]" if self.conditions else ""
        race_str = f" {self.race}" if self.race else ""
        draft_str = " [DRAFT]" if self.is_draft else ""
        return f"{self.name} (Lvl {self.level}{race_str} {self.class_name}) - HP: {self.hp}/{self.max_hp}, AC: {self.ac}{conditions_str}{draft_str}"


@dataclass
class Monster:
    """Monster in combat"""
    name: str
    hp: int
    max_hp: int
    ac: int
    cr: float
    initiative: Optional[int] = None
    conditions: List[str] = field(default_factory=list)

    def to_display(self) -> str:
        """Format for display"""
        conditions_str = f" [{', '.join(self.conditions)}]" if self.conditions else ""
        return f"{self.name} - HP: {self.hp}/{self.max_hp}, AC: {self.ac}, CR: {self.cr}{conditions_str}"


@dataclass
class DiceRoll:
    """Dice roll result"""
    timestamp: datetime
    type: str  # "attack", "damage", "save", "check", "other"
    notation: str
    result: int
    description: str
    critical: bool = False
    fumble: bool = False

    def to_display(self) -> str:
        """Format for display"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        crit_str = " [CRIT!]" if self.critical else " [FUMBLE!]" if self.fumble else ""
        return f"[{time_str}] {self.type.upper()}: {self.description} = {self.result}{crit_str}"


@dataclass
class CombatEvent:
    """Combat log entry"""
    timestamp: datetime
    actor: str
    action: str
    target: Optional[str] = None
    result: Optional[str] = None

    def to_display(self) -> str:
        """Format for display"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        if self.target:
            msg = f"{self.actor} → {self.target}: {self.action}"
        else:
            msg = f"{self.actor}: {self.action}"

        if self.result:
            msg += f" → {self.result}"

        return f"[{time_str}] {msg}"


class GameState:
    """Manages game state across sessions"""

    def __init__(self, event_bus=None):
        self.characters: List[Character] = []
        self.monsters: List[Monster] = []
        self.dice_rolls: List[DiceRoll] = []
        self.combat_log: List[CombatEvent] = []
        self.in_combat: bool = False
        self.current_turn: Optional[str] = None
        self.round_number: int = 0
        self._event_bus = event_bus

    def _emit(self, event_type_name: str, payload: dict):
        """Emit an event if event bus is wired."""
        if not self._event_bus:
            return
        try:
            from core.events import EventType, GameEvent
            event_type = EventType[event_type_name]
            self._event_bus.emit(GameEvent(
                event_type=event_type,
                payload=payload,
                timestamp=datetime.now(),
                source='GameState',
                session_id=''
            ))
        except (KeyError, ImportError):
            pass

    def add_character(self, character: Character):
        """Add a player character. Prevents duplicates by name (case-insensitive)."""
        existing = self.get_character(character.name)
        if existing:
            idx = next(i for i, c in enumerate(self.characters) if c.name.lower() == character.name.lower())
            self.characters[idx] = character
            print(f"[GameState] Updated existing character '{character.name}' instead of creating duplicate")
        else:
            self.characters.append(character)
        self._emit('CHARACTER_CREATED', {'name': character.name, 'class': character.class_name})

    def add_monster(self, monster: Monster):
        """Add a monster"""
        self.monsters.append(monster)
        self._emit('MONSTER_SPAWNED', {'name': monster.name, 'cr': monster.cr})

    def remove_monster(self, name: str):
        """Remove a monster (defeated)"""
        self.monsters = [m for m in self.monsters if m.name.lower() != name.lower()]

    def log_dice_roll(self, roll: DiceRoll):
        """Log a dice roll"""
        self.dice_rolls.append(roll)
        # Keep last 50 rolls
        if len(self.dice_rolls) > 50:
            self.dice_rolls = self.dice_rolls[-50:]

    def log_combat_event(self, event: CombatEvent):
        """Log a combat event"""
        self.combat_log.append(event)
        # Keep last 50 events
        if len(self.combat_log) > 50:
            self.combat_log = self.combat_log[-50:]

    def start_combat(self):
        """Start combat encounter"""
        self.in_combat = True
        self.round_number = 1
        self.log_combat_event(CombatEvent(
            timestamp=datetime.now(),
            actor="System",
            action="Combat started! Roll initiative!"
        ))
        self._emit('COMBAT_STARTED', {'round': 1})

    def end_combat(self):
        """End combat encounter"""
        self.in_combat = False
        self.current_turn = None
        self.round_number = 0
        # Clear monster initiatives
        for monster in self.monsters:
            monster.initiative = None
        for character in self.characters:
            character.initiative = None
        self.log_combat_event(CombatEvent(
            timestamp=datetime.now(),
            actor="System",
            action="Combat ended!"
        ))

    def next_turn(self):
        """Advance to next turn in initiative order"""
        if not self.in_combat:
            return

        # Get all combatants with initiative
        combatants = []
        for char in self.characters:
            if char.initiative is not None:
                combatants.append((char.name, char.initiative, "character"))
        for monster in self.monsters:
            if monster.initiative is not None:
                combatants.append((monster.name, monster.initiative, "monster"))

        # Sort by initiative (descending)
        combatants.sort(key=lambda x: x[1], reverse=True)

        if not combatants:
            return

        # Find current turn and advance
        if self.current_turn is None:
            self.current_turn = combatants[0][0]
        else:
            current_idx = next((i for i, c in enumerate(combatants) if c[0] == self.current_turn), -1)
            next_idx = (current_idx + 1) % len(combatants)
            self.current_turn = combatants[next_idx][0]

            # New round?
            if next_idx == 0:
                self.round_number += 1
                self.log_combat_event(CombatEvent(
                    timestamp=datetime.now(),
                    actor="System",
                    action=f"Round {self.round_number} begins!"
                ))

    def get_initiative_order(self) -> List[tuple]:
        """Get sorted initiative order"""
        combatants = []
        for char in self.characters:
            if char.initiative is not None:
                combatants.append((char.name, char.initiative, "character"))
        for monster in self.monsters:
            if monster.initiative is not None:
                combatants.append((monster.name, monster.initiative, "monster"))

        combatants.sort(key=lambda x: x[1], reverse=True)
        return combatants

    def damage_character(self, name: str, damage: int):
        """Apply damage to character"""
        for char in self.characters:
            if char.name.lower() == name.lower():
                char.hp = max(0, char.hp - damage)
                self.log_combat_event(CombatEvent(
                    timestamp=datetime.now(),
                    actor=name,
                    action=f"takes {damage} damage",
                    result=f"{char.hp}/{char.max_hp} HP remaining"
                ))
                break

    def damage_monster(self, name: str, damage: int):
        """Apply damage to monster"""
        for monster in self.monsters:
            if monster.name.lower() == name.lower():
                monster.hp = max(0, monster.hp - damage)
                self.log_combat_event(CombatEvent(
                    timestamp=datetime.now(),
                    actor=name,
                    action=f"takes {damage} damage",
                    result=f"{monster.hp}/{monster.max_hp} HP remaining"
                ))

                # Remove if dead
                if monster.hp <= 0:
                    self.remove_monster(name)
                    self.log_combat_event(CombatEvent(
                        timestamp=datetime.now(),
                        actor=name,
                        action="defeated!"
                    ))
                break

    def heal_character(self, name: str, healing: int):
        """Heal character"""
        for char in self.characters:
            if char.name.lower() == name.lower():
                old_hp = char.hp
                char.hp = min(char.max_hp, char.hp + healing)
                actual_healing = char.hp - old_hp
                self.log_combat_event(CombatEvent(
                    timestamp=datetime.now(),
                    actor=name,
                    action=f"healed for {actual_healing} HP",
                    result=f"{char.hp}/{char.max_hp} HP"
                ))
                break

    def get_character(self, name: str) -> Optional[Character]:
        """Get character by name (case-insensitive)"""
        for char in self.characters:
            if char.name.lower() == name.lower():
                return char
        return None

    def get_monster(self, name: str) -> Optional[Monster]:
        """Get monster by name (case-insensitive)"""
        for monster in self.monsters:
            if monster.name.lower() == name.lower():
                return monster
        return None

    def damage_entity(self, name: str, damage: int) -> bool:
        """Apply damage to character or monster"""
        # Try character first
        char = self.get_character(name)
        if char:
            self.damage_character(name, damage)
            return True

        # Try monster
        monster = self.get_monster(name)
        if monster:
            self.damage_monster(name, damage)
            return True

        return False

    def heal_entity(self, name: str, healing: int) -> bool:
        """Heal character or monster"""
        # Try character first
        char = self.get_character(name)
        if char:
            self.heal_character(name, healing)
            return True

        # Try monster (rare but possible)
        monster = self.get_monster(name)
        if monster:
            old_hp = monster.hp
            monster.hp = min(monster.max_hp, monster.hp + healing)
            actual_healing = monster.hp - old_hp
            self.log_combat_event(CombatEvent(
                timestamp=datetime.now(),
                actor=name,
                action=f"healed for {actual_healing} HP",
                result=f"{monster.hp}/{monster.max_hp} HP"
            ))
            return True

        return False

    def add_dice_roll(self, notation: str, result: int, critical: bool = False,
                     fumble: bool = False, roll_type: str = "other",
                     description: str = None):
        """Add a dice roll to the log"""
        if description is None:
            description = notation

        roll = DiceRoll(
            timestamp=datetime.now(),
            type=roll_type,
            notation=notation,
            result=result,
            description=description,
            critical=critical,
            fumble=fumble
        )
        self.log_dice_roll(roll)

    def add_condition(self, name: str, condition: str) -> bool:
        """Add condition to character or monster"""
        # Try character first
        char = self.get_character(name)
        if char:
            if condition not in char.conditions:
                char.conditions.append(condition)
            return True

        # Try monster
        monster = self.get_monster(name)
        if monster:
            if condition not in monster.conditions:
                monster.conditions.append(condition)
            return True

        return False

    def remove_condition(self, name: str, condition: str) -> bool:
        """Remove condition from character or monster"""
        # Try character first
        char = self.get_character(name)
        if char:
            if condition in char.conditions:
                char.conditions.remove(condition)
            return True

        # Try monster
        monster = self.get_monster(name)
        if monster:
            if condition in monster.conditions:
                monster.conditions.remove(condition)
            return True

        return False

    def set_initiative(self, name: str, initiative: int, entity_type: str = "character"):
        """Set initiative for character or monster"""
        if entity_type == "character":
            char = self.get_character(name)
            if char:
                char.initiative = initiative
        else:
            monster = self.get_monster(name)
            if monster:
                monster.initiative = initiative

    @property
    def combat_active(self) -> bool:
        """Check if combat is active. Deprecated: use in_combat instead."""
        import warnings
        warnings.warn("combat_active is deprecated, use in_combat instead", DeprecationWarning, stacklevel=2)
        return self.in_combat

    def get_stats_summary(self) -> Dict:
        """Get summary of game stats"""
        return {
            "characters": len(self.characters),
            "monsters": len(self.monsters),
            "in_combat": self.in_combat,
            "round": self.round_number if self.in_combat else 0,
            "current_turn": self.current_turn,
            "total_rolls": len(self.dice_rolls),
            "total_events": len(self.combat_log)
        }
