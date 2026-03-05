"""
Movement Tools - Handle character movement with spatial system integration

These tools handle movement at different scales:
- Within location: update x, y coordinates
- Between locations: change location_id and reset coordinates
"""

# Tool definitions for movement
MOVEMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "move_character",
            "description": "Move character within current location or to a nearby destination. Updates spatial coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_name": {
                        "type": "string",
                        "description": "Name of character to move"
                    },
                    "direction": {
                        "type": "string",
                        "description": "Direction to move (north, south, east, west, forward, back, etc.)"
                    },
                    "distance": {
                        "type": "number",
                        "description": "Distance to move in meters (optional, default 5m)"
                    },
                    "target_location": {
                        "type": "string",
                        "description": "Named location to move to (e.g., 'the tavern', 'the castle')"
                    }
                },
                "required": []
            }
        }
    }
]


def move_character(
    character_name: str,
    spatial_agent,
    session_id: str,
    game_state=None,
    direction: str = None,
    distance: float = 5.0,
    target_location: str = None,
    target_x: float = None,
    target_y: float = None
) -> dict:
    """
    Move a character using the spatial system.

    Handles both combat and narrative movement:
    - Combat: Strict movement speed limits, conditions checked
    - Narrative: Flexible movement, can take multiple turns

    Args:
        character_name: Character to move
        spatial_agent: Spatial agent instance
        session_id: Current session ID
        game_state: GameState for checking combat mode and character stats
        direction: Direction to move (north, south, east, west, forward, back)
        distance: Distance in meters
        target_location: Named location to move to

    Returns:
        Dict with move status and new position
    """
    if not spatial_agent:
        return {
            'tool': 'move_character',
            'status': 'error',
            'error': 'Spatial system not available'
        }

    # Get character's spatial entity
    entity = spatial_agent.get_entity_by_creature_id(character_name)
    if not entity:
        return {
            'tool': 'move_character',
            'status': 'error',
            'error': f"Character '{character_name}' not found in spatial system"
        }

    current_x, current_y = entity['x'], entity['y']
    entity_id = entity['id']

    # Check if in combat mode
    in_combat = game_state.in_combat if game_state else False

    # Get character data for movement speed and conditions
    character = None
    if game_state:
        character = game_state.get_character(character_name)

    # Check movement-impairing conditions
    if character:
        conditions = getattr(character, 'conditions', [])
        blocking_conditions = {
            'paralyzed': 'paralyzed and cannot move',
            'petrified': 'petrified and cannot move',
            'stunned': 'stunned and cannot move',
            'unconscious': 'unconscious and cannot move',
            'grappled': 'grappled (use action to break free first)',
            'restrained': 'restrained (movement costs double)',
        }

        for condition in conditions:
            condition_lower = condition.lower()
            if condition_lower in ['paralyzed', 'petrified', 'stunned', 'unconscious', 'grappled']:
                return {
                    'tool': 'move_character',
                    'status': 'blocked',
                    'error': f"Cannot move: {blocking_conditions[condition_lower]}",
                    'condition': condition
                }
            elif condition_lower == 'prone':
                # Prone: standing up costs half movement
                distance = distance / 2
            elif condition_lower == 'restrained':
                # Restrained: movement costs double
                distance = distance / 2

    # Get movement speed (default 30ft = 9m per turn)
    movement_speed = 9.0  # Default D&D movement speed in meters
    if character:
        # Check for movement speed attribute
        speed_ft = getattr(character, 'movement_speed', 30)
        movement_speed = speed_ft * 0.3048  # Convert feet to meters

    # ================================================================
    # COMBAT MODE: Strict movement limits
    # ================================================================
    if in_combat:
        # Check if character has already used movement this turn
        # (This would need turn tracking - for now, just validate distance)
        if distance > movement_speed:
            return {
                'tool': 'move_character',
                'status': 'limited',
                'error': f"In combat, can only move {movement_speed:.1f}m per turn (requested: {distance:.1f}m)",
                'max_movement': movement_speed,
                'requested_movement': distance,
                'suggestions': [
                    f"Move {movement_speed:.1f}m this turn",
                    "Use Dash action to double movement speed",
                    "Complete movement over multiple turns"
                ],
                'is_combat': True
            }

        # Validate distance doesn't exceed movement speed
        actual_distance = min(distance, movement_speed)

    # ================================================================
    # NARRATIVE MODE: Flexible movement
    # ================================================================
    else:
        # In narrative mode, long distances are OK
        # We'll handle them as multi-turn descriptive movement
        actual_distance = distance

        if distance > movement_speed * 3:
            # Very long distance - narrative description will handle
            return {
                'tool': 'move_character',
                'status': 'narrative',
                'message': f"Moving {distance:.0f}m to {direction or target_location}",
                'is_narrative': True,
                'estimated_turns': int(distance / movement_speed),
                'note': 'Long-distance travel - DM will describe journey with potential events'
            }

    # If target coordinates provided (from spatial translation), move toward them
    if target_x is not None and target_y is not None:
        # Calculate direction and distance to target
        dx = target_x - current_x
        dy = target_y - current_y
        target_distance = (dx**2 + dy**2)**0.5

        if target_distance < 0.5:  # Already at target
            return {
                'tool': 'move_character',
                'action': 'move_character',
                'status': 'success',
                'character': character_name,
                'new_position': {'x': current_x, 'y': current_y},
                'distance': 0.0,
                'at_target': True,
                'message': f"{character_name} is already at the destination",
            }

        # Move toward target (up to actual_distance)
        if target_distance <= actual_distance:
            # Can reach target
            new_x = target_x
            new_y = target_y
            actual_distance = target_distance
        else:
            # Move partial distance toward target
            ratio = actual_distance / target_distance
            new_x = current_x + dx * ratio
            new_y = current_y + dy * ratio

    # Calculate new position based on direction
    elif direction:
        direction_vectors = {
            'north': (0, actual_distance),
            'south': (0, -actual_distance),
            'east': (actual_distance, 0),
            'west': (-actual_distance, 0),
            'northeast': (actual_distance * 0.707, actual_distance * 0.707),
            'northwest': (-actual_distance * 0.707, actual_distance * 0.707),
            'southeast': (actual_distance * 0.707, -actual_distance * 0.707),
            'southwest': (-actual_distance * 0.707, -actual_distance * 0.707),
            'forward': (0, actual_distance),  # Default forward = north
            'back': (0, -actual_distance),
        }

        direction_lower = direction.lower()
        if direction_lower in direction_vectors:
            dx, dy = direction_vectors[direction_lower]
            new_x = current_x + dx
            new_y = current_y + dy
        else:
            return {
                'tool': 'move_character',
                'status': 'error',
                'error': f"Unknown direction: '{direction}'"
            }
    elif target_location:
        # For now, target_location movement is narrative
        # In future, could look up location coordinates
        return {
            'tool': 'move_character',
            'status': 'narrative',
            'message': f"Moving to {target_location}",
            'is_narrative': True,
            'note': 'Location-based travel - DM will describe the journey'
        }
    else:
        return {
            'tool': 'move_character',
            'status': 'error',
            'error': 'Must specify either direction or target_location'
        }

    # Move entity using spatial agent
    success = spatial_agent.move_entity(
        entity_id=entity_id,
        new_x=new_x,
        new_y=new_y,
        caused_by='player_command',
        triggering_action='move_character'
    )

    if success:
        result = {
            'tool': 'move_character',
            'status': 'success',
            'character': character_name,
            'old_position': {'x': current_x, 'y': current_y},
            'new_position': {'x': new_x, 'y': new_y},
            'distance': actual_distance,
            'direction': direction,
            'is_combat': in_combat
        }

        # Add combat-specific information
        if in_combat:
            movement_remaining = movement_speed - actual_distance
            result['movement_remaining'] = movement_remaining
            result['movement_speed'] = movement_speed

        return result
    else:
        return {
            'tool': 'move_character',
            'status': 'error',
            'error': 'Failed to update position (may be out of bounds)',
            'is_combat': in_combat
        }


# Function map for execution
MOVEMENT_FUNCTION_MAP = {
    "move_character": move_character
}
