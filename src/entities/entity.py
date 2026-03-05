"""
Entity class for modifier aggregation and formula context

Manages:
- Modifier aggregation from database
- Hierarchical modifier matching (e.g., all_saving_throws → saving_throw_dex)
- Caching for performance
- Cache invalidation on changes
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Modifier:
    """Single modifier that applies to a formula"""
    type: str           # 'flat', 'dice', 'advantage', 'disadvantage', 'multiplier'
    value: Any          # 2, '1d4', True, 2.0
    source: str         # 'Robe of the Archmagi', 'Bless', 'Poisoned'
    source_id: str      # 'item:robe-id', 'spell:bless-id'
    duration: str       # 'permanent', 'temporary', 'concentration', 'rounds'
    expires_at: Optional[datetime] = None

    def __repr__(self):
        return f"Modifier({self.type}:{self.value} from {self.source})"


class Entity:
    """
    Lightweight entity wrapper for modifier aggregation.

    Manages:
    - Modifier aggregation from database
    - Caching for performance
    - Cache invalidation on changes

    Usage:
        entity = Entity("creature:lyra-uuid", game_db)
        modifiers = entity.get_spell_save_dc_modifiers()
        # Returns: [Modifier(flat:2 from Robe of the Archmagi)]
    """

    def __init__(self, entity_id: str, db):
        """
        Initialize entity

        Args:
            entity_id: Creature ID (e.g., "creature:uuid-123")
            db: GameStateDB instance
        """
        self.entity_id = entity_id
        self.db = db
        self._modifier_cache: Dict[str, List[Modifier]] = {}
        self._cache_dirty: Set[str] = set()

    # ===== UNIQUE FORMULAS (explicit methods) =====

    def get_spell_save_dc_modifiers(self) -> List[Modifier]:
        """Get modifiers for spell save DC"""
        return self._aggregate_modifiers("spell_save_dc")

    def get_spell_attack_bonus_modifiers(self) -> List[Modifier]:
        """Get modifiers for spell attack bonus"""
        return self._aggregate_modifiers("spell_attack_bonus")

    def get_ac_modifiers(self) -> List[Modifier]:
        """Get modifiers for armor class"""
        return self._aggregate_modifiers("armor_class")

    def get_initiative_modifiers(self) -> List[Modifier]:
        """Get modifiers for initiative"""
        return self._aggregate_modifiers("initiative")

    def get_weapon_damage_modifiers(self) -> List[Modifier]:
        """Get modifiers for weapon damage"""
        return self._aggregate_modifiers("weapon_damage")

    # ===== HIERARCHICAL GROUPS (parameterized methods) =====

    def get_saving_throw_modifiers(self, ability: str) -> List[Modifier]:
        """
        Get modifiers for specific save (str, dex, con, int, wis, cha)
        Includes hierarchical 'all_saving_throws' modifiers

        Args:
            ability: Ability name (e.g., 'dex', 'wis')

        Returns:
            List of modifiers including hierarchical matches
        """
        return self._aggregate_modifiers(f"saving_throw_{ability}")

    def get_skill_modifiers(self, skill: str) -> List[Modifier]:
        """
        Get modifiers for specific skill
        Includes hierarchical 'all_skills' and 'all_checks' modifiers

        Args:
            skill: Skill name (e.g., 'persuasion', 'stealth')

        Returns:
            List of modifiers including hierarchical matches
        """
        return self._aggregate_modifiers(f"skill_{skill}")

    def get_attack_modifiers(self, attack_type: str) -> List[Modifier]:
        """
        Get attack modifiers by type

        Args:
            attack_type: 'melee', 'ranged', 'spell'

        Returns:
            List of modifiers including 'all_attacks' modifiers
        """
        return self._aggregate_modifiers(f"{attack_type}_attack_bonus")

    def get_damage_modifiers(self, damage_type: Optional[str] = None) -> List[Modifier]:
        """
        Get damage modifiers

        Args:
            damage_type: Specific damage type ('fire', 'slashing', etc.) or None for all

        Returns:
            List of modifiers
        """
        if damage_type:
            return self._aggregate_modifiers(f"damage_{damage_type}")
        return self._aggregate_modifiers("damage")

    # ===== FALLBACK FOR RAG-DISCOVERED FORMULAS =====

    def get_modifiers_for(self, target: str) -> List[Modifier]:
        """
        Universal modifier getter for any formula
        (including RAG-discovered formulas)

        Args:
            target: Formula target (e.g., 'grapple_escape_dc')

        Returns:
            List of modifiers
        """
        return self._aggregate_modifiers(target)

    # ===== CORE IMPLEMENTATION =====

    def _aggregate_modifiers(self, target: str) -> List[Modifier]:
        """
        Query database and aggregate all modifiers for target.
        Handles both direct and hierarchical matches.

        Args:
            target: Formula target (e.g., 'spell_save_dc', 'saving_throw_dex')

        Returns:
            List of Modifier objects
        """
        # Check cache
        if target in self._modifier_cache and target not in self._cache_dirty:
            return self._modifier_cache[target]

        modifiers = []

        # 1. Direct modifiers for this specific target
        modifiers.extend(self._query_active_modifiers(target))

        # 2. Hierarchical modifiers based on target pattern
        hierarchical_targets = self._get_hierarchical_targets(target)
        for hier_target in hierarchical_targets:
            modifiers.extend(self._query_active_modifiers(hier_target))

        # Cache result
        self._modifier_cache[target] = modifiers
        self._cache_dirty.discard(target)

        logger.debug(f"Entity {self.entity_id}: Found {len(modifiers)} modifiers for {target}")
        return modifiers

    def _get_hierarchical_targets(self, target: str) -> List[str]:
        """
        Get hierarchical modifier targets that should apply to this target

        Args:
            target: Specific target (e.g., 'saving_throw_dex')

        Returns:
            List of hierarchical targets (e.g., ['all_saving_throws'])
        """
        hierarchical = []

        # Saving throw hierarchy
        if target.startswith("saving_throw_"):
            hierarchical.append("all_saving_throws")

        # Skill hierarchy
        elif target.startswith("skill_"):
            hierarchical.append("all_skills")
            hierarchical.append("all_checks")

        # Attack hierarchy
        elif target.endswith("_attack_bonus") or target == "spell_attack_bonus":
            hierarchical.append("all_attacks")

        # Damage hierarchy
        elif target.startswith("damage_"):
            hierarchical.append("all_damage")

        # Ability check hierarchy
        elif target.startswith("check_"):
            hierarchical.append("all_checks")

        return hierarchical

    def _query_active_modifiers(self, applies_to: str) -> List[Modifier]:
        """
        Query database for active modifiers

        Args:
            applies_to: What the modifier applies to

        Returns:
            List of Modifier objects
        """
        query = """
        SELECT
            modifier_type,
            modifier_value,
            source_name,
            source_id,
            duration_type,
            expires_at
        FROM active_modifiers
        WHERE creature_id = ?
          AND applies_to = ?
          AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY created_at ASC
        """

        try:
            rows = self.db.query(query, (self.entity_id, applies_to))

            return [
                Modifier(
                    type=row['modifier_type'],
                    value=self._parse_value(row['modifier_value'], row['modifier_type']),
                    source=row['source_name'] or 'Unknown',
                    source_id=row['source_id'] or '',
                    duration=row['duration_type'] or 'permanent',
                    expires_at=self._parse_timestamp(row.get('expires_at'))
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to query modifiers for {self.entity_id}, {applies_to}: {e}")
            return []

    def _parse_value(self, value_str: str, modifier_type: str) -> Any:
        """
        Parse modifier value from string

        Args:
            value_str: String value from database
            modifier_type: Type of modifier

        Returns:
            Parsed value (int, str, bool, float)
        """
        if not value_str:
            return 0

        try:
            if modifier_type == 'flat':
                return int(value_str)
            elif modifier_type == 'dice':
                return value_str  # Keep as dice notation string
            elif modifier_type in ('advantage', 'disadvantage'):
                return value_str.lower() in ('true', '1', 'yes')
            elif modifier_type == 'multiplier':
                return float(value_str)
            else:
                return value_str
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse modifier value '{value_str}' as {modifier_type}: {e}")
            return 0

    def _parse_timestamp(self, ts_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime"""
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str)
        except (ValueError, AttributeError):
            return None

    def invalidate_cache(self, formula_names: Optional[List[str]] = None):
        """
        Mark cache as dirty. Called when entity changes.

        Args:
            formula_names: Specific formulas to invalidate, or None for all
        """
        if formula_names is None:
            self._cache_dirty = set(self._modifier_cache.keys())
            logger.debug(f"Entity {self.entity_id}: Invalidated all cached modifiers")
        else:
            self._cache_dirty.update(formula_names)
            logger.debug(f"Entity {self.entity_id}: Invalidated {len(formula_names)} formulas")

    def get_context(self) -> Dict[str, Any]:
        """
        Get base stats for formula execution (ability scores, level, etc.)

        Returns:
            Dictionary of entity stats for formula context
        """
        # Delegate to database query
        return self.db.get_entity_context(self.entity_id)

    def add_modifier(
        self,
        applies_to: str,
        modifier_type: str,
        modifier_value: Any,
        source_name: str,
        source_id: str = '',
        duration_type: str = 'permanent',
        expires_at: Optional[datetime] = None,
        duration_rounds: Optional[int] = None
    ) -> int:
        """
        Add a modifier to this entity

        Args:
            applies_to: What formula this modifies
            modifier_type: Type of modifier
            modifier_value: Value of modifier
            source_name: Source description
            source_id: Source identifier
            duration_type: Duration type
            expires_at: Expiration timestamp
            duration_rounds: Rounds remaining (for combat)

        Returns:
            Modifier ID
        """
        query = """
        INSERT INTO active_modifiers (
            creature_id, applies_to, modifier_type, modifier_value,
            source_name, source_id, duration_type, expires_at,
            duration_rounds, rounds_remaining
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Convert value to string for storage
        value_str = str(modifier_value)

        # Convert datetime to ISO string
        expires_str = expires_at.isoformat() if expires_at else None

        result = self.db.execute(
            query,
            (
                self.entity_id,
                applies_to,
                modifier_type,
                value_str,
                source_name,
                source_id,
                duration_type,
                expires_str,
                duration_rounds,
                duration_rounds  # rounds_remaining starts same as duration_rounds
            )
        )

        # Invalidate cache for this formula
        self.invalidate_cache([applies_to])

        logger.info(f"Added modifier to {self.entity_id}: {modifier_type}:{value_str} to {applies_to} from {source_name}")

        return result

    def remove_modifier(self, modifier_id: int):
        """
        Remove a modifier by ID

        Args:
            modifier_id: ID of modifier to remove
        """
        query = "DELETE FROM active_modifiers WHERE id = ? AND creature_id = ?"
        self.db.execute(query, (modifier_id, self.entity_id))

        # Invalidate all cache since we don't know what formula it affected
        self.invalidate_cache()

        logger.info(f"Removed modifier {modifier_id} from {self.entity_id}")

    def remove_modifiers_by_source(self, source_id: str):
        """
        Remove all modifiers from a specific source

        Args:
            source_id: Source identifier (e.g., 'spell:bless-123')
        """
        query = "DELETE FROM active_modifiers WHERE creature_id = ? AND source_id = ?"
        self.db.execute(query, (self.entity_id, source_id))

        # Invalidate all cache
        self.invalidate_cache()

        logger.info(f"Removed all modifiers from source {source_id} on {self.entity_id}")

    def get_all_modifiers(self) -> List[Dict[str, Any]]:
        """
        Get all active modifiers for this entity

        Returns:
            List of modifier dictionaries
        """
        query = """
        SELECT
            id, applies_to, modifier_type, modifier_value,
            source_name, source_id, duration_type, expires_at,
            duration_rounds, rounds_remaining
        FROM active_modifiers
        WHERE creature_id = ?
          AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY applies_to, created_at
        """

        return self.db.query(query, (self.entity_id,))
