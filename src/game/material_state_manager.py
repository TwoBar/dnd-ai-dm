"""
Material State Manager

Handles:
- Material collection validation (container compatibility, tool requirements)
- Spillage system (movement-based volume loss)
- Material decay (temperature changes, state transitions, evaporation)
"""

import math
import sqlite3
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class MaterialStateManager:
    """
    Manages material states, container compatibility, and collection.
    """

    def __init__(self, reference_db_path: str, game_state_db_path: str):
        self.reference_db_path = reference_db_path
        self.game_state_db_path = game_state_db_path

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _get_ref_db(self):
        """Get connection to reference database"""
        conn = sqlite3.connect(self.reference_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_game_db(self):
        """Get connection to game state database"""
        conn = sqlite3.connect(self.game_state_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_serving_size_ml(self, content_id: str, creature_size: str) -> float:
        """
        Get serving size for a creature based on size.

        Args:
            content_id: 'content:water'
            creature_size: 'small', 'medium', 'large'

        Returns:
            Volume in ml for one serving
        """
        conn = self._get_ref_db()

        # Get material
        material = conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (content_id,)
        ).fetchone()

        # Get size multiplier
        size_mult = conn.execute(
            "SELECT serving_multiplier FROM size_multipliers WHERE size = ?",
            (creature_size,)
        ).fetchone()

        conn.close()

        if not material or not size_mult:
            return 330.0  # Default

        return material['serving_size_ml'] * size_mult['serving_multiplier']

    def calculate_charges_for_creature(
        self,
        content_volume_ml: float,
        content_id: str,
        creature_size: str
    ) -> float:
        """
        Calculate how many servings/charges a creature can get from this volume.

        Returns:
            Number of servings (can be fractional: 2.53 charges)
        """
        serving_size = self.get_serving_size_ml(content_id, creature_size)
        return content_volume_ml / serving_size

    # ============================================================
    # COLLECTION VALIDATION
    # ============================================================

    def can_collect(
        self,
        material_id: str,
        creature_id: str,
        target_container_inv_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Check if a creature can collect a material.

        Returns:
            (can_collect: bool, reason: str)
        """
        ref_conn = self._get_ref_db()
        game_conn = self._get_game_db()

        # Get material
        material = ref_conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (material_id,)
        ).fetchone()

        if not material:
            ref_conn.close()
            game_conn.close()
            return (False, f"Unknown material: {material_id}")

        # Does it require a container?
        if material['requires_container']:
            if not target_container_inv_id:
                ref_conn.close()
                game_conn.close()
                return (False, f"{material['name']} requires a container to collect")

            # Check container compatibility
            container_inv = game_conn.execute(
                "SELECT * FROM creature_inventory WHERE id = ?",
                (target_container_inv_id,)
            ).fetchone()

            if not container_inv:
                ref_conn.close()
                game_conn.close()
                return (False, "Container not found")

            container = ref_conn.execute(
                "SELECT * FROM items WHERE id = ?",
                (container_inv['item_id'],)
            ).fetchone()

            container_type = ref_conn.execute(
                "SELECT * FROM container_types WHERE id = ?",
                (container['container_type_id'],)
            ).fetchone()

            # State compatibility
            if material['matter_state'] == 'liquid' and not container_type['can_hold_liquid']:
                ref_conn.close()
                game_conn.close()
                return (False, f"Cannot store liquids in {container['name']}")

            if material['matter_state'] == 'powder' and not container_type['can_hold_powder']:
                ref_conn.close()
                game_conn.close()
                return (False, f"Cannot store powders in {container['name']}")

            # Container must be watertight for liquids
            if material['matter_state'] == 'liquid' and not container_type['is_watertight']:
                ref_conn.close()
                game_conn.close()
                return (False, f"{container['name']} is not watertight")

            # Check specific compatibility
            compatible = json.loads(material['compatible_containers'] or '[]')
            if container['container_type_id'] not in compatible:
                ref_conn.close()
                game_conn.close()
                return (False, f"{container['name']} cannot hold {material['name']}")

            # Temperature check
            if material['base_temperature'] > container_type['max_temperature']:
                ref_conn.close()
                game_conn.close()
                return (False, f"{material['name']} is too hot for {container['name']} (will melt/burn)")

            if material['base_temperature'] < container_type['min_temperature']:
                ref_conn.close()
                game_conn.close()
                return (False, f"{material['name']} is too cold for {container['name']} (will crack)")

            # Acid check
            if material['ph_level'] and material['ph_level'] < 3.0 and not container_type['acid_resistant']:
                ref_conn.close()
                game_conn.close()
                return (False, f"{material['name']} will corrode {container['name']}")

        # Check if special tool required
        if material['collection_tool']:
            has_tool = game_conn.execute("""
                SELECT COUNT(*) as count FROM creature_inventory
                WHERE creature_id = ? AND item_id = (
                    SELECT item_id FROM tools WHERE id = ?
                )
            """, (creature_id, material['collection_tool'])).fetchone()

            if has_tool['count'] == 0:
                tool = ref_conn.execute(
                    "SELECT * FROM tools WHERE id = ?",
                    (material['collection_tool'],)
                ).fetchone()

                ref_conn.close()
                game_conn.close()
                return (False, f"Requires {tool['name']} to collect {material['name']}")

        ref_conn.close()
        game_conn.close()
        return (True, "Can collect")

    def collect_material(
        self,
        material_id: str,
        volume_ml: float,
        creature_id: str,
        target_container_inv_id: int,
        source_location: str = 'environment'
    ) -> Dict:
        """
        Collect material from environment into a container.
        """
        # Validation
        can_collect, reason = self.can_collect(material_id, creature_id, target_container_inv_id)
        if not can_collect:
            return {'success': False, 'error': reason}

        ref_conn = self._get_ref_db()
        game_conn = self._get_game_db()

        material = ref_conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (material_id,)
        ).fetchone()

        container_inv = game_conn.execute(
            "SELECT * FROM creature_inventory WHERE id = ?",
            (target_container_inv_id,)
        ).fetchone()

        container = ref_conn.execute(
            "SELECT * FROM items WHERE id = ?",
            (container_inv['item_id'],)
        ).fetchone()

        # Check capacity
        current_volume = container_inv['content_volume_ml'] or 0.0
        available_capacity = container['container_capacity_ml'] - current_volume

        if volume_ml > available_capacity:
            ref_conn.close()
            game_conn.close()
            return {
                'success': False,
                'error': f"Only {available_capacity}ml space remaining in {container['name']}"
            }

        # Add to container
        new_volume = current_volume + volume_ml
        content_weight = new_volume * (material['content_weight_per_ml'] or 0.001)

        # Calculate total weight
        container_weight = container['container_weight_kg'] or 0.0
        total_weight = container_weight + content_weight

        game_conn.execute("""
            UPDATE creature_inventory SET
                is_filled = 1,
                contains_material_id = ?,
                content_volume_ml = ?,
                content_weight_kg = ?,
                current_temperature = ?,
                current_ph = ?,
                current_salinity_ppm = ?,
                current_weight_kg = ?,
                last_state_update = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            material_id,
            new_volume,
            content_weight,
            material['base_temperature'],
            material['ph_level'],
            material['salinity_ppm'],
            total_weight,
            target_container_inv_id
        ))

        game_conn.commit()
        ref_conn.close()
        game_conn.close()

        return {
            'success': True,
            'volume_collected_ml': volume_ml,
            'total_volume_ml': new_volume,
            'message': f"Collected {volume_ml}ml of {material['name']}"
        }


class SpillageSystem:
    """Handles movement-based spillage for containers"""

    def __init__(self, reference_db_path: str, game_state_db_path: str):
        self.reference_db_path = reference_db_path
        self.game_state_db_path = game_state_db_path

    def _get_ref_db(self):
        conn = sqlite3.connect(self.reference_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_game_db(self):
        conn = sqlite3.connect(self.game_state_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_spillage(
        self,
        inventory_item_id: int,
        movement_type: str,
        hours_duration: float
    ) -> Dict:
        """
        Calculate how much liquid/powder spills during movement.
        """
        ref_conn = self._get_ref_db()
        game_conn = self._get_game_db()

        inv_item = game_conn.execute(
            "SELECT * FROM creature_inventory WHERE id = ?",
            (inventory_item_id,)
        ).fetchone()

        # Not filled? No spillage
        if not inv_item or not inv_item['is_filled']:
            ref_conn.close()
            game_conn.close()
            return {'spillage_occurred': False, 'volume_spilled_ml': 0}

        # Get material
        material = ref_conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (inv_item['contains_material_id'],)
        ).fetchone()

        # Solids don't spill
        if material['matter_state'] == 'solid':
            ref_conn.close()
            game_conn.close()
            return {'spillage_occurred': False, 'volume_spilled_ml': 0}

        # Only liquids and powders spill
        if material['matter_state'] not in ['liquid', 'powder']:
            ref_conn.close()
            game_conn.close()
            return {'spillage_occurred': False, 'volume_spilled_ml': 0}

        # Get container info
        item = ref_conn.execute(
            "SELECT * FROM items WHERE id = ?",
            (inv_item['item_id'],)
        ).fetchone()

        container_type = ref_conn.execute(
            "SELECT * FROM container_types WHERE id = ?",
            (item['container_type_id'],)
        ).fetchone()

        # Get movement intensity
        movement = ref_conn.execute(
            "SELECT * FROM movement_intensities WHERE movement_type = ?",
            (movement_type,)
        ).fetchone()

        # Closed containers have better protection
        closure_modifier = 1.0
        if container_type['can_be_closed'] and inv_item['is_closed']:
            closure_modifier = 0.2  # 80% reduction when closed

        # Calculate spillage rate
        base_spillage_per_hour = container_type['spillage_rate_multiplier']
        movement_multiplier = movement['spillage_multiplier']

        spillage_rate_per_hour = (
            base_spillage_per_hour *
            movement_multiplier *
            closure_modifier
        )

        # Calculate actual spillage
        current_volume = inv_item['content_volume_ml']
        spillage_percentage = min(1.0, spillage_rate_per_hour * hours_duration / 100)
        volume_spilled = current_volume * spillage_percentage

        ref_conn.close()
        game_conn.close()

        return {
            'spillage_occurred': volume_spilled > 0,
            'volume_spilled_ml': volume_spilled,
            'percentage_lost': spillage_percentage * 100,
            'spillage_rate': spillage_rate_per_hour,
        }

    def apply_spillage_to_inventory(
        self,
        inventory_item_id: int,
        movement_type: str,
        hours_duration: float
    ) -> Dict:
        """
        Apply spillage and update inventory.
        """
        spillage = self.calculate_spillage(
            inventory_item_id,
            movement_type,
            hours_duration
        )

        if not spillage['spillage_occurred']:
            return spillage

        ref_conn = self._get_ref_db()
        game_conn = self._get_game_db()

        inv_item = game_conn.execute(
            "SELECT * FROM creature_inventory WHERE id = ?",
            (inventory_item_id,)
        ).fetchone()

        item = ref_conn.execute(
            "SELECT * FROM items WHERE id = ?",
            (inv_item['item_id'],)
        ).fetchone()

        material = ref_conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (inv_item['contains_material_id'],)
        ).fetchone()

        # Reduce volume
        new_volume = inv_item['content_volume_ml'] - spillage['volume_spilled_ml']

        if new_volume <= 0:
            # Completely spilled!
            game_conn.execute("""
                UPDATE creature_inventory SET
                    is_filled = 0,
                    contains_material_id = NULL,
                    content_volume_ml = 0,
                    content_weight_kg = 0,
                    current_weight_kg = ?
                WHERE id = ?
            """, (item['container_weight_kg'], inventory_item_id))

            spillage['message'] = f"All the {material['name']} spilled from your {item['name']}!"
            spillage['total_loss'] = True
        else:
            # Partial spillage
            new_content_weight = new_volume * (material['content_weight_per_ml'] or 0.001)
            new_total_weight = (item['container_weight_kg'] or 0.0) + new_content_weight

            game_conn.execute("""
                UPDATE creature_inventory SET
                    content_volume_ml = ?,
                    content_weight_kg = ?,
                    current_weight_kg = ?
                WHERE id = ?
            """, (new_volume, new_content_weight, new_total_weight, inventory_item_id))

            spillage['message'] = f"{spillage['volume_spilled_ml']:.0f}ml of {material['name']} spilled from your {item['name']}"
            spillage['volume_remaining_ml'] = new_volume
            spillage['total_loss'] = False

        game_conn.commit()
        ref_conn.close()
        game_conn.close()

        return spillage


class MaterialDecaySystem:
    """Handles time-based changes to materials"""

    def __init__(self, reference_db_path: str, game_state_db_path: str):
        self.reference_db_path = reference_db_path
        self.game_state_db_path = game_state_db_path

    def _get_ref_db(self):
        conn = sqlite3.connect(self.reference_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_game_db(self):
        conn = sqlite3.connect(self.game_state_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def update_material_state(self, inventory_item_id: int, hours_passed: float) -> Dict:
        """
        Update a single container's material state.
        Handles: temperature change, melting, cooling, evaporation
        """
        ref_conn = self._get_ref_db()
        game_conn = self._get_game_db()

        inv_item = game_conn.execute(
            "SELECT * FROM creature_inventory WHERE id = ?",
            (inventory_item_id,)
        ).fetchone()

        if not inv_item or not inv_item['is_filled']:
            ref_conn.close()
            game_conn.close()
            return {'changed': False}

        material = ref_conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (inv_item['contains_material_id'],)
        ).fetchone()

        if not material['decays_over_time']:
            ref_conn.close()
            game_conn.close()
            return {'changed': False}

        # Temperature change
        if material['decay_rate_per_hour']:
            temp_change = material['decay_rate_per_hour'] * hours_passed
            new_temp = inv_item['current_temperature'] + temp_change

            # Check for state change
            state_changed = False
            new_material_id = None

            # Melting/boiling (cold → hot)
            if new_temp > material['max_stable_temp']:
                if material['state_change_to_hot']:
                    new_material_id = material['state_change_to_hot']
                    state_changed = True

            # Freezing/condensing (hot → cold)
            elif new_temp < material['min_stable_temp']:
                if material['state_change_to_cold']:
                    new_material_id = material['state_change_to_cold']
                    state_changed = True

            if state_changed:
                result = self._transform_material(inventory_item_id, new_material_id, new_temp)
                ref_conn.close()
                game_conn.close()
                return result

            # Update temperature
            game_conn.execute("""
                UPDATE creature_inventory SET current_temperature = ?
                WHERE id = ?
            """, (new_temp, inventory_item_id))

        # Evaporation (for hot liquids)
        if inv_item['current_temperature'] and inv_item['current_temperature'] > 80.0:
            evap_rate = material['evaporation_rate_per_hour'] or 0.01
            volume_loss = inv_item['content_volume_ml'] * evap_rate * hours_passed
            new_volume = max(0, inv_item['content_volume_ml'] - volume_loss)

            if new_volume <= 0:
                # Completely evaporated!
                game_conn.execute("""
                    UPDATE creature_inventory SET
                        is_filled = 0,
                        contains_material_id = NULL,
                        content_volume_ml = 0,
                        content_weight_kg = 0
                    WHERE id = ?
                """, (inventory_item_id,))

                game_conn.commit()
                ref_conn.close()
                game_conn.close()
                return {'changed': True, 'evaporated': True, 'message': 'Liquid evaporated completely'}
            else:
                game_conn.execute("""
                    UPDATE creature_inventory SET content_volume_ml = ?
                    WHERE id = ?
                """, (new_volume, inventory_item_id))

        game_conn.commit()
        ref_conn.close()
        game_conn.close()
        return {'changed': True}

    def _transform_material(
        self,
        inventory_item_id: int,
        new_material_id: str,
        new_temperature: float
    ) -> Dict:
        """Transform material (ice → water, water → steam, etc.)"""
        ref_conn = self._get_ref_db()
        game_conn = self._get_game_db()

        new_material = ref_conn.execute(
            "SELECT * FROM material_properties WHERE id = ?",
            (new_material_id,)
        ).fetchone()

        inv_item = game_conn.execute(
            "SELECT * FROM creature_inventory WHERE id = ?",
            (inventory_item_id,)
        ).fetchone()

        # Handle state changes
        if new_material['matter_state'] == 'gas':
            # Turned to gas - escapes!
            game_conn.execute("""
                UPDATE creature_inventory SET
                    is_filled = 0,
                    contains_material_id = NULL,
                    content_volume_ml = 0,
                    content_weight_kg = 0
                WHERE id = ?
            """, (inventory_item_id,))

            message = f"Material evaporated into {new_material['name']}!"

        elif new_material['matter_state'] == 'solid':
            # Liquid froze - volume might expand
            new_volume = inv_item['content_volume_ml'] * 1.09  # Water expands 9% when frozen

            game_conn.execute("""
                UPDATE creature_inventory SET
                    contains_material_id = ?,
                    content_volume_ml = ?,
                    current_temperature = ?
                WHERE id = ?
            """, (new_material_id, new_volume, new_temperature, inventory_item_id))

            message = f"Material froze into {new_material['name']}"

        else:
            # Solid → liquid
            game_conn.execute("""
                UPDATE creature_inventory SET
                    contains_material_id = ?,
                    current_temperature = ?
                WHERE id = ?
            """, (new_material_id, new_temperature, inventory_item_id))

            message = f"Material melted into {new_material['name']}"

        game_conn.commit()
        ref_conn.close()
        game_conn.close()

        return {
            'changed': True,
            'transformed': True,
            'new_material_id': new_material_id,
            'message': message
        }
