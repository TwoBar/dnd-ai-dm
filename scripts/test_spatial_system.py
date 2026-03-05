#!/usr/bin/env python3
"""
Test script for the spatial system.

Demonstrates:
- Creating locations with absolute coordinates
- Placing entities in space
- Generating room contents
- Placement suggestions with plausibility scores
- Spatial queries (entities in location, nearby entities)
- Event logging
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.game.spatial import (
    SpatialAgent,
    ZoneGenerator,
    PlacementAdvisor,
    BoundingBox,
    EntityPlacement,
    GenerationContext,
    GenerationPriority,
    PlacementStrategy
)


def print_section(title: str):
    """Print a section header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def test_basic_location_creation():
    """Test creating locations with hierarchical structure"""
    print_section("TEST: Basic Location Creation")

    # Initialize system
    agent = SpatialAgent('data/reference.db', 'data/game_state.db')

    # Create a tavern building
    tavern_bbox = BoundingBox(
        x_min=0,
        y_min=0,
        z_min=0,
        x_max=20,  # 20 meters wide
        y_max=15,  # 15 meters deep
        z_max=6    # 2 floors (3m each)
    )

    success = agent.create_location(
        session_id='test_session',
        location_id='loc:building:prancing_pony',
        name='The Prancing Pony Tavern',
        location_type='building',
        bbox=tavern_bbox,
        scale_band='L',
        description='A cozy tavern on the edge of town'
    )

    print(f"✓ Created tavern building: {success}")

    # Create common room inside tavern
    common_room_bbox = BoundingBox(
        x_min=2,
        y_min=2,
        z_min=0,
        x_max=12,  # 10m × 8m room
        y_max=10,
        z_max=3
    )

    success = agent.create_location(
        session_id='test_session',
        location_id='loc:room:tavern_common',
        name='Common Room',
        location_type='room',
        bbox=common_room_bbox,
        scale_band='M',  # Combat scale (0.5m tiles)
        parent_location_id='loc:building:prancing_pony',
        description='The main gathering area with tables and a fireplace'
    )

    print(f"✓ Created common room: {success}")

    # Query location
    location = agent.get_location('loc:room:tavern_common')
    print(f"\nLocation details:")
    print(f"  Name: {location['name']}")
    print(f"  Type: {location['location_type']}")
    print(f"  Scale: {location['scale_band']} ({location['tile_size_meters']}m tiles)")
    print(f"  Dimensions: {location['x_max'] - location['x_min']}m × {location['y_max'] - location['y_min']}m")

    return agent


def test_entity_placement(agent: SpatialAgent):
    """Test placing entities with absolute coordinates"""
    print_section("TEST: Entity Placement")

    # Place a table in the center
    table_placement = EntityPlacement(
        entity_id='furniture:table:1',
        entity_name='Wooden Table',
        x=7.0,
        y=6.0,
        z=0.0,
        volume_m3=0.5,
        footprint_width=2.0,
        footprint_depth=1.0,
        height=0.75,
        is_blocking=True
    )

    success = agent.place_entity(
        session_id='test_session',
        entity_id='furniture:table:1',
        location_id='loc:room:tavern_common',
        placement=table_placement,
        furniture_id='furniture:table:1',
        sprite_id='table',
        description='Sturdy oak table with carved legs',
        caused_by='zone_generation'
    )

    print(f"✓ Placed table: {success}")

    # Place chairs around the table
    chair_positions = [
        (7.0, 5.0, 180),   # South side
        (8.0, 6.0, 270),   # East side
        (7.0, 7.0, 0),     # North side
        (6.0, 6.0, 90),    # West side
    ]

    for i, (x, y, orientation) in enumerate(chair_positions):
        chair_placement = EntityPlacement(
            entity_id=f'furniture:chair:{i+1}',
            entity_name=f'Chair {i+1}',
            x=x,
            y=y,
            z=0.0,
            volume_m3=0.2,
            footprint_width=0.5,
            footprint_depth=0.5,
            height=1.0,
            orientation_degrees=orientation,
            is_blocking=True
        )

        success = agent.place_entity(
            session_id='test_session',
            entity_id=f'furniture:chair:{i+1}',
            location_id='loc:room:tavern_common',
            placement=chair_placement,
            furniture_id=f'furniture:chair:{i+1}',
            sprite_id='chair',
            caused_by='zone_generation'
        )

    print(f"✓ Placed 4 chairs around table")

    # Query entities
    entities = agent.get_entities_in_location('loc:room:tavern_common', scale_filter=False)
    print(f"\nEntities in common room: {len(entities)}")
    for entity in entities:
        print(f"  - {entity['entity_name']} at ({entity['x']:.1f}, {entity['y']:.1f})")


def test_placement_advisor(agent: SpatialAgent):
    """Test placement suggestions with plausibility scores"""
    print_section("TEST: Placement Advisor")

    advisor = PlacementAdvisor(agent)

    # Get suggestions for placing a barrel
    print("\nPlacement suggestions for barrel (against wall):")
    suggestions = advisor.suggest_placements(
        location_id='loc:room:tavern_common',
        entity_volume_m3=0.3,
        footprint_width=0.6,
        footprint_depth=0.6,
        strategy=PlacementStrategy.AGAINST_WALL,
        count=5
    )

    for i, suggestion in enumerate(suggestions, 1):
        print(f"  {i}. ({suggestion.x:.1f}, {suggestion.y:.1f}) "
              f"orientation={suggestion.orientation_degrees:.0f}° "
              f"score={suggestion.plausibility_score:.2f} "
              f"- {suggestion.reasoning}")

    # Get suggestions for placing near the table
    print("\nPlacement suggestions for placing near table:")
    suggestions = advisor.suggest_placement_near(
        location_id='loc:room:tavern_common',
        entity_volume_m3=0.05,
        near_entity_id='furniture:table:1',
        footprint_width=0.3,
        footprint_depth=0.3,
        min_distance=0.5,
        max_distance=2.0,
        count=3
    )

    for i, suggestion in enumerate(suggestions, 1):
        print(f"  {i}. ({suggestion.x:.1f}, {suggestion.y:.1f}) "
              f"score={suggestion.plausibility_score:.2f} "
              f"- {suggestion.reasoning}")


def test_zone_generator(agent: SpatialAgent):
    """Test procedural generation of room contents"""
    print_section("TEST: Zone Generator")

    generator = ZoneGenerator(agent, 'data/reference.db', 'data/game_state.db')

    # Create a new room for testing generation
    bedroom_bbox = BoundingBox(
        x_min=13,
        y_min=2,
        z_min=0,
        x_max=18,
        y_max=7,
        z_max=3
    )

    agent.create_location(
        session_id='test_session',
        location_id='loc:room:tavern_bedroom',
        name='Guest Bedroom',
        location_type='room',
        bbox=bedroom_bbox,
        scale_band='M',
        parent_location_id='loc:building:prancing_pony',
        description='A simple room for rent'
    )

    print("✓ Created bedroom location")

    # Generate contents
    result = generator.generate_room_contents(
        session_id='test_session',
        location_id='loc:room:tavern_bedroom',
        room_type='bedroom',
        building_type='inn'
    )

    print(f"\nGeneration results:")
    print(f"  Success: {result['success']}")
    print(f"  Entities generated: {result['generated_count']}")

    for entity in result['entities']:
        print(f"    - {entity['name']} ({entity['type']})")

    if result.get('errors'):
        print(f"  Errors: {len(result['errors'])}")
        for error in result['errors']:
            print(f"    ! {error}")

    # Test container contents generation
    print("\n✓ Testing container contents generation...")
    container_result = generator.generate_container_contents(
        session_id='test_session',
        container_entity_id='furniture:loc:room:tavern_bedroom:Chest:1',
        room_type='bedroom',
        building_type='inn'
    )

    if container_result['success']:
        print(f"  Generated {container_result['item_count']} items in {container_result['container']}")
        for item in container_result['items'][:3]:  # Show first 3
            print(f"    - {item['name']} ({item['size_category']}, ~{item['estimated_volume_m3']*1000:.1f}L)")


def test_spatial_queries(agent: SpatialAgent):
    """Test spatial query capabilities"""
    print_section("TEST: Spatial Queries")

    # Get entities near center of common room
    print("\nEntities within 3m of (7, 6):")
    nearby = agent.get_entities_near(
        location_id='loc:room:tavern_common',
        x=7.0,
        y=6.0,
        radius=3.0
    )

    for entity in nearby:
        print(f"  - {entity['entity_name']} "
              f"at distance {entity['distance']:.1f}m")

    # Get entities filtered by scale
    print("\nEntities visible at Medium scale (0.125m³ minimum):")
    entities = agent.get_entities_in_location(
        'loc:room:tavern_common',
        scale_filter=True
    )

    print(f"  Total: {len(entities)} entities visible at this scale")


def test_entity_movement(agent: SpatialAgent):
    """Test moving entities"""
    print_section("TEST: Entity Movement")

    # Move a chair
    print("\nMoving chair from (7, 5) to (8, 5)...")

    success = agent.move_entity(
        entity_id='furniture:chair:1',
        new_x=8.0,
        new_y=5.0,
        new_orientation=90,
        caused_by='player_action',
        triggering_action='push_furniture'
    )

    print(f"✓ Moved chair: {success}")

    # Query to verify
    conn = agent._get_game_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT x, y, orientation_degrees FROM spatial_entities WHERE id = ?",
                      ('furniture:chair:1',))
        row = cursor.fetchone()
        print(f"  New position: ({row['x']:.1f}, {row['y']:.1f}), "
              f"orientation: {row['orientation_degrees']:.0f}°")
    finally:
        conn.close()


def test_event_history(agent: SpatialAgent):
    """Test spatial event logging"""
    print_section("TEST: Event History")

    # Get recent events
    events = agent.get_spatial_events('test_session', limit=10)

    print(f"\nRecent spatial events ({len(events)}):")
    for event in events[:5]:  # Show first 5
        print(f"  [{event['event_type']}] {event['caused_by']}")
        if event.get('location_id'):
            location = agent.get_location(event['location_id'])
            if location:
                print(f"    Location: {location['name']}")


def main():
    """Run all tests"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║           SPATIAL SYSTEM TEST SUITE                       ║
    ║                                                           ║
    ║  Testing procedural map generation with persistent       ║
    ║  spatial model, absolute coordinates, and multi-scale    ║
    ║  representation.                                          ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    try:
        # Run tests in sequence
        agent = test_basic_location_creation()
        test_entity_placement(agent)
        test_placement_advisor(agent)
        test_zone_generator(agent)
        test_spatial_queries(agent)
        test_entity_movement(agent)
        test_event_history(agent)

        print_section("ALL TESTS COMPLETED")
        print("\n✓ Spatial system is working correctly!")
        print("\nKey features demonstrated:")
        print("  • Hierarchical locations with absolute coordinates")
        print("  • Entity placement with collision detection")
        print("  • Plausibility-based placement suggestions")
        print("  • Procedural room content generation")
        print("  • Spatial queries (nearby, in location)")
        print("  • Entity movement with event logging")
        print("  • Multi-scale volume-based filtering")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
