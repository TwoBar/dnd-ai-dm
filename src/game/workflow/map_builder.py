"""
Map state builder for frontend visualization.

Builds the map_state dict from spatial agent data.
"""
from typing import Dict, List, Optional


def build_map_state(spatial_agent, session_id: str, location_id: str) -> Optional[Dict]:
    """
    Build map state data for frontend visualization.

    Shows ALL creatures across all sessions (shared world) and tags each
    with ``is_own_session`` so the frontend can render own vs. other players
    differently.

    Args:
        spatial_agent: SpatialAgent instance
        session_id: Current session ID
        location_id: Current location ID

    Returns:
        Dictionary with map data (bbox, entities, walls, connections) or None
    """
    if not spatial_agent:
        return None

    try:
        location = spatial_agent.get_location(location_id)
        if not location:
            return None

        bbox = {
            'min_x': location.get('x_min', 0),
            'max_x': location.get('x_max', 20),
            'min_y': location.get('y_min', 0),
            'max_y': location.get('y_max', 20)
        }

        all_entities = spatial_agent.get_entities_in_location(
            location_id=location_id, scale_filter=False
        )

        entities = []
        walls = []

        for entity in all_entities:
            entity_session = entity.get('session_id', '')
            is_creature = bool(entity.get('creature_id'))
            is_furniture = bool(entity.get('furniture_id'))

            # Furniture is world state — always show regardless of session_id
            # Non-creature, non-furniture entities: show if 'world' or own session
            if not is_creature and not is_furniture and entity_session not in ('world', session_id):
                continue

            is_own = entity_session == session_id
            entity_id = entity.get('id', '')

            entity_data = {
                'id': entity_id,
                'x': entity.get('x', 0),
                'y': entity.get('y', 0),
                'entity_name': entity.get('entity_name', 'Unknown'),
                'creature_id': entity.get('creature_id'),
                'furniture_id': entity.get('furniture_id'),
                'sprite_id': entity.get('sprite_id'),
                'is_own_session': is_own,
                'session_id': entity_session,
            }

            if is_creature:
                # Distinguish monsters from player characters
                if entity_id.startswith('monster_'):
                    entity_data['entity_metadata'] = {'type': 'monster'}
                else:
                    entity_data['entity_metadata'] = {'type': 'player_character'}
                entities.append(entity_data)
            elif is_furniture:
                entity_data['entity_metadata'] = {'type': 'furniture'}
                entities.append(entity_data)
            elif entity.get('is_blocking'):
                walls.append({
                    'x': entity.get('x', 0),
                    'y': entity.get('y', 0),
                    'width': entity.get('footprint_width', 1),
                    'height': entity.get('footprint_depth', 1)
                })
                entity_data['entity_metadata'] = {'type': 'feature'}
                entities.append(entity_data)
            else:
                entity_data['entity_metadata'] = {'type': 'feature'}
                entities.append(entity_data)

        child_locations = spatial_agent.get_child_locations(location_id)
        connections = []
        for child in child_locations:
            conn_x = (child.get('x_min', 0) + child.get('x_max', 0)) / 2
            conn_y = child.get('y_min', 0)
            connections.append({
                'x': conn_x, 'y': conn_y,
                'label': child.get('name', 'Exit'),
                'target_location': child.get('id')
            })

        return {
            'location_id': location_id,
            'bbox': bbox,
            'entities': entities,
            'walls': walls,
            'connections': connections
        }

    except Exception as e:
        print(f"[MapBuilder] Error building map state: {e}")
        return None
