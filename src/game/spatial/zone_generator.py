"""
ZoneGenerator - Lazy procedural location generation

This module handles on-demand generation of spatial locations and their contents.
Generation is triggered by player actions or narrative needs, not pre-populated.

Key principles:
- Locations generated lazily when needed
- Two-phase item generation (LLM size categories → code volumes)
- Container-based item generation (no abstract "search for item")
- Minimal context hierarchy (container + room + building type)
"""

import sqlite3
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .spatial_agent import SpatialAgent, BoundingBox, EntityPlacement


class GenerationPriority(Enum):
    """Priority levels for generation queue"""
    IMMEDIATE = 10  # Player is entering this location
    HIGH = 8        # Adjacent to player or mentioned in narrative
    MEDIUM = 5      # Connected location
    LOW = 3         # Background/distant location
    DEFERRED = 1    # Far away, generate only if needed


@dataclass
class GenerationContext:
    """Context for location generation"""
    location_name: str
    location_type: str
    parent_location_id: Optional[str]
    scale_band: str

    # Semantic context for LLM
    narrative_context: Optional[str] = None
    purpose: Optional[str] = None  # "combat", "exploration", "social"

    # Physical constraints
    suggested_bbox: Optional[BoundingBox] = None

    # Parent context
    parent_name: Optional[str] = None
    parent_type: Optional[str] = None


class ZoneGenerator:
    """
    Handles lazy procedural generation of locations and contents.

    Works with SpatialAgent to create the persistent spatial model.
    """

    def __init__(
        self,
        spatial_agent: SpatialAgent,
        reference_db_path: str,
        game_state_db_path: str
    ):
        """
        Initialize ZoneGenerator.

        Args:
            spatial_agent: SpatialAgent instance for spatial operations
            reference_db_path: Path to reference database
            game_state_db_path: Path to game state database
        """
        self.spatial_agent = spatial_agent
        self.ref_db_path = reference_db_path
        self.game_db_path = game_state_db_path

    def _get_ref_connection(self) -> sqlite3.Connection:
        """Get connection to reference database"""
        conn = sqlite3.connect(self.ref_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_game_connection(self) -> sqlite3.Connection:
        """Get connection to game state database"""
        conn = sqlite3.connect(self.game_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ========================================================================
    # GENERATION QUEUE MANAGEMENT
    # ========================================================================

    def queue_location_generation(
        self,
        session_id: str,
        context: GenerationContext,
        priority: GenerationPriority = GenerationPriority.MEDIUM,
        reason: str = "player_proximity"
    ) -> str:
        """
        Add a location to the generation queue.

        Args:
            session_id: Session ID
            context: Generation context with semantic information
            priority: Generation priority
            reason: Why generation was triggered

        Returns:
            Location ID that will be generated
        """
        # Create location ID
        location_id = self._generate_location_id(context)

        # Create placeholder location
        bbox = context.suggested_bbox or self._estimate_bbox_for_type(
            context.location_type,
            context.scale_band
        )

        self.spatial_agent.create_location(
            session_id=session_id,
            location_id=location_id,
            name=context.location_name,
            location_type=context.location_type,
            bbox=bbox,
            scale_band=context.scale_band,
            parent_location_id=context.parent_location_id,
            description=f"Placeholder for {context.location_name}",
            generation_context={
                'narrative_context': context.narrative_context,
                'purpose': context.purpose,
                'parent_name': context.parent_name,
                'parent_type': context.parent_type
            }
        )

        # Add to generation queue
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO generation_queue (
                    session_id, location_id, priority, reason, context
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                location_id,
                priority.value,
                reason,
                json.dumps({
                    'location_name': context.location_name,
                    'location_type': context.location_type,
                    'parent_location_id': context.parent_location_id,
                    'scale_band': context.scale_band,
                    'narrative_context': context.narrative_context,
                    'purpose': context.purpose
                })
            ))
            conn.commit()
        finally:
            conn.close()

        return location_id

    def get_next_generation_task(self, session_id: str) -> Optional[Dict]:
        """
        Get the highest priority pending generation task.

        Args:
            session_id: Session ID

        Returns:
            Generation task dict or None if queue is empty
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM generation_queue
                WHERE session_id = ? AND status = 'pending'
                ORDER BY priority DESC, queued_at ASC
                LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def mark_generation_started(self, queue_id: int) -> bool:
        """Mark a generation task as started"""
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE generation_queue
                SET status = 'generating', started_at = datetime('now')
                WHERE id = ?
            """, (queue_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_generation_completed(
        self,
        queue_id: int,
        success: bool = True
    ) -> bool:
        """Mark a generation task as completed or failed"""
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE generation_queue
                SET status = ?, completed_at = datetime('now')
                WHERE id = ?
            """, ('completed' if success else 'failed', queue_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ========================================================================
    # PROCEDURAL GENERATION
    # ========================================================================

    def generate_room_contents(
        self,
        session_id: str,
        location_id: str,
        room_type: str,
        building_type: str
    ) -> Dict[str, Any]:
        """
        Generate contents for a room.

        This is a PLACEHOLDER for LLM integration.
        In full implementation, this would:
        1. Query LLM for furniture and items by size category
        2. Programmatically assign volumes/dimensions
        3. Use PlacementAdvisor to position everything

        Args:
            session_id: Session ID
            location_id: Location to populate
            room_type: Type of room (e.g., "bedroom", "kitchen")
            building_type: Type of building (e.g., "tavern", "temple")

        Returns:
            Generation results with entity counts and errors
        """
        location = self.spatial_agent.get_location(location_id)
        if not location:
            return {'success': False, 'error': 'Location not found'}

        # TODO: LLM Phase 1 - Generate semantic entities by size
        # For now, use simple procedural generation
        furniture_list = self._get_typical_furniture_for_room(room_type, building_type)

        generated_entities = []
        errors = []

        # Place furniture
        for i, furniture_spec in enumerate(furniture_list):
            # Calculate position (simple grid placement for now)
            bbox = BoundingBox(
                location['x_min'], location['y_min'], location['z_min'],
                location['x_max'], location['y_max'], location['z_max']
            )

            # Simple positioning: distribute along walls
            position = self._calculate_furniture_position(
                i, len(furniture_list), bbox
            )

            entity_id = f"furniture:{location_id}:{furniture_spec['name']}:{i}"

            placement = EntityPlacement(
                entity_id=entity_id,
                entity_name=furniture_spec['name'],
                x=position[0],
                y=position[1],
                z=position[2],
                volume_m3=furniture_spec['volume_m3'],
                footprint_width=furniture_spec.get('width'),
                footprint_depth=furniture_spec.get('depth'),
                height=furniture_spec.get('height'),
                is_blocking=furniture_spec.get('blocking', True)
            )

            success = self.spatial_agent.place_entity(
                session_id=session_id,
                entity_id=entity_id,
                location_id=location_id,
                placement=placement,
                furniture_id=entity_id,
                sprite_id=furniture_spec.get('sprite_id'),
                description=furniture_spec.get('description'),
                caused_by='zone_generation'
            )

            if success:
                generated_entities.append({
                    'entity_id': entity_id,
                    'name': furniture_spec['name'],
                    'type': 'furniture'
                })
            else:
                errors.append(f"Failed to place {furniture_spec['name']}")

        return {
            'success': len(errors) == 0,
            'generated_count': len(generated_entities),
            'entities': generated_entities,
            'errors': errors
        }

    def generate_container_contents(
        self,
        session_id: str,
        container_entity_id: str,
        room_type: str,
        building_type: str
    ) -> Dict[str, Any]:
        """
        Generate items inside a container when inspected.

        This implements the "no abstract search" principle:
        - Players can't search for specific items
        - Items generated when container is opened/inspected
        - Two-phase: LLM generates by size → code assigns volumes

        Args:
            session_id: Session ID
            container_entity_id: Spatial entity that is a container
            room_type: Type of room containing container
            building_type: Type of building

        Returns:
            Generation results with created items
        """
        # Get container entity
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM spatial_entities WHERE id = ?
            """, (container_entity_id,))
            container = cursor.fetchone()

            if not container:
                return {'success': False, 'error': 'Container not found'}

            # Extract container name for plausibility lookup
            container_name = container['entity_name'].lower()

        finally:
            conn.close()

        # Get plausibility rules
        plausibility = self._get_container_plausibility(
            container_name, room_type, building_type
        )

        if not plausibility:
            # Default to generic container
            plausibility = {
                'typical_small_count': 3,
                'typical_medium_count': 1,
                'typical_large_count': 0
            }

        # TODO: LLM Phase 1 - Generate item names by size category
        # For now, use simple procedural generation
        items = self._generate_typical_items(
            container_name,
            room_type,
            building_type,
            plausibility
        )

        generated_items = []

        # TODO: Phase 2 - Programmatically assign volumes and add to inventory
        # This would create creature_inventory entries with the container as holder

        for item_spec in items:
            generated_items.append({
                'name': item_spec['name'],
                'size_category': item_spec['size_category'],
                'estimated_volume_m3': item_spec['volume_m3']
            })

        return {
            'success': True,
            'container': container_name,
            'item_count': len(generated_items),
            'items': generated_items,
            'note': 'Full inventory integration pending'
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _generate_location_id(self, context: GenerationContext) -> str:
        """Generate unique location ID from context"""
        # Clean name for ID
        name_slug = context.location_name.lower().replace(' ', '_')
        return f"loc:{context.location_type}:{name_slug}"

    def _estimate_bbox_for_type(
        self,
        location_type: str,
        scale_band: str
    ) -> BoundingBox:
        """
        Estimate reasonable bounding box for a location type.

        In full implementation, this would use LLM or more sophisticated
        procedural generation. For now, use simple defaults.
        """
        # Get tile size for scale
        tile_size = self.spatial_agent._get_tile_size_for_scale(scale_band)

        # Default sizes in tiles
        size_map = {
            'region': (100, 100, 10),
            'city': (50, 50, 5),
            'district': (30, 30, 3),
            'building': (20, 20, 3),
            'room': (10, 10, 1),
            'furniture': (2, 2, 1)
        }

        tiles = size_map.get(location_type, (10, 10, 1))

        return BoundingBox(
            x_min=0,
            y_min=0,
            z_min=0,
            x_max=tiles[0] * tile_size,
            y_max=tiles[1] * tile_size,
            z_max=tiles[2] * 3.0  # 3m per floor
        )

    def _get_typical_furniture_for_room(
        self,
        room_type: str,
        building_type: str
    ) -> List[Dict]:
        """
        Get typical furniture for a room type.

        PLACEHOLDER - In full implementation, LLM would generate this.
        """
        furniture_templates = {
            'common_room': [
                {
                    'name': 'Table',
                    'volume_m3': 0.5,
                    'width': 2.0,
                    'depth': 1.0,
                    'height': 0.75,
                    'blocking': True,
                    'sprite_id': 'table',
                    'description': 'Sturdy wooden table'
                },
                {
                    'name': 'Chair',
                    'volume_m3': 0.2,
                    'width': 0.5,
                    'depth': 0.5,
                    'height': 1.0,
                    'blocking': True,
                    'sprite_id': 'chair',
                    'description': 'Simple wooden chair'
                },
                {
                    'name': 'Barrel',
                    'volume_m3': 0.3,
                    'width': 0.6,
                    'depth': 0.6,
                    'height': 0.9,
                    'blocking': True,
                    'sprite_id': 'barrel',
                    'description': 'Wooden storage barrel'
                }
            ],
            'bedroom': [
                {
                    'name': 'Bed',
                    'volume_m3': 1.5,
                    'width': 2.0,
                    'depth': 1.5,
                    'height': 0.5,
                    'blocking': True,
                    'sprite_id': 'bed',
                    'description': 'Simple bed with straw mattress'
                },
                {
                    'name': 'Chest',
                    'volume_m3': 0.4,
                    'width': 1.0,
                    'depth': 0.5,
                    'height': 0.5,
                    'blocking': True,
                    'sprite_id': 'chest',
                    'description': 'Wooden storage chest'
                }
            ]
        }

        return furniture_templates.get(room_type, [])

    def _calculate_furniture_position(
        self,
        index: int,
        total: int,
        bbox: BoundingBox
    ) -> Tuple[float, float, float]:
        """
        Calculate position for furniture.

        PLACEHOLDER - Simple grid positioning.
        In full implementation, use PlacementAdvisor.
        """
        # Distribute along perimeter
        perimeter = 2 * (bbox.width + bbox.height)
        spacing = perimeter / max(total, 1)
        distance = index * spacing

        # Place along walls
        if distance < bbox.width:
            # South wall
            x = bbox.x_min + distance
            y = bbox.y_min + 0.5
        elif distance < bbox.width + bbox.height:
            # East wall
            x = bbox.x_max - 0.5
            y = bbox.y_min + (distance - bbox.width)
        elif distance < 2 * bbox.width + bbox.height:
            # North wall
            x = bbox.x_max - (distance - bbox.width - bbox.height)
            y = bbox.y_max - 0.5
        else:
            # West wall
            x = bbox.x_min + 0.5
            y = bbox.y_max - (distance - 2 * bbox.width - bbox.height)

        return (x, y, bbox.z_min)

    def _get_container_plausibility(
        self,
        container_name: str,
        room_type: str,
        building_type: str
    ) -> Optional[Dict]:
        """Get plausibility rules for container"""
        conn = self._get_ref_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM container_plausibility_rules
                WHERE container_name = ?
                  AND (room_type = ? OR room_type = 'any')
                  AND (building_type = ? OR building_type = 'any')
                ORDER BY
                  CASE WHEN room_type = ? THEN 1 ELSE 2 END,
                  CASE WHEN building_type = ? THEN 1 ELSE 2 END
                LIMIT 1
            """, (container_name, room_type, building_type, room_type, building_type))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _generate_typical_items(
        self,
        container_name: str,
        room_type: str,
        building_type: str,
        plausibility: Dict
    ) -> List[Dict]:
        """
        Generate typical items for a container.

        PLACEHOLDER - In full implementation, LLM would generate this.
        """
        import random

        items = []

        # Small items
        small_items = ['coin', 'key', 'gem', 'button', 'nail']
        for _ in range(plausibility['typical_small_count']):
            items.append({
                'name': random.choice(small_items),
                'size_category': 'small',
                'volume_m3': random.uniform(0.00001, 0.001)
            })

        # Medium items
        medium_items = ['book', 'dagger', 'potion', 'candle', 'rope']
        for _ in range(plausibility['typical_medium_count']):
            items.append({
                'name': random.choice(medium_items),
                'size_category': 'medium',
                'volume_m3': random.uniform(0.001, 0.01)
            })

        # Large items
        large_items = ['sword', 'shield', 'armor', 'blanket', 'sack']
        for _ in range(plausibility['typical_large_count']):
            items.append({
                'name': random.choice(large_items),
                'size_category': 'large',
                'volume_m3': random.uniform(0.01, 0.1)
            })

        return items
