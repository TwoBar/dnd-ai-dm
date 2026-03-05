"""
SpatialTranslator - Converts natural language spatial references to coordinates/entities

This module handles translation of natural language like:
- "nearest goblin" → actual goblin entity ID
- "the bar" → bar entity coordinates
- "move north" → direction vector
- "behind the table" → relative position calculation
"""

import logging
import math
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SpatialReference:
    """Result of translating a spatial reference"""
    entity_id: Optional[str] = None  # If reference is to a specific entity
    position: Optional[Tuple[float, float]] = None  # If reference is to a position
    direction: Optional[Tuple[float, float]] = None  # If reference is directional
    distance: Optional[float] = None  # If distance was specified
    reference_type: str = "unknown"  # "entity", "position", "direction", "relative"
    confidence: float = 0.0  # 0-1 confidence in translation
    original_text: str = ""  # Original natural language


class SpatialTranslator:
    """
    Translates natural language spatial references to coordinates/entities.

    Uses:
    1. Keyword matching for common patterns ("nearest", "closest", cardinal directions)
    2. Entity name search
    3. Spatial relationship parsing ("behind", "next to", "north of")
    4. LLM fallback for complex queries (future enhancement)
    """

    # Cardinal direction vectors (normalized)
    DIRECTIONS = {
        'north': (0, 1),
        'south': (0, -1),
        'east': (1, 0),
        'west': (-1, 0),
        'northeast': (0.707, 0.707),
        'northwest': (-0.707, 0.707),
        'southeast': (0.707, -0.707),
        'southwest': (-0.707, -0.707),
        'ne': (0.707, 0.707),
        'nw': (-0.707, 0.707),
        'se': (0.707, -0.707),
        'sw': (-0.707, -0.707),
        'up': (0, 0),  # Z-axis (not used in 2D)
        'down': (0, 0),
    }

    # Distance keywords (meters)
    DISTANCES = {
        'close': 1.0,
        'near': 1.5,
        'nearby': 2.0,
        'far': 5.0,
        'distant': 10.0,
    }

    # Proximity keywords
    PROXIMITY_KEYWORDS = ['nearest', 'closest', 'next to', 'beside', 'adjacent to']

    # Relative position keywords
    RELATIVE_KEYWORDS = {
        'behind': 180,  # degrees offset from direction
        'in front of': 0,
        'to the left of': 90,
        'to the right of': -90,
        'above': 0,  # Z-axis
        'below': 0,
    }

    def __init__(self, spatial_agent):
        """
        Initialize SpatialTranslator.

        Args:
            spatial_agent: SpatialAgent instance for entity lookups
        """
        self.spatial_agent = spatial_agent

    def translate_target(
        self,
        natural_language: str,
        current_location_id: str,
        observer_position: Tuple[float, float],
        session_id: str
    ) -> Optional[SpatialReference]:
        """
        Translate natural language target reference to spatial information.

        Args:
            natural_language: User's target description (e.g., "nearest goblin", "the bar")
            current_location_id: Current location ID
            observer_position: Observer's (x, y) position
            session_id: Current session ID

        Returns:
            SpatialReference with entity_id or position, or None if can't translate
        """
        text_lower = natural_language.lower().strip()

        logger.debug(f"[SpatialTranslator] Translating: '{text_lower}'")

        # Strategy 1: Proximity keywords ("nearest goblin")
        if any(keyword in text_lower for keyword in self.PROXIMITY_KEYWORDS):
            result = self._translate_proximity(text_lower, current_location_id, observer_position, session_id)
            if result:
                return result

        # Strategy 2: Cardinal directions ("north", "move east")
        for direction, vector in self.DIRECTIONS.items():
            if direction in text_lower:
                return SpatialReference(
                    direction=vector,
                    reference_type="direction",
                    confidence=0.9,
                    original_text=natural_language
                )

        # Strategy 3: Entity name search ("the bar", "goblin 1")
        result = self._translate_entity_name(text_lower, current_location_id, session_id)
        if result:
            return result

        # Strategy 4: Relative position ("behind the table")
        result = self._translate_relative_position(text_lower, current_location_id, observer_position, session_id)
        if result:
            return result

        # Strategy 5: Absolute coordinates ("5, 5" or "position 3,4")
        result = self._translate_coordinates(text_lower)
        if result:
            return result

        logger.warning(f"[SpatialTranslator] Could not translate: '{natural_language}'")
        return None

    def _translate_proximity(
        self,
        text: str,
        location_id: str,
        observer_pos: Tuple[float, float],
        session_id: str
    ) -> Optional[SpatialReference]:
        """
        Translate proximity references like "nearest goblin" or "closest enemy".

        Args:
            text: Lowercased text
            location_id: Current location
            observer_pos: Observer position (x, y)
            session_id: Session ID

        Returns:
            SpatialReference for nearest matching entity
        """
        # Extract entity type from text
        # "nearest goblin" → "goblin"
        # "closest enemy" → "enemy"

        entity_type_patterns = [
            r'nearest (\w+)',
            r'closest (\w+)',
            r'next to (\w+)',
            r'beside (\w+)',
        ]

        entity_type = None
        for pattern in entity_type_patterns:
            match = re.search(pattern, text)
            if match:
                entity_type = match.group(1)
                break

        if not entity_type:
            return None

        # Get all entities in location (scale_filter=False to include small entities)
        entities = self.spatial_agent.get_entities_in_location(location_id, scale_filter=False)

        # Filter by type
        matching_entities = []
        for entity in entities:
            entity_name = entity.get('entity_name', '').lower()
            entity_metadata = entity.get('entity_metadata', {})

            # Match by name or type
            if (entity_type in entity_name or
                entity_type in str(entity_metadata.get('type', '')).lower()):
                matching_entities.append(entity)

        if not matching_entities:
            logger.debug(f"[SpatialTranslator] No entities found matching '{entity_type}'")
            return None

        # Find nearest
        nearest = min(
            matching_entities,
            key=lambda e: self._distance(observer_pos, (e['x'], e['y']))
        )

        distance = self._distance(observer_pos, (nearest['x'], nearest['y']))

        return SpatialReference(
            entity_id=nearest['entity_id'],
            position=(nearest['x'], nearest['y']),
            distance=distance,
            reference_type="entity",
            confidence=0.9,
            original_text=text
        )

    def _translate_entity_name(
        self,
        text: str,
        location_id: str,
        session_id: str
    ) -> Optional[SpatialReference]:
        """
        Translate entity name references like "the bar" or "goblin".

        Args:
            text: Lowercased text
            location_id: Current location
            session_id: Session ID

        Returns:
            SpatialReference for matching entity
        """
        # Remove common articles
        cleaned = text.replace('the ', '').replace('a ', '').replace('an ', '')

        # Get all entities (scale_filter=False to include small entities like furniture)
        entities = self.spatial_agent.get_entities_in_location(location_id, scale_filter=False)

        # Fuzzy match by name
        for entity in entities:
            entity_name = entity.get('entity_name', '').lower()

            # Exact match
            if entity_name == cleaned:
                return SpatialReference(
                    entity_id=entity.get('id', entity.get('entity_id', 'unknown')),
                    position=(entity['x'], entity['y']),
                    reference_type="entity",
                    confidence=1.0,
                    original_text=text
                )

            # Partial match (e.g., "bar" matches "Bar Counter")
            if cleaned in entity_name or entity_name in cleaned:
                return SpatialReference(
                    entity_id=entity.get('id', entity.get('entity_id', 'unknown')),
                    position=(entity['x'], entity['y']),
                    reference_type="entity",
                    confidence=0.7,
                    original_text=text
                )

        return None

    def _translate_relative_position(
        self,
        text: str,
        location_id: str,
        observer_pos: Tuple[float, float],
        session_id: str
    ) -> Optional[SpatialReference]:
        """
        Translate relative position like "behind the table" or "north of the bar".

        Args:
            text: Lowercased text
            location_id: Current location
            observer_pos: Observer position
            session_id: Session ID

        Returns:
            SpatialReference with calculated position
        """
        # Pattern: <relative_word> the <entity_name>
        # e.g., "behind the table", "north of the bar"

        for rel_keyword, angle_offset in self.RELATIVE_KEYWORDS.items():
            if rel_keyword in text:
                # Extract entity name after the keyword
                parts = text.split(rel_keyword)
                if len(parts) < 2:
                    continue

                entity_ref = parts[1].strip()

                # Find the entity
                entity_result = self._translate_entity_name(entity_ref, location_id, session_id)
                if not entity_result or not entity_result.position:
                    continue

                # Calculate relative position
                # For now, simple: 1.5m in the direction of the relative keyword
                base_x, base_y = entity_result.position

                if rel_keyword == 'behind':
                    # Behind = opposite direction from observer
                    dx = base_x - observer_pos[0]
                    dy = base_y - observer_pos[1]
                    distance = math.sqrt(dx**2 + dy**2)
                    if distance > 0:
                        # Normalize and extend
                        nx, ny = dx / distance, dy / distance
                        new_x = base_x + nx * 1.5
                        new_y = base_y + ny * 1.5
                    else:
                        new_x, new_y = base_x, base_y

                elif rel_keyword == 'in front of':
                    # In front = between observer and entity
                    dx = base_x - observer_pos[0]
                    dy = base_y - observer_pos[1]
                    distance = math.sqrt(dx**2 + dy**2)
                    if distance > 0:
                        nx, ny = dx / distance, dy / distance
                        new_x = base_x - nx * 1.5
                        new_y = base_y - ny * 1.5
                    else:
                        new_x, new_y = base_x, base_y

                else:
                    # Generic: offset by 1.5m in the specified direction
                    # (simplified, would need actual orientation)
                    new_x = base_x + 1.5
                    new_y = base_y

                return SpatialReference(
                    position=(new_x, new_y),
                    reference_type="relative",
                    confidence=0.7,
                    original_text=text
                )

        return None

    def _translate_coordinates(self, text: str) -> Optional[SpatialReference]:
        """
        Translate absolute coordinate references like "5, 5" or "position 3,4".

        Args:
            text: Lowercased text

        Returns:
            SpatialReference with position
        """
        # Pattern: numbers separated by comma or space
        # e.g., "5,5", "5, 5", "5 5", "position 5,5"

        patterns = [
            r'(\d+\.?\d*)\s*,\s*(\d+\.?\d*)',  # "5,5" or "5.5, 3.2"
            r'position\s+(\d+\.?\d*)\s+(\d+\.?\d*)',  # "position 5 5"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                x = float(match.group(1))
                y = float(match.group(2))
                return SpatialReference(
                    position=(x, y),
                    reference_type="position",
                    confidence=1.0,
                    original_text=text
                )

        return None

    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions"""
        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        return math.sqrt(dx**2 + dy**2)

    def extract_movement_distance(self, text: str) -> Optional[float]:
        """
        Extract movement distance from text like "move 5 feet" or "step back".

        Args:
            text: Natural language text

        Returns:
            Distance in meters, or None
        """
        text_lower = text.lower()

        # Pattern: "<number> <unit>"
        # Support: feet, meters, m, ft, squares/tiles
        patterns = [
            (r'(\d+\.?\d*)\s*(?:feet|ft)', 0.3048),  # feet to meters
            (r'(\d+\.?\d*)\s*(?:meters?|m)', 1.0),  # meters
            (r'(\d+\.?\d*)\s*(?:squares?|tiles?)', 1.5),  # D&D squares (5ft = 1.5m)
        ]

        for pattern, multiplier in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = float(match.group(1))
                return value * multiplier

        # Keyword-based defaults
        if 'step' in text_lower or 'short' in text_lower:
            return 1.5  # One square

        if 'stride' in text_lower or 'long' in text_lower:
            return 3.0  # Two squares

        return None
