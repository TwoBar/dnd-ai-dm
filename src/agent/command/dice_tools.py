"""
Dice rolling tools for the Command Agent.
"""
from typing import Dict

from game.dice import roll as dice_roll


def tool_roll_dice(
    game_state,
    notation: str,
    advantage: bool = False,
    disadvantage: bool = False,
    context: str = None
) -> Dict:
    """Roll dice and log result."""
    dice_result = dice_roll(notation, advantage=advantage, disadvantage=disadvantage)

    result_total = dice_result.total
    critical = dice_result.is_critical
    fumble = dice_result.is_fumble

    game_state.add_dice_roll(notation, result_total, critical, fumble, description=str(dice_result))

    return {
        'tool': 'roll_dice',
        'status': 'success',
        'notation': notation,
        'result': str(dice_result),
        'total': result_total,
        'critical': critical,
        'fumble': fumble,
        'context': context
    }
