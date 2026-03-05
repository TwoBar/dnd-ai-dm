"""
WearableManager - Equipment and carrying capacity management

This module handles:
- Equipping and unequipping items
- Slot availability based on body type
- Layering conflicts (can't wear jacket under shirt)
- Dynamic slot creation (additional piercings, pouches)
- Carrying capacity and encumbrance (D&D 5e rules)
- Armor class calculation
"""

import sqlite3
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class EquipmentSlot:
    """Represents an equipment slot"""
    slot_id: str
    name: str
    slot_category: str
    body_part: Optional[str]
    layer_level: int
    is_paired: bool
    currently_equipped: Optional[Dict] = None


@dataclass
class CarryingCapacity:
    """Carrying capacity information"""
    base_capacity: float  # In pounds
    current_weight: float
    encumbrance_level: str
    speed_penalty: int
    has_disadvantage: bool
    affected_checks: Optional[List[str]]


class WearableManager:
    """
    Manages equipment, wearables, and carrying capacity.

    Handles D&D 5e encumbrance rules and equipment slots.
    """

    def __init__(self, reference_db_path: str, game_state_db_path: str):
        """
        Initialize WearableManager.

        Args:
            reference_db_path: Path to reference database
            game_state_db_path: Path to game state database
        """
        self.ref_db_path = reference_db_path
        self.game_db_path = game_state_db_path

    def _get_ref_connection(self) -> sqlite3.Connection:
        """Get connection to reference database"""
        conn = sqlite3.connect(self.ref_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_game_connection(self) -> sqlite3.Connection:
        """Get connection to game state database with reference DB attached"""
        conn = sqlite3.connect(self.game_db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Attach reference database for cross-database queries
        conn.execute(f"ATTACH DATABASE '{self.ref_db_path}' AS ref_db")
        return conn

    # ========================================================================
    # EQUIPMENT SLOT MANAGEMENT
    # ========================================================================

    def get_available_slots(
        self,
        creature_id: str,
        body_type_id: str = 'humanoid'
    ) -> List[EquipmentSlot]:
        """
        Get all available equipment slots for a creature.

        Args:
            creature_id: Creature ID
            body_type_id: Body type (default: humanoid)

        Returns:
            List of EquipmentSlot objects with current equipment
        """
        ref_conn = self._get_ref_connection()
        game_conn = self._get_game_connection()

        try:
            # Get base slots for body type
            ref_cursor = ref_conn.cursor()
            ref_cursor.execute("""
                SELECT es.*
                FROM equipment_slots es
                JOIN body_type_slots bts ON es.id = bts.slot_id
                WHERE bts.body_type_id = ? AND bts.is_available = 1
                ORDER BY es.display_order
            """, (body_type_id,))

            slots = []
            for row in ref_cursor.fetchall():
                slot = EquipmentSlot(
                    slot_id=row['id'],
                    name=row['name'],
                    slot_category=row['slot_category'],
                    body_part=row['body_part'],
                    layer_level=row['layer_level'],
                    is_paired=bool(row['is_paired'])
                )

                # Check if something is equipped
                game_cursor = game_conn.cursor()
                game_cursor.execute("""
                    SELECT ei.*, i.name as item_name, i.weight
                    FROM equipped_items ei
                    JOIN ref_db.items i ON ei.item_id = i.id
                    WHERE ei.creature_id = ? AND ei.slot_id = ? AND ei.is_active = 1
                """, (creature_id, slot.slot_id))

                equipped = game_cursor.fetchone()
                if equipped:
                    slot.currently_equipped = dict(equipped)

                slots.append(slot)

            # Add dynamic slots
            game_cursor = game_conn.cursor()
            game_cursor.execute("""
                SELECT * FROM dynamic_equipment_slots
                WHERE creature_id = ?
            """, (creature_id,))

            for row in game_cursor.fetchall():
                slot = EquipmentSlot(
                    slot_id=row['slot_id'],
                    name=row['slot_name'],
                    slot_category=row['slot_category'],
                    body_part=row['body_part'],
                    layer_level=3,  # Default layer
                    is_paired=False
                )

                # Check if equipped
                game_cursor.execute("""
                    SELECT ei.*, i.name as item_name, i.weight
                    FROM equipped_items ei
                    JOIN ref_db.items i ON ei.item_id = i.id
                    WHERE ei.creature_id = ? AND ei.slot_id = ? AND ei.is_active = 1
                """, (creature_id, slot.slot_id))

                equipped = game_cursor.fetchone()
                if equipped:
                    slot.currently_equipped = dict(equipped)

                slots.append(slot)

            return slots

        finally:
            ref_conn.close()
            game_conn.close()

    def add_dynamic_slot(
        self,
        creature_id: str,
        slot_id: str,
        slot_name: str,
        slot_category: str,
        body_part: str,
        reason: str = "custom"
    ) -> bool:
        """
        Add a dynamic equipment slot for a creature.

        Args:
            creature_id: Creature ID
            slot_id: Unique slot identifier (e.g., "earring_left_2")
            slot_name: Display name
            slot_category: Category (clothing, jewelry, held, carried)
            body_part: Body part
            reason: Why slot was added

        Returns:
            True if added successfully
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dynamic_equipment_slots (
                    creature_id, slot_id, slot_name, slot_category,
                    body_part, added_reason
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (creature_id, slot_id, slot_name, slot_category, body_part, reason))

            conn.commit()
            return True

        except sqlite3.IntegrityError:
            print(f"Slot {slot_id} already exists for creature {creature_id}")
            return False
        finally:
            conn.close()

    # ========================================================================
    # EQUIP / UNEQUIP
    # ========================================================================

    def equip_item(
        self,
        creature_id: str,
        inventory_item_id: int,
        slot_id: str,
        session_id: str,
        caused_by: str = "player_action"
    ) -> Tuple[bool, str]:
        """
        Equip an item from inventory to a slot.

        Args:
            creature_id: Creature ID
            inventory_item_id: Inventory item ID to equip
            slot_id: Target equipment slot
            session_id: Session ID
            caused_by: What triggered this action

        Returns:
            (success, message)
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            # Get inventory item
            cursor.execute("""
                SELECT ci.*, i.name, i.is_wearable, i.equipment_slot_id,
                       i.occupies_slots, i.weight
                FROM creature_inventory ci
                JOIN ref_db.items i ON ci.item_id = i.id
                WHERE ci.id = ? AND ci.creature_id = ?
            """, (inventory_item_id, creature_id))

            inv_item = cursor.fetchone()
            if not inv_item:
                return False, "Item not found in inventory"

            if not inv_item['is_wearable']:
                return False, f"{inv_item['name']} is not wearable"

            # Check if slot is available
            cursor.execute("""
                SELECT * FROM equipped_items
                WHERE creature_id = ? AND slot_id = ? AND is_active = 1
            """, (creature_id, slot_id))

            existing = cursor.fetchone()
            if existing:
                return False, f"Slot {slot_id} is already occupied"

            # Check slot conflicts (layering)
            can_equip, conflict_msg = self._check_slot_conflicts(
                conn, creature_id, slot_id
            )
            if not can_equip:
                return False, conflict_msg

            # Equip the item
            cursor.execute("""
                INSERT INTO equipped_items (
                    creature_id, slot_id, inventory_item_id, item_id, item_name
                ) VALUES (?, ?, ?, ?, ?)
            """, (creature_id, slot_id, inventory_item_id,
                  inv_item['item_id'], inv_item['name']))

            # Log event
            self._log_equipment_event(
                conn, session_id, creature_id, 'equipped',
                slot_id, inv_item['item_id'], inventory_item_id,
                {'item_name': inv_item['name']}, caused_by
            )

            # Recalculate AC if armor
            self._recalculate_armor_class(conn, creature_id)

            # Recalculate carrying capacity
            self._recalculate_carrying_capacity(conn, creature_id, session_id)

            conn.commit()
            return True, f"Equipped {inv_item['name']} to {slot_id}"

        except sqlite3.Error as e:
            conn.rollback()
            return False, f"Database error: {e}"
        finally:
            conn.close()

    def unequip_item(
        self,
        creature_id: str,
        slot_id: str,
        session_id: str,
        caused_by: str = "player_action"
    ) -> Tuple[bool, str]:
        """
        Unequip an item from a slot.

        Args:
            creature_id: Creature ID
            slot_id: Slot to unequip from
            session_id: Session ID
            caused_by: What triggered this action

        Returns:
            (success, message)
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            # Get equipped item
            cursor.execute("""
                SELECT * FROM equipped_items
                WHERE creature_id = ? AND slot_id = ? AND is_active = 1
            """, (creature_id, slot_id))

            equipped = cursor.fetchone()
            if not equipped:
                return False, f"No item equipped in {slot_id}"

            # Remove from equipped
            cursor.execute("""
                DELETE FROM equipped_items
                WHERE id = ?
            """, (equipped['id'],))

            # Log event
            self._log_equipment_event(
                conn, session_id, creature_id, 'unequipped',
                slot_id, equipped['item_id'], equipped['inventory_item_id'],
                {'item_name': equipped['item_name']}, caused_by
            )

            # Recalculate AC
            self._recalculate_armor_class(conn, creature_id)

            # Recalculate carrying capacity
            self._recalculate_carrying_capacity(conn, creature_id, session_id)

            conn.commit()
            return True, f"Unequipped {equipped['item_name']} from {slot_id}"

        except sqlite3.Error as e:
            conn.rollback()
            return False, f"Database error: {e}"
        finally:
            conn.close()

    # ========================================================================
    # CARRYING CAPACITY
    # ========================================================================

    def calculate_carrying_capacity(
        self,
        creature_id: str,
        session_id: str,
        strength_score: int,
        size_category: str = "Medium"
    ) -> CarryingCapacity:
        """
        Calculate carrying capacity based on D&D 5e rules.

        Rules:
        - Base capacity = STR × 15 pounds (for Medium creatures)
        - Small/Tiny: × 0.5
        - Large: × 2
        - Huge: × 4
        - Gargantuan: × 8

        Variant Encumbrance:
        - Over STR × 5: Encumbered (speed -10)
        - Over STR × 10: Heavily Encumbered (speed -20, disadvantage)

        Args:
            creature_id: Creature ID
            session_id: Session ID
            strength_score: STR ability score
            size_category: Creature size

        Returns:
            CarryingCapacity object
        """
        # Calculate base capacity
        base_capacity = strength_score * 15.0

        # Size multipliers
        size_multipliers = {
            'Tiny': 0.5,
            'Small': 0.5,
            'Medium': 1.0,
            'Large': 2.0,
            'Huge': 4.0,
            'Gargantuan': 8.0
        }

        size_mult = size_multipliers.get(size_category, 1.0)
        capacity = base_capacity * size_mult

        # Get current weight
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            # Total weight from equipped items
            cursor.execute("""
                SELECT COALESCE(SUM(i.weight), 0) as equipped_weight
                FROM equipped_items ei
                JOIN creature_inventory ci ON ei.inventory_item_id = ci.id
                JOIN ref_db.items i ON ci.item_id = i.id
                WHERE ei.creature_id = ? AND ei.is_active = 1
            """, (creature_id,))

            equipped_weight = cursor.fetchone()['equipped_weight']

            # Total weight from unequipped inventory
            cursor.execute("""
                SELECT COALESCE(SUM(i.weight * ci.quantity), 0) as inventory_weight
                FROM creature_inventory ci
                JOIN ref_db.items i ON ci.item_id = i.id
                LEFT JOIN equipped_items ei ON ci.id = ei.inventory_item_id AND ei.is_active = 1
                WHERE ci.creature_id = ? AND ei.id IS NULL
            """, (creature_id,))

            inventory_weight = cursor.fetchone()['inventory_weight']

            # Note: Assuming weight is already in pounds (D&D standard)
            # If you need kg, items should store weight in kg and convert here
            total_weight_lbs = equipped_weight + inventory_weight

            # Determine encumbrance level
            encumbrance_level = "Normal"
            speed_penalty = 0
            has_disadvantage = False
            affected_checks = None

            # Variant encumbrance thresholds
            encumbered_threshold = strength_score * 5
            heavily_encumbered_threshold = strength_score * 10

            if total_weight_lbs > capacity:
                encumbrance_level = "Over Capacity"
                speed_penalty = 0  # Can't move at all
                has_disadvantage = True
                affected_checks = ['STR', 'DEX', 'CON']
            elif total_weight_lbs > heavily_encumbered_threshold:
                encumbrance_level = "Heavily Encumbered"
                speed_penalty = 20
                has_disadvantage = True
                affected_checks = ['STR', 'DEX', 'CON']
            elif total_weight_lbs > encumbered_threshold:
                encumbrance_level = "Encumbered"
                speed_penalty = 10
                has_disadvantage = False

            # Update carrying_capacity_state table
            cursor.execute("""
                INSERT OR REPLACE INTO carrying_capacity_state (
                    creature_id, session_id, strength_score, size_category,
                    base_carrying_capacity, current_weight_carried,
                    size_multiplier, encumbrance_level, speed_penalty,
                    has_disadvantage, affected_checks,
                    total_equipped_weight, total_inventory_weight,
                    total_container_contents_weight
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                creature_id, session_id, strength_score, size_category,
                capacity, total_weight_lbs, size_mult,
                encumbrance_level, speed_penalty, has_disadvantage,
                ','.join(affected_checks) if affected_checks else None,
                equipped_weight,
                inventory_weight,
                0  # content weight (for future material system integration)
            ))

            # Log event if encumbered
            if encumbrance_level != "Normal":
                self._log_equipment_event(
                    conn, session_id, creature_id, 'encumbered',
                    None, None, None,
                    {
                        'encumbrance_level': encumbrance_level,
                        'weight': total_weight_lbs,
                        'capacity': capacity
                    },
                    'system'
                )

            conn.commit()

            return CarryingCapacity(
                base_capacity=capacity,
                current_weight=total_weight_lbs,
                encumbrance_level=encumbrance_level,
                speed_penalty=speed_penalty,
                has_disadvantage=has_disadvantage,
                affected_checks=affected_checks
            )

        finally:
            conn.close()

    def get_carrying_capacity_status(self, creature_id: str) -> Optional[Dict]:
        """Get cached carrying capacity status"""
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM carrying_capacity_state WHERE creature_id = ?
            """, (creature_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ========================================================================
    # ARMOR CLASS CALCULATION
    # ========================================================================

    def calculate_armor_class(
        self,
        creature_id: str,
        base_dex_modifier: int
    ) -> int:
        """
        Calculate total armor class.

        D&D 5e rules:
        - Base AC = 10 + DEX mod (no armor)
        - Light armor = armor AC + DEX mod
        - Medium armor = armor AC + DEX mod (max +2)
        - Heavy armor = armor AC (no DEX)
        - Shield = +2 AC

        Args:
            creature_id: Creature ID
            base_dex_modifier: DEX ability modifier

        Returns:
            Total AC
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            # Get equipped armor
            cursor.execute("""
                SELECT i.armor_class, i.armor_type
                FROM equipped_items ei
                JOIN ref_db.items i ON ei.item_id = i.id
                WHERE ei.creature_id = ? AND i.armor_type IN ('light', 'medium', 'heavy')
                  AND ei.is_active = 1
                LIMIT 1
            """, (creature_id,))

            armor = cursor.fetchone()

            # Get shield
            cursor.execute("""
                SELECT i.armor_class
                FROM equipped_items ei
                JOIN ref_db.items i ON ei.item_id = i.id
                WHERE ei.creature_id = ? AND i.armor_type = 'shield'
                  AND ei.is_active = 1
                LIMIT 1
            """, (creature_id,))

            shield = cursor.fetchone()

            # Calculate AC
            if armor:
                armor_ac = armor['armor_class'] or 0
                armor_type = armor['armor_type']

                if armor_type == 'light':
                    ac = armor_ac + base_dex_modifier
                    max_dex = None
                elif armor_type == 'medium':
                    ac = armor_ac + min(base_dex_modifier, 2)
                    max_dex = 2
                else:  # heavy
                    ac = armor_ac
                    max_dex = 0
            else:
                # No armor - base AC
                ac = 10 + base_dex_modifier
                armor_ac = 0
                armor_type = 'none'
                max_dex = None

            # Add shield
            shield_ac = 0
            if shield and shield['armor_class']:
                shield_ac = shield['armor_class']
                ac += shield_ac

            # Cache the result
            ac_breakdown = {
                'base': 10 if not armor else 0,
                'armor': armor_ac,
                'dex': min(base_dex_modifier, max_dex) if max_dex is not None else base_dex_modifier,
                'shield': shield_ac
            }

            cursor.execute("""
                INSERT OR REPLACE INTO armor_class_cache (
                    creature_id, base_ac, armor_ac, armor_type, shield_ac,
                    dex_modifier, max_dex_bonus, total_ac, ac_breakdown
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                creature_id, 10, armor_ac, armor_type, shield_ac,
                base_dex_modifier, max_dex, ac, json.dumps(ac_breakdown)
            ))

            conn.commit()
            return ac

        finally:
            conn.close()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _check_slot_conflicts(
        self,
        conn: sqlite3.Connection,
        creature_id: str,
        slot_id: str
    ) -> Tuple[bool, str]:
        """Check if slot conflicts with currently equipped items"""
        ref_conn = self._get_ref_connection()
        try:
            # Get slot info
            ref_cursor = ref_conn.cursor()
            ref_cursor.execute("""
                SELECT conflicts_with, layer_level, body_part
                FROM equipment_slots WHERE id = ?
            """, (slot_id,))

            slot_info = ref_cursor.fetchone()
            if not slot_info:
                return False, f"Slot {slot_id} does not exist"

            conflicts_json = slot_info['conflicts_with']
            if conflicts_json:
                conflicts = json.loads(conflicts_json)

                # Check if any conflicting slot is occupied
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(conflicts))
                cursor.execute(f"""
                    SELECT slot_id, item_name FROM equipped_items
                    WHERE creature_id = ? AND slot_id IN ({placeholders})
                      AND is_active = 1
                """, [creature_id] + conflicts)

                conflict = cursor.fetchone()
                if conflict:
                    return False, f"Conflicts with {conflict['item_name']} in {conflict['slot_id']}"

            return True, "OK"

        finally:
            ref_conn.close()

    def _recalculate_armor_class(self, conn: sqlite3.Connection, creature_id: str):
        """Recalculate AC (requires DEX from creature stats)"""
        # Get DEX modifier from creature
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dex_mod FROM creatures WHERE id = ?
        """, (creature_id,))
        row = cursor.fetchone()

        if row and row['dex_mod'] is not None:
            self.calculate_armor_class(creature_id, row['dex_mod'])

    def _recalculate_carrying_capacity(
        self,
        conn: sqlite3.Connection,
        creature_id: str,
        session_id: str
    ):
        """Recalculate carrying capacity (requires STR from creature stats)"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT str, size FROM creatures WHERE id = ?
        """, (creature_id,))
        row = cursor.fetchone()

        if row and row['str'] is not None:
            self.calculate_carrying_capacity(
                creature_id, session_id,
                row['str'], row['size'] or 'Medium'
            )

    def _log_equipment_event(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        creature_id: str,
        event_type: str,
        slot_id: Optional[str],
        item_id: Optional[str],
        inventory_item_id: Optional[int],
        event_data: Dict,
        caused_by: str
    ):
        """Log an equipment event"""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO equipment_events (
                session_id, creature_id, event_type, slot_id,
                item_id, inventory_item_id, event_data, caused_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, creature_id, event_type, slot_id,
            item_id, inventory_item_id, json.dumps(event_data), caused_by
        ))
