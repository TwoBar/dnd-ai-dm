"""
Spatial System - Procedural map generation with persistent spatial model

This package provides the complete spatial system for D&D AI DM:
- Authoritative spatial state with absolute coordinates
- Lazy/on-demand location generation
- Multi-scale representation with volume-based filtering
- Event-driven mutation logging
- Plausibility-based entity placement

Main components:
- SpatialAgent: Core spatial state manager (authoritative)
- ZoneGenerator: Lazy procedural location generation
- PlacementAdvisor: Plausibility-based entity positioning

Usage example:
    from game.spatial import SpatialAgent, ZoneGenerator, PlacementAdvisor
    from game.spatial import BoundingBox, EntityPlacement, GenerationContext

    # Initialize
    agent = SpatialAgent('data/reference.db', 'data/game_state.db')
    generator = ZoneGenerator(agent, 'data/reference.db', 'data/game_state.db')
    advisor = PlacementAdvisor(agent)

    # Create a location
    bbox = BoundingBox(0, 0, 0, 15, 10, 3)
    agent.create_location(
        session_id='session123',
        location_id='loc:room:tavern_common',
        name='Tavern Common Room',
        location_type='room',
        bbox=bbox,
        scale_band='M'
    )

    # Generate contents
    generator.generate_room_contents(
        session_id='session123',
        location_id='loc:room:tavern_common',
        room_type='common_room',
        building_type='tavern'
    )

    # Get placement suggestions
    suggestions = advisor.suggest_placements(
        location_id='loc:room:tavern_common',
        entity_volume_m3=0.5,
        footprint_width=2.0,
        footprint_depth=1.0
    )
"""

from .spatial_agent import SpatialAgent, BoundingBox, EntityPlacement
from .zone_generator import ZoneGenerator, GenerationContext, GenerationPriority
from .placement_advisor import PlacementAdvisor, PlacementStrategy, PlacementSuggestion

__all__ = [
    # Core classes
    'SpatialAgent',
    'ZoneGenerator',
    'PlacementAdvisor',

    # Data classes
    'BoundingBox',
    'EntityPlacement',
    'GenerationContext',
    'PlacementSuggestion',

    # Enums
    'GenerationPriority',
    'PlacementStrategy',
]
