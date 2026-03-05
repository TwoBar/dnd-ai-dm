"""
Multiclass Calculator

Handles all multiclass calculations and edge cases explicitly.
Implements all 10 known D&D 5E multiclass rules without complex detection.
"""

import math
from typing import Dict, List, Optional, Tuple
import sqlite3
from pathlib import Path


class MulticlassCalculator:
    """
    Calculates multiclass-related values for characters.

    All D&D 5E multiclass edge cases are handled explicitly:
    1. Warlock Pact Magic (separate slots)
    2. Unarmored Defense conflicts
    3. Fighting Style duplicates
    4. Extra Attack stacking
    5. Channel Divinity uses
    6. Spellcasting abilities
    7. Spell preparation
    8. Proficiency bonus
    9. Multiclass spell slot calculation
    10. Prerequisites checking
    """

    # Multiclass Spell Slot Table (PHB p. 165)
    MULTICLASS_SPELL_SLOTS = {
        1:  [2, 0, 0, 0, 0, 0, 0, 0, 0],
        2:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
        3:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
        4:  [4, 3, 0, 0, 0, 0, 0, 0, 0],
        5:  [4, 3, 2, 0, 0, 0, 0, 0, 0],
        6:  [4, 3, 3, 0, 0, 0, 0, 0, 0],
        7:  [4, 3, 3, 1, 0, 0, 0, 0, 0],
        8:  [4, 3, 3, 2, 0, 0, 0, 0, 0],
        9:  [4, 3, 3, 3, 1, 0, 0, 0, 0],
        10: [4, 3, 3, 3, 2, 0, 0, 0, 0],
        11: [4, 3, 3, 3, 2, 1, 0, 0, 0],
        12: [4, 3, 3, 3, 2, 1, 0, 0, 0],
        13: [4, 3, 3, 3, 2, 1, 1, 0, 0],
        14: [4, 3, 3, 3, 2, 1, 1, 0, 0],
        15: [4, 3, 3, 3, 2, 1, 1, 1, 0],
        16: [4, 3, 3, 3, 2, 1, 1, 1, 0],
        17: [4, 3, 3, 3, 2, 1, 1, 1, 1],
        18: [4, 3, 3, 3, 3, 1, 1, 1, 1],
        19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
        20: [4, 3, 3, 3, 3, 2, 2, 1, 1],
    }

    def __init__(self, reference_db_path: str):
        """Initialize with reference database path"""
        self.reference_db_path = reference_db_path

    def _get_class_data(self, class_id: str) -> Dict:
        """Get class data from reference database"""
        conn = sqlite3.connect(self.reference_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        class_data = cursor.execute(
            "SELECT * FROM classes WHERE id = ?", (class_id,)
        ).fetchone()

        conn.close()

        if not class_data:
            raise ValueError(f"Class not found: {class_id}")

        return dict(class_data)

    # ============================================================
    # Rule 1: Warlock Pact Magic (Separate Slots)
    # ============================================================

    def calculate_pact_magic_slots(self, warlock_level: int) -> Optional[Dict[str, int]]:
        """
        Calculate Warlock Pact Magic slots separately.

        Pact Magic doesn't combine with Spellcasting feature.

        Args:
            warlock_level: Character's Warlock class level

        Returns:
            {"count": 2, "level": 2, "used": 0} or None if no Warlock
        """
        if warlock_level == 0:
            return None

        # Pact Magic slots table (PHB p. 107)
        slots_by_level = {
            1: {"count": 1, "level": 1},
            2: {"count": 2, "level": 1},
            3: {"count": 2, "level": 2},
            4: {"count": 2, "level": 2},
            5: {"count": 2, "level": 3},
            6: {"count": 2, "level": 3},
            7: {"count": 2, "level": 4},
            8: {"count": 2, "level": 4},
            9: {"count": 2, "level": 5},
            10: {"count": 2, "level": 5},
            11: {"count": 3, "level": 5},
            12: {"count": 3, "level": 5},
            13: {"count": 3, "level": 5},
            14: {"count": 3, "level": 5},
            15: {"count": 3, "level": 5},
            16: {"count": 3, "level": 5},
            17: {"count": 4, "level": 5},
            18: {"count": 4, "level": 5},
            19: {"count": 4, "level": 5},
            20: {"count": 4, "level": 5},
        }

        slots = slots_by_level.get(warlock_level, {"count": 0, "level": 0})
        return {**slots, "used": 0}

    # ============================================================
    # Rule 2: Unarmored Defense Conflicts
    # ============================================================

    def resolve_unarmored_defense(
        self,
        has_barbarian: bool,
        has_monk: bool,
        choice: Optional[str] = None
    ) -> str:
        """
        Resolve Unarmored Defense conflict between Barbarian and Monk.

        Both classes grant Unarmored Defense:
        - Barbarian: 10 + DEX + CON
        - Monk: 10 + DEX + WIS

        Character must choose one.

        Args:
            has_barbarian: Character has Barbarian levels
            has_monk: Character has Monk levels
            choice: 'barbarian' or 'monk' (required if both true)

        Returns:
            'barbarian', 'monk', or 'none'

        Raises:
            ValueError: If both classes and no choice provided
        """
        if has_barbarian and has_monk:
            if not choice:
                raise ValueError(
                    "Character has both Barbarian and Monk. "
                    "Must choose which Unarmored Defense to use."
                )
            if choice not in ['barbarian', 'monk']:
                raise ValueError(f"Invalid Unarmored Defense choice: {choice}")
            return choice
        elif has_barbarian:
            return 'barbarian'
        elif has_monk:
            return 'monk'
        else:
            return 'none'

    # ============================================================
    # Rule 3: Fighting Style Duplicates
    # ============================================================

    def check_fighting_style_duplicate(
        self,
        existing_styles: List[str],
        new_style: str
    ) -> bool:
        """
        Check if a Fighting Style is already known.

        You cannot take the same Fighting Style twice.

        Args:
            existing_styles: List of already-known Fighting Style names
            new_style: Fighting Style being considered

        Returns:
            True if allowed (not a duplicate), False if duplicate
        """
        return new_style not in existing_styles

    # ============================================================
    # Rule 4: Extra Attack Stacking
    # ============================================================

    def calculate_extra_attack(self, class_levels: Dict[str, int]) -> int:
        """
        Calculate Extra Attack feature.

        Extra Attack does NOT stack from multiclassing.
        Fighter gets more attacks at higher levels.

        Args:
            class_levels: {'class:fighter': 11, 'class:barbarian': 5}

        Returns:
            Number of attacks (1-4)
        """
        fighter_level = class_levels.get('class:fighter', 0)

        # Fighter gets Extra Attack (2) at 5, Extra Attack (3) at 11, Extra Attack (4) at 20
        if fighter_level >= 20:
            return 4
        elif fighter_level >= 11:
            return 3
        elif fighter_level >= 5:
            return 2

        # Other classes with Extra Attack at level 5
        extra_attack_classes = [
            'class:barbarian', 'class:paladin', 'class:ranger',
            'class:monk', 'class:bard'  # Bard (College of Valor/Swords)
        ]

        for class_id in extra_attack_classes:
            if class_levels.get(class_id, 0) >= 5:
                return 2

        return 1  # Base: 1 attack

    # ============================================================
    # Rule 5: Channel Divinity Uses
    # ============================================================

    def calculate_channel_divinity(self, class_levels: Dict[str, int]) -> Dict[str, int]:
        """
        Calculate Channel Divinity uses.

        Cleric and Paladin Channel Divinity DO stack.
        Uses increase at specific levels.

        Args:
            class_levels: {'class:cleric': 6, 'class:paladin': 3}

        Returns:
            {"uses": 2, "options": ["Turn Undead", "Preserve Life", "Sacred Weapon"]}
        """
        cleric_level = class_levels.get('class:cleric', 0)
        paladin_level = class_levels.get('class:paladin', 0)

        uses = 0

        # Cleric: 1 use at 2, 2 uses at 6, 3 uses at 18
        if cleric_level >= 18:
            uses += 3
        elif cleric_level >= 6:
            uses += 2
        elif cleric_level >= 2:
            uses += 1

        # Paladin: 1 use at 3
        if paladin_level >= 3:
            uses += 1

        return {"uses": uses}

    # ============================================================
    # Rule 6: Spellcasting Abilities
    # ============================================================

    def get_spellcasting_abilities(self, class_levels: Dict[str, int]) -> Dict[str, str]:
        """
        Get spellcasting ability for each class.

        Each class uses its own spellcasting ability.

        Args:
            class_levels: {'class:bard': 3, 'class:paladin': 5}

        Returns:
            {'class:bard': 'cha', 'class:paladin': 'cha'}
        """
        # Spellcasting ability by class
        SPELLCASTING_ABILITIES = {
            'class:bard': 'cha',
            'class:cleric': 'wis',
            'class:druid': 'wis',
            'class:paladin': 'cha',
            'class:ranger': 'wis',
            'class:sorcerer': 'cha',
            'class:warlock': 'cha',
            'class:wizard': 'int',
        }

        abilities = {}
        for class_id in class_levels.keys():
            if class_id in SPELLCASTING_ABILITIES:
                abilities[class_id] = SPELLCASTING_ABILITIES[class_id]

        return abilities

    # ============================================================
    # Rule 7: Spell Preparation
    # ============================================================

    def calculate_prepared_spells(
        self,
        class_id: str,
        class_level: int,
        ability_modifier: int
    ) -> Optional[int]:
        """
        Calculate number of prepared spells for a class.

        Applies only to prepared casters (Cleric, Druid, Paladin, Wizard).
        Known casters (Bard, Sorcerer) don't prepare.

        Args:
            class_id: 'class:cleric'
            class_level: 5
            ability_modifier: 3 (Wisdom modifier)

        Returns:
            Number of spells that can be prepared, or None if not a prepared caster
        """
        PREPARED_CASTERS = {
            'class:cleric': 'wis',
            'class:druid': 'wis',
            'class:paladin': 'cha',
            'class:wizard': 'int',
        }

        if class_id not in PREPARED_CASTERS:
            return None

        # Formula: class_level + ability_modifier (minimum 1)
        prepared = max(1, class_level + ability_modifier)
        return prepared

    # ============================================================
    # Rule 8: Proficiency Bonus
    # ============================================================

    def calculate_proficiency_bonus(self, total_level: int) -> int:
        """
        Calculate proficiency bonus from total character level.

        Formula: floor((total_level - 1) / 4) + 2

        Args:
            total_level: Sum of all class levels

        Returns:
            Proficiency bonus (2-6)
        """
        return math.floor((total_level - 1) / 4) + 2

    # ============================================================
    # Rule 9: Multiclass Spell Slot Calculation
    # ============================================================

    def calculate_multiclass_spell_slots(
        self,
        class_levels: Dict[str, int]
    ) -> Dict[int, int]:
        """
        Calculate spell slots for multiclass characters.

        Combines all Spellcasting classes (excludes Pact Magic).

        Formula:
        - Full casters (Bard, Cleric, Druid, Sorcerer, Wizard): level × 1.0
        - Half casters (Paladin, Ranger): level × 0.5
        - Third casters (Eldritch Knight, Arcane Trickster): level × 0.33
        - Pact Magic (Warlock): NOT included

        Args:
            class_levels: {'class:bard': 3, 'class:paladin': 5}

        Returns:
            {1: 4, 2: 3, 3: 2} - spell slots by level
        """
        # Caster level multipliers
        CASTER_MULTIPLIERS = {
            'class:bard': 1.0,
            'class:cleric': 1.0,
            'class:druid': 1.0,
            'class:sorcerer': 1.0,
            'class:wizard': 1.0,
            'class:paladin': 0.5,
            'class:ranger': 0.5,
            'class:fighter': 0.33,  # Eldritch Knight
            'class:rogue': 0.33,    # Arcane Trickster
        }

        # Calculate total caster level
        caster_level = 0
        for class_id, class_level in class_levels.items():
            multiplier = CASTER_MULTIPLIERS.get(class_id, 0)
            caster_level += math.floor(class_level * multiplier)

        if caster_level == 0:
            return {}

        # Look up spell slots in multiclass table
        caster_level = min(20, max(1, caster_level))
        slots_list = self.MULTICLASS_SPELL_SLOTS[caster_level]

        # Convert to dictionary
        slots = {}
        for level, count in enumerate(slots_list, start=1):
            if count > 0:
                slots[level] = count

        return slots

    # ============================================================
    # Rule 10: Multiclass Prerequisites
    # ============================================================

    def check_multiclass_prerequisites(
        self,
        class_id: str,
        ability_scores: Dict[str, int]
    ) -> Tuple[bool, str]:
        """
        Check if character meets multiclass prerequisites.

        PHB p. 163: "To qualify for a new class, you must meet the ability score
        prerequisites for both your current class and your new one."

        Args:
            class_id: 'class:paladin'
            ability_scores: {'str': 15, 'dex': 10, 'con': 14, 'int': 8, 'wis': 12, 'cha': 13}

        Returns:
            (meets_requirements: bool, message: str)
        """
        PREREQUISITES = {
            'class:barbarian': {'str': 13},
            'class:bard': {'cha': 13},
            'class:cleric': {'wis': 13},
            'class:druid': {'wis': 13},
            'class:fighter': {'str': 13, 'dex': 13},  # STR OR DEX
            'class:monk': {'dex': 13, 'wis': 13},
            'class:paladin': {'str': 13, 'cha': 13},
            'class:ranger': {'dex': 13, 'wis': 13},
            'class:rogue': {'dex': 13},
            'class:sorcerer': {'cha': 13},
            'class:warlock': {'cha': 13},
            'class:wizard': {'int': 13},
        }

        prereqs = PREREQUISITES.get(class_id, {})
        if not prereqs:
            return (True, "No prerequisites")

        # Special case: Fighter can use STR OR DEX
        if class_id == 'class:fighter':
            if ability_scores['str'] >= 13 or ability_scores['dex'] >= 13:
                return (True, "Meets prerequisites")
            else:
                return (False, "Requires STR 13 or DEX 13")

        # Check all prerequisites
        failed = []
        for ability, required in prereqs.items():
            if ability_scores.get(ability, 0) < required:
                failed.append(f"{ability.upper()} {required}")

        if failed:
            return (False, f"Requires: {', '.join(failed)}")
        else:
            return (True, "Meets prerequisites")
