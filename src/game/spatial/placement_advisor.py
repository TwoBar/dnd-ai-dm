"""
PlacementAdvisor - Suggests entity placements with plausibility scores

This module suggests positions for entities without requiring a huge ontology.
Uses simple spatial rules and existing entities to provide plausible placements.

Key principles:
- Plausibility scores, not rigid rules
- Volume-based reasoning (not semantic types)
- Collision avoidance with existing entities
- Simple heuristics: walls, corners, centers, etc.
"""

import sqlite3
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .spatial_agent import SpatialAgent, BoundingBox


class PlacementStrategy(Enum):
    """Common placement strategies"""
    AGAINST_WALL = "against_wall"      # Furniture along walls
    IN_CORNER = "in_corner"            # Large items in corners
    CENTER = "center"                  # Tables, central features
    DISTRIBUTED = "distributed"        # Multiple small items spread out
    NEAR_OTHER = "near_other"          # Place near related entity
    RANDOM = "random"                  # Anywhere that fits


@dataclass
class PlacementSuggestion:
    """A suggested placement with plausibility score"""
    x: float
    y: float
    z: float
    orientation_degrees: float
    plausibility_score: float  # 0.0 to 1.0
    strategy: PlacementStrategy
    reasoning: str


class PlacementAdvisor:
    """
    Suggests entity placements with plausibility scores.

    Provides multiple placement suggestions ranked by plausibility.
    Does not enforce rigid rules - just suggestions.
    """

    def __init__(self, spatial_agent: SpatialAgent):
        """
        Initialize PlacementAdvisor.

        Args:
            spatial_agent: SpatialAgent instance for spatial queries
        """
        self.spatial_agent = spatial_agent

    # ========================================================================
    # PLACEMENT SUGGESTIONS
    # ========================================================================

    def suggest_placements(
        self,
        location_id: str,
        entity_volume_m3: float,
        footprint_width: Optional[float] = None,
        footprint_depth: Optional[float] = None,
        strategy: Optional[PlacementStrategy] = None,
        count: int = 5
    ) -> List[PlacementSuggestion]:
        """
        Suggest placements for an entity.

        Args:
            location_id: Location to place entity in
            entity_volume_m3: Volume of entity
            footprint_width: Width of entity footprint (meters)
            footprint_depth: Depth of entity footprint (meters)
            strategy: Preferred placement strategy (or auto-detect)
            count: Number of suggestions to generate

        Returns:
            List of placement suggestions ranked by plausibility
        """
        location = self.spatial_agent.get_location(location_id)
        if not location:
            return []

        bbox = BoundingBox(
            location['x_min'], location['y_min'], location['z_min'],
            location['x_max'], location['y_max'], location['z_max']
        )

        # Estimate footprint if not provided
        if footprint_width is None or footprint_depth is None:
            footprint_width, footprint_depth = self._estimate_footprint(
                entity_volume_m3
            )

        # Auto-detect strategy if not specified
        if strategy is None:
            strategy = self._suggest_strategy(entity_volume_m3, bbox)

        # Get existing entities for collision avoidance
        existing_entities = self.spatial_agent.get_entities_in_location(
            location_id, scale_filter=False
        )

        # Generate suggestions based on strategy
        suggestions = []

        if strategy == PlacementStrategy.AGAINST_WALL:
            suggestions = self._suggest_wall_placements(
                bbox, footprint_width, footprint_depth, existing_entities, count
            )

        elif strategy == PlacementStrategy.IN_CORNER:
            suggestions = self._suggest_corner_placements(
                bbox, footprint_width, footprint_depth, existing_entities, count
            )

        elif strategy == PlacementStrategy.CENTER:
            suggestions = self._suggest_center_placements(
                bbox, footprint_width, footprint_depth, existing_entities, count
            )

        elif strategy == PlacementStrategy.DISTRIBUTED:
            suggestions = self._suggest_distributed_placements(
                bbox, footprint_width, footprint_depth, existing_entities, count
            )

        elif strategy == PlacementStrategy.NEAR_OTHER:
            # Need reference entity - fall back to distributed
            suggestions = self._suggest_distributed_placements(
                bbox, footprint_width, footprint_depth, existing_entities, count
            )

        else:  # RANDOM
            suggestions = self._suggest_random_placements(
                bbox, footprint_width, footprint_depth, existing_entities, count
            )

        # Sort by plausibility score
        suggestions.sort(key=lambda s: s.plausibility_score, reverse=True)

        return suggestions[:count]

    def suggest_placement_near(
        self,
        location_id: str,
        entity_volume_m3: float,
        near_entity_id: str,
        footprint_width: Optional[float] = None,
        footprint_depth: Optional[float] = None,
        min_distance: float = 0.5,
        max_distance: float = 3.0,
        count: int = 5
    ) -> List[PlacementSuggestion]:
        """
        Suggest placements near another entity.

        Args:
            location_id: Location to place in
            entity_volume_m3: Volume of entity to place
            near_entity_id: Entity to place near
            footprint_width: Width of footprint
            footprint_depth: Depth of footprint
            min_distance: Minimum distance from target entity
            max_distance: Maximum distance from target entity
            count: Number of suggestions

        Returns:
            List of placement suggestions
        """
        # Get target entity position
        conn = self.spatial_agent._get_game_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT x, y, z FROM spatial_entities WHERE id = ?
            """, (near_entity_id,))
            row = cursor.fetchone()

            if not row:
                return []

            target_x, target_y, target_z = row['x'], row['y'], row['z']

        finally:
            conn.close()

        location = self.spatial_agent.get_location(location_id)
        if not location:
            return []

        bbox = BoundingBox(
            location['x_min'], location['y_min'], location['z_min'],
            location['x_max'], location['y_max'], location['z_max']
        )

        # Estimate footprint if not provided
        if footprint_width is None or footprint_depth is None:
            footprint_width, footprint_depth = self._estimate_footprint(
                entity_volume_m3
            )

        # Get existing entities
        existing_entities = self.spatial_agent.get_entities_in_location(
            location_id, scale_filter=False
        )

        suggestions = []

        # Try positions in a circle around target
        for i in range(count * 3):  # Generate more candidates
            angle = (i / (count * 3)) * 2 * math.pi
            distance = min_distance + (max_distance - min_distance) * (i % 3) / 2

            x = target_x + math.cos(angle) * distance
            y = target_y + math.sin(angle) * distance
            z = target_z

            # Check if position is valid
            if not bbox.contains_point(x, y, z):
                continue

            # Check collision
            if self._check_collision(x, y, footprint_width, footprint_depth, existing_entities):
                continue

            # Calculate plausibility
            actual_distance = math.sqrt((x - target_x)**2 + (y - target_y)**2)
            plausibility = 1.0 - abs(actual_distance - (min_distance + max_distance) / 2) / max_distance

            suggestions.append(PlacementSuggestion(
                x=x,
                y=y,
                z=z,
                orientation_degrees=math.degrees(math.atan2(target_y - y, target_x - x)),
                plausibility_score=max(0.1, min(1.0, plausibility)),
                strategy=PlacementStrategy.NEAR_OTHER,
                reasoning=f"Placed {actual_distance:.1f}m from target"
            ))

        suggestions.sort(key=lambda s: s.plausibility_score, reverse=True)
        return suggestions[:count]

    # ========================================================================
    # STRATEGY-SPECIFIC METHODS
    # ========================================================================

    def _suggest_wall_placements(
        self,
        bbox: BoundingBox,
        width: float,
        depth: float,
        existing: List,
        count: int
    ) -> List[PlacementSuggestion]:
        """Suggest placements against walls"""
        suggestions = []
        wall_offset = 0.5  # Distance from wall

        walls = [
            # (x_start, y_start, x_end, y_end, direction, orientation)
            (bbox.x_min + wall_offset, bbox.y_min + wall_offset,
             bbox.x_max - wall_offset, bbox.y_min + wall_offset, 'south', 0),
            (bbox.x_max - wall_offset, bbox.y_min + wall_offset,
             bbox.x_max - wall_offset, bbox.y_max - wall_offset, 'east', 90),
            (bbox.x_max - wall_offset, bbox.y_max - wall_offset,
             bbox.x_min + wall_offset, bbox.y_max - wall_offset, 'north', 180),
            (bbox.x_min + wall_offset, bbox.y_max - wall_offset,
             bbox.x_min + wall_offset, bbox.y_min + wall_offset, 'west', 270),
        ]

        for x_start, y_start, x_end, y_end, wall_name, orientation in walls:
            # Sample positions along this wall
            wall_length = math.sqrt((x_end - x_start)**2 + (y_end - y_start)**2)
            num_samples = max(3, int(wall_length / 2))

            for i in range(num_samples):
                t = i / max(num_samples - 1, 1)
                x = x_start + t * (x_end - x_start)
                y = y_start + t * (y_end - y_start)
                z = bbox.z_min

                # Check collision
                if self._check_collision(x, y, width, depth, existing):
                    continue

                # Higher plausibility for evenly spaced positions
                spacing_score = 1.0 - abs(t - 0.5)

                suggestions.append(PlacementSuggestion(
                    x=x,
                    y=y,
                    z=z,
                    orientation_degrees=orientation,
                    plausibility_score=0.8 + spacing_score * 0.2,
                    strategy=PlacementStrategy.AGAINST_WALL,
                    reasoning=f"Against {wall_name} wall"
                ))

                if len(suggestions) >= count * 2:
                    break

        return suggestions

    def _suggest_corner_placements(
        self,
        bbox: BoundingBox,
        width: float,
        depth: float,
        existing: List,
        count: int
    ) -> List[PlacementSuggestion]:
        """Suggest placements in corners"""
        suggestions = []
        corner_offset = 1.0

        corners = [
            (bbox.x_min + corner_offset, bbox.y_min + corner_offset, 45, 'southwest'),
            (bbox.x_max - corner_offset, bbox.y_min + corner_offset, 135, 'southeast'),
            (bbox.x_max - corner_offset, bbox.y_max - corner_offset, 225, 'northeast'),
            (bbox.x_min + corner_offset, bbox.y_max - corner_offset, 315, 'northwest'),
        ]

        for x, y, orientation, corner_name in corners:
            z = bbox.z_min

            # Check collision
            if self._check_collision(x, y, width, depth, existing):
                continue

            suggestions.append(PlacementSuggestion(
                x=x,
                y=y,
                z=z,
                orientation_degrees=orientation,
                plausibility_score=0.9,
                strategy=PlacementStrategy.IN_CORNER,
                reasoning=f"In {corner_name} corner"
            ))

        return suggestions

    def _suggest_center_placements(
        self,
        bbox: BoundingBox,
        width: float,
        depth: float,
        existing: List,
        count: int
    ) -> List[PlacementSuggestion]:
        """Suggest placements near center"""
        suggestions = []
        center = bbox.center

        # Try exact center and nearby positions
        offsets = [
            (0, 0, 1.0, "center"),
            (1.0, 0, 0.8, "center-east"),
            (-1.0, 0, 0.8, "center-west"),
            (0, 1.0, 0.8, "center-north"),
            (0, -1.0, 0.8, "center-south"),
        ]

        for dx, dy, score, description in offsets:
            x = center[0] + dx
            y = center[1] + dy
            z = bbox.z_min

            if not bbox.contains_point(x, y, z):
                continue

            if self._check_collision(x, y, width, depth, existing):
                continue

            suggestions.append(PlacementSuggestion(
                x=x,
                y=y,
                z=z,
                orientation_degrees=0,
                plausibility_score=score,
                strategy=PlacementStrategy.CENTER,
                reasoning=f"At {description}"
            ))

        return suggestions

    def _suggest_distributed_placements(
        self,
        bbox: BoundingBox,
        width: float,
        depth: float,
        existing: List,
        count: int
    ) -> List[PlacementSuggestion]:
        """Suggest evenly distributed placements"""
        suggestions = []

        # Create grid of sample points
        grid_size = max(3, int(math.sqrt(count * 2)))
        step_x = bbox.width / (grid_size + 1)
        step_y = bbox.height / (grid_size + 1)

        for i in range(1, grid_size + 1):
            for j in range(1, grid_size + 1):
                x = bbox.x_min + i * step_x
                y = bbox.y_min + j * step_y
                z = bbox.z_min

                if self._check_collision(x, y, width, depth, existing):
                    continue

                # Higher score for positions away from edges
                edge_dist = min(
                    x - bbox.x_min,
                    bbox.x_max - x,
                    y - bbox.y_min,
                    bbox.y_max - y
                )
                edge_score = min(1.0, edge_dist / 2.0)

                suggestions.append(PlacementSuggestion(
                    x=x,
                    y=y,
                    z=z,
                    orientation_degrees=0,
                    plausibility_score=0.5 + edge_score * 0.5,
                    strategy=PlacementStrategy.DISTRIBUTED,
                    reasoning=f"Grid position ({i}, {j})"
                ))

        return suggestions

    def _suggest_random_placements(
        self,
        bbox: BoundingBox,
        width: float,
        depth: float,
        existing: List,
        count: int
    ) -> List[PlacementSuggestion]:
        """Suggest random valid placements"""
        import random
        suggestions = []

        attempts = count * 10
        for _ in range(attempts):
            x = random.uniform(bbox.x_min + width/2, bbox.x_max - width/2)
            y = random.uniform(bbox.y_min + depth/2, bbox.y_max - depth/2)
            z = bbox.z_min
            orientation = random.uniform(0, 360)

            if self._check_collision(x, y, width, depth, existing):
                continue

            suggestions.append(PlacementSuggestion(
                x=x,
                y=y,
                z=z,
                orientation_degrees=orientation,
                plausibility_score=0.5,
                strategy=PlacementStrategy.RANDOM,
                reasoning="Random placement"
            ))

            if len(suggestions) >= count:
                break

        return suggestions

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _estimate_footprint(self, volume_m3: float) -> Tuple[float, float]:
        """
        Estimate footprint dimensions from volume.

        Assumes roughly cubic proportions with reasonable height.
        """
        # Assume height is 1/3 of cube root of volume for most objects
        cube_root = volume_m3 ** (1/3)
        height = cube_root * 0.5
        base_area = volume_m3 / max(height, 0.1)

        # Assume square base for simplicity
        side = math.sqrt(base_area)

        return (side, side)

    def _suggest_strategy(
        self,
        volume_m3: float,
        bbox: BoundingBox
    ) -> PlacementStrategy:
        """Auto-detect best placement strategy based on volume"""
        room_volume = bbox.width * bbox.height * bbox.depth

        # Very large items go in corners
        if volume_m3 > room_volume * 0.1:
            return PlacementStrategy.IN_CORNER

        # Medium-large items against walls
        if volume_m3 > room_volume * 0.02:
            return PlacementStrategy.AGAINST_WALL

        # Small items distributed
        return PlacementStrategy.DISTRIBUTED

    def _check_collision(
        self,
        x: float,
        y: float,
        width: float,
        depth: float,
        existing_entities: List
    ) -> bool:
        """
        Check if placement would collide with existing entities.

        Simple bounding box collision check.
        """
        half_w = width / 2
        half_d = depth / 2

        for entity in existing_entities:
            # Skip non-blocking entities
            if not entity.get('is_blocking', True):
                continue

            # Get entity bounds
            entity_x = entity['x']
            entity_y = entity['y']
            entity_w = entity.get('footprint_width', 0.5) / 2
            entity_d = entity.get('footprint_depth', 0.5) / 2

            # AABB collision check
            if (abs(x - entity_x) < (half_w + entity_w) and
                abs(y - entity_y) < (half_d + entity_d)):
                return True

        return False
