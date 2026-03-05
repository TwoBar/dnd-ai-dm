"""
SpatialAgent - Authoritative spatial state management

This module provides the core spatial system that manages:
- Spatial locations (hierarchical semantic zones)
- Entity placement with absolute coordinates
- Event-driven mutation logging
- Multi-scale representation with volume-based filtering

The SpatialAgent is the single source of truth for spatial state.
All spatial changes must go through event logging.
"""

import sqlite3
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class BoundingBox:
    """Represents a spatial bounding box"""
    x_min: float
    y_min: float
    z_min: float
    x_max: float
    y_max: float
    z_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def depth(self) -> float:
        return self.z_max - self.z_min

    @property
    def center(self) -> Tuple[float, float, float]:
        return (
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2,
            (self.z_min + self.z_max) / 2
        )

    def contains_point(self, x: float, y: float, z: float = 0) -> bool:
        """Check if a point is within this bounding box"""
        return (
            self.x_min <= x <= self.x_max and
            self.y_min <= y <= self.y_max and
            self.z_min <= z <= self.z_max
        )


@dataclass
class EntityPlacement:
    """Represents a placed entity in space"""
    entity_id: str
    entity_name: str
    x: float
    y: float
    z: float
    volume_m3: float
    footprint_width: Optional[float] = None
    footprint_depth: Optional[float] = None
    height: Optional[float] = None
    orientation_degrees: float = 0
    is_blocking: bool = True


class SpatialAgent:
    """
    Authoritative spatial state manager.

    Manages the persistent spatial model with absolute coordinates.
    All spatial changes are logged as events.
    """

    def __init__(self, reference_db_path: str, game_state_db_path: str):
        """
        Initialize SpatialAgent with database connections.

        Args:
            reference_db_path: Path to reference database (scale config, sprites)
            game_state_db_path: Path to game state database (locations, entities, events)
        """
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
    # LOCATION MANAGEMENT
    # ========================================================================

    def create_location(
        self,
        session_id: str,
        location_id: str,
        name: str,
        location_type: str,
        bbox: BoundingBox,
        scale_band: str,
        parent_location_id: Optional[str] = None,
        description: Optional[str] = None,
        generation_context: Optional[Dict] = None
    ) -> bool:
        """
        Create a new spatial location.

        Args:
            session_id: Session ID
            location_id: Unique identifier for this location
            name: Human-readable name
            location_type: Type from location_types table
            bbox: Bounding box defining the space
            scale_band: Scale band (XXL, XL, L, M, S)
            parent_location_id: Parent location ID (if hierarchical)
            description: Optional description
            generation_context: Context used for generation (for LLM)

        Returns:
            True if created successfully
        """
        # Get tile size for scale band
        tile_size = self._get_tile_size_for_scale(scale_band)
        if tile_size is None:
            return False

        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO spatial_locations (
                    id, session_id, name, parent_location_id, location_type,
                    x_min, y_min, z_min, x_max, y_max, z_max,
                    scale_band, tile_size_meters, is_generated,
                    generated_at, generation_context, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                location_id, session_id, name, parent_location_id, location_type,
                bbox.x_min, bbox.y_min, bbox.z_min,
                bbox.x_max, bbox.y_max, bbox.z_max,
                scale_band, tile_size, True, datetime.now().isoformat(),
                json.dumps(generation_context) if generation_context else None,
                description
            ))

            # Log event
            self._log_spatial_event(
                conn=conn,
                session_id=session_id,
                event_type='location_created',
                location_id=location_id,
                event_data={
                    'name': name,
                    'location_type': location_type,
                    'scale_band': scale_band,
                    'bbox': {
                        'x_min': bbox.x_min, 'y_min': bbox.y_min, 'z_min': bbox.z_min,
                        'x_max': bbox.x_max, 'y_max': bbox.y_max, 'z_max': bbox.z_max
                    }
                },
                caused_by='zone_generation'
            )

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"Error creating location: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_location(self, location_id: str) -> Optional[Dict]:
        """Get location details by ID"""
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM spatial_locations WHERE id = ?
            """, (location_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_child_locations(self, parent_location_id: str) -> List[Dict]:
        """Get all child locations of a parent"""
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM spatial_locations
                WHERE parent_location_id = ?
                ORDER BY name
            """, (parent_location_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # ========================================================================
    # ENTITY PLACEMENT
    # ========================================================================

    def place_entity(
        self,
        session_id: str,
        entity_id: str,
        location_id: str,
        placement: EntityPlacement,
        creature_id: Optional[str] = None,
        item_id: Optional[str] = None,
        inventory_item_id: Optional[int] = None,
        furniture_id: Optional[str] = None,
        sprite_id: Optional[str] = None,
        description: Optional[str] = None,
        caused_by: str = 'placement'
    ) -> bool:
        """
        Place an entity at absolute coordinates within a location.

        Args:
            session_id: Session ID
            entity_id: Unique identifier for this spatial entity
            location_id: Location containing this entity
            placement: EntityPlacement with position and physical properties
            creature_id: ID if this is a creature
            item_id: ID if this is an item
            inventory_item_id: ID if this is a placed inventory item
            furniture_id: ID if this is furniture
            sprite_id: Sprite to render
            description: Entity description
            caused_by: What caused this placement

        Returns:
            True if placed successfully
        """
        # Validate location exists
        location = self.get_location(location_id)
        if not location:
            print(f"Error: Location {location_id} does not exist")
            return False

        # Validate position is within location bounds
        if not self._is_position_in_location(
            location, placement.x, placement.y, placement.z
        ):
            print(f"Error: Position ({placement.x}, {placement.y}, {placement.z}) outside location bounds")
            return False

        # Calculate footprint tiles if multi-tile
        footprint_tiles = None
        if placement.footprint_width and placement.footprint_depth:
            footprint_tiles = self._calculate_footprint_tiles(
                placement.footprint_width,
                placement.footprint_depth,
                location['tile_size_meters']
            )

        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO spatial_entities (
                    id, session_id, creature_id, item_id, inventory_item_id, furniture_id,
                    location_id, x, y, z, volume_m3,
                    footprint_width, footprint_depth, height, orientation_degrees,
                    footprint_tiles, is_blocking, is_visible, is_interactive,
                    entity_name, entity_description, sprite_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity_id, session_id, creature_id, item_id, inventory_item_id, furniture_id,
                location_id, placement.x, placement.y, placement.z, placement.volume_m3,
                placement.footprint_width, placement.footprint_depth, placement.height,
                placement.orientation_degrees,
                json.dumps(footprint_tiles) if footprint_tiles else None,
                placement.is_blocking, True, True,
                placement.entity_name, description, sprite_id
            ))

            # Log event
            self._log_spatial_event(
                conn=conn,
                session_id=session_id,
                event_type='entity_placed',
                location_id=location_id,
                entity_id=entity_id,
                creature_id=creature_id,
                event_data={
                    'entity_name': placement.entity_name,
                    'position': {'x': placement.x, 'y': placement.y, 'z': placement.z},
                    'volume_m3': placement.volume_m3
                },
                caused_by=caused_by
            )

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"Error placing entity: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def move_entity(
        self,
        entity_id: str,
        new_x: float,
        new_y: float,
        new_z: Optional[float] = None,
        new_orientation: Optional[float] = None,
        caused_by: str = 'movement',
        triggering_action: Optional[str] = None
    ) -> bool:
        """
        Move an entity to a new position.

        Args:
            entity_id: Entity to move
            new_x: New X coordinate
            new_y: New Y coordinate
            new_z: New Z coordinate (optional, keeps existing if None)
            new_orientation: New orientation in degrees (optional)
            caused_by: What caused this movement
            triggering_action: Specific action that triggered movement

        Returns:
            True if moved successfully
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            # Get current state
            cursor.execute("SELECT * FROM spatial_entities WHERE id = ?", (entity_id,))
            entity = cursor.fetchone()
            if not entity:
                print(f"Error: Entity {entity_id} not found")
                return False

            # Validate new position is within location
            location = self.get_location(entity['location_id'])
            if not self._is_position_in_location(location, new_x, new_y, new_z or entity['z']):
                print(f"Error: New position outside location bounds")
                return False

            # Update position
            update_parts = ["x = ?", "y = ?", "updated_at = ?"]
            params = [new_x, new_y, datetime.now().isoformat()]

            if new_z is not None:
                update_parts.append("z = ?")
                params.append(new_z)

            if new_orientation is not None:
                update_parts.append("orientation_degrees = ?")
                params.append(new_orientation)

            params.append(entity_id)

            cursor.execute(f"""
                UPDATE spatial_entities
                SET {', '.join(update_parts)}
                WHERE id = ?
            """, params)

            # Log event
            self._log_spatial_event(
                conn=conn,
                session_id=entity['session_id'],
                event_type='entity_moved',
                location_id=entity['location_id'],
                entity_id=entity_id,
                creature_id=entity['creature_id'],
                event_data={
                    'old_position': {'x': entity['x'], 'y': entity['y'], 'z': entity['z']},
                    'new_position': {'x': new_x, 'y': new_y, 'z': new_z or entity['z']},
                    'old_orientation': entity['orientation_degrees'],
                    'new_orientation': new_orientation
                },
                caused_by=caused_by,
                triggering_action=triggering_action
            )

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"Error moving entity: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def remove_entity(
        self,
        entity_id: str,
        caused_by: str = 'removal',
        reason: Optional[str] = None
    ) -> bool:
        """
        Remove an entity from spatial system.

        Args:
            entity_id: Entity to remove
            caused_by: What caused this removal
            reason: Why entity was removed

        Returns:
            True if removed successfully
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            # Get entity before deletion
            cursor.execute("SELECT * FROM spatial_entities WHERE id = ?", (entity_id,))
            entity = cursor.fetchone()
            if not entity:
                return False

            # Delete entity
            cursor.execute("DELETE FROM spatial_entities WHERE id = ?", (entity_id,))

            # Log event
            self._log_spatial_event(
                conn=conn,
                session_id=entity['session_id'],
                event_type='entity_removed',
                location_id=entity['location_id'],
                entity_id=entity_id,
                creature_id=entity['creature_id'],
                event_data={
                    'entity_name': entity['entity_name'],
                    'position': {'x': entity['x'], 'y': entity['y'], 'z': entity['z']},
                    'reason': reason
                },
                caused_by=caused_by
            )

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"Error removing entity: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ========================================================================
    # SPATIAL QUERIES
    # ========================================================================

    def get_entities_in_location(
        self,
        location_id: str,
        scale_filter: bool = True
    ) -> List[Dict]:
        """
        Get all entities in a location.

        Args:
            location_id: Location to query
            scale_filter: If True, filter by volume threshold for the scale band

        Returns:
            List of entity dictionaries
        """
        location = self.get_location(location_id)
        if not location:
            return []

        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            if scale_filter:
                # Get volume threshold for this scale
                min_volume = self._get_min_volume_for_scale(location['scale_band'])
                cursor.execute("""
                    SELECT * FROM spatial_entities
                    WHERE location_id = ? AND volume_m3 >= ?
                    ORDER BY z, y, x
                """, (location_id, min_volume))
            else:
                cursor.execute("""
                    SELECT * FROM spatial_entities
                    WHERE location_id = ?
                    ORDER BY z, y, x
                """, (location_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_entities_near(
        self,
        location_id: str,
        x: float,
        y: float,
        radius: float,
        z: Optional[float] = None
    ) -> List[Dict]:
        """
        Get entities within radius of a point.

        Args:
            location_id: Location to search in
            x, y: Center point
            radius: Search radius in meters
            z: Optional Z coordinate (if None, ignores Z)

        Returns:
            List of entities sorted by distance
        """
        entities = self.get_entities_in_location(location_id, scale_filter=False)

        # Filter by distance
        nearby = []
        for entity in entities:
            dx = entity['x'] - x
            dy = entity['y'] - y
            dz = (entity['z'] - z) if z is not None else 0

            distance = (dx**2 + dy**2 + dz**2) ** 0.5

            if distance <= radius:
                entity_dict = dict(entity)
                entity_dict['distance'] = distance
                nearby.append(entity_dict)

        # Sort by distance
        nearby.sort(key=lambda e: e['distance'])
        return nearby

    def get_entity_by_creature_id(self, creature_id: str) -> Optional[Dict]:
        """Get spatial entity for a creature"""
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM spatial_entities WHERE creature_id = ?
            """, (creature_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ========================================================================
    # EVENT LOGGING
    # ========================================================================

    def _log_spatial_event(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        event_type: str,
        event_data: Dict,
        location_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        creature_id: Optional[str] = None,
        caused_by: str = 'system',
        triggering_action: Optional[str] = None
    ):
        """Log a spatial event (internal method, uses existing connection)"""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO spatial_events (
                session_id, event_type, location_id, entity_id, creature_id,
                event_data, caused_by, triggering_action, game_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, event_type, location_id, entity_id, creature_id,
            json.dumps(event_data), caused_by, triggering_action,
            datetime.now().isoformat()
        ))

    def get_spatial_events(
        self,
        session_id: str,
        event_type: Optional[str] = None,
        location_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Query spatial event history.

        Args:
            session_id: Session ID
            event_type: Filter by event type (optional)
            location_id: Filter by location (optional)
            limit: Max events to return

        Returns:
            List of events ordered by time (newest first)
        """
        conn = self._get_game_connection()
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM spatial_events WHERE session_id = ?"
            params = [session_id]

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            if location_id:
                query += " AND location_id = ?"
                params.append(location_id)

            query += " ORDER BY real_time DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_tile_size_for_scale(self, scale_band: str) -> Optional[float]:
        """Get tile size in meters for a scale band"""
        conn = self._get_ref_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tile_size_meters FROM scale_bands WHERE band_id = ?
            """, (scale_band,))
            row = cursor.fetchone()
            return row['tile_size_meters'] if row else None
        finally:
            conn.close()

    def _get_min_volume_for_scale(self, scale_band: str) -> float:
        """Get minimum entity volume for a scale band"""
        conn = self._get_ref_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT min_entity_volume_m3 FROM scale_bands WHERE band_id = ?
            """, (scale_band,))
            row = cursor.fetchone()
            return row['min_entity_volume_m3'] if row else 0.0
        finally:
            conn.close()

    def _is_position_in_location(
        self,
        location: Dict,
        x: float,
        y: float,
        z: float
    ) -> bool:
        """Check if position is within location bounds"""
        return (
            location['x_min'] <= x <= location['x_max'] and
            location['y_min'] <= y <= location['y_max'] and
            location['z_min'] <= z <= location['z_max']
        )

    def _calculate_footprint_tiles(
        self,
        width_meters: float,
        depth_meters: float,
        tile_size: float
    ) -> List[List[int]]:
        """
        Calculate tile offsets for multi-tile entity.

        Returns list of [dx, dy] offsets from entity center.
        """
        tiles_wide = max(1, round(width_meters / tile_size))
        tiles_deep = max(1, round(depth_meters / tile_size))

        footprint = []
        for dy in range(tiles_deep):
            for dx in range(tiles_wide):
                footprint.append([dx, dy])

        return footprint
