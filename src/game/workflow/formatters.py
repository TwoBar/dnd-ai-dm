"""
Mechanics summary formatting.

Converts raw mechanics results into human-readable summaries.
"""
from typing import Dict, Optional


def format_mechanics_summary(mechanics_result: Optional[Dict]) -> str:
    """Format mechanics result into human-readable summary"""
    if not mechanics_result:
        return ""

    lines = []

    # Format dice rolls
    for roll in mechanics_result.get('dice_rolls', []):
        notation = roll.get('notation', '?')
        result = roll.get('result', 0)
        rolls = roll.get('rolls', [])
        line = f"🎲 {notation} = {result}"
        if rolls:
            line += f" ({', '.join(map(str, rolls))})"
        if roll.get('is_critical'):
            line += " [CRITICAL!]"
        elif roll.get('is_fumble'):
            line += " [FUMBLE!]"
        lines.append(line)

    # Format actions
    for action in mechanics_result.get('actions', []):
        action_type = action.get('action', 'unknown')
        if action_type == 'draft_character':
            char_details = action.get('details', '')
            if char_details:
                lines.append(f"✨ {char_details}")
            else:
                lines.append(f"✨ Created character: {action.get('name', 'Unknown')}")
        elif action_type == 'apply_damage':
            lines.append(f"⚔️ {action.get('target', 'Unknown')} takes {action.get('damage', 0)} damage")
        elif action_type == 'heal_character':
            lines.append(f"💚 {action.get('target', 'Unknown')} heals {action.get('healing', 0)} HP")
        elif action_type == 'move_character':
            _format_movement(action, lines)

    return "\n".join(lines)


def _format_movement(action: Dict, lines: list):
    """Format movement action details"""
    status = action.get('status', 'success')
    if status == 'success':
        character = action.get('character', 'Character')
        distance = action.get('distance', 0)
        new_pos = action.get('new_position', {})
        is_combat = action.get('is_combat', False)

        # Already at destination
        if action.get('at_target') or distance == 0:
            lines.append(f"🚶 {character} is already at the destination")
            return

        direction = action.get('direction') or 'forward'
        line = f"🚶 {character} moved {distance:.1f}m {direction}"
        if new_pos:
            line += f" to ({new_pos.get('x', 0):.1f}, {new_pos.get('y', 0):.1f})"
        if is_combat:
            movement_remaining = action.get('movement_remaining', 0)
            if movement_remaining > 0:
                line += f" [⚔️ {movement_remaining:.1f}m movement remaining this turn]"
            else:
                line += " [⚔️ Movement used]"
        lines.append(line)
    elif status == 'blocked':
        lines.append(f"❌ {action.get('character', 'Character')}: {action.get('error', 'Movement blocked')}")
    elif status == 'limited':
        lines.append(
            f"⚠️ {action.get('character', 'Character')} can only move "
            f"{action.get('max_movement', 0):.1f}m this turn "
            f"(requested: {action.get('requested_movement', 0):.1f}m)"
        )
    elif status == 'narrative':
        message = action.get('message', 'Moving')
        estimated_turns = action.get('estimated_turns')
        if estimated_turns:
            lines.append(f"🗺️ {message} (~{estimated_turns} turns of travel)")
        else:
            lines.append(f"🗺️ {message}")
