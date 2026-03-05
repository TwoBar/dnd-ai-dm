"""Dice rolling system for D&D"""
import re
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DiceRoll:
    """Result of a dice roll"""
    notation: str  # Original notation (e.g., "2d6+3")
    rolls: List[int]  # Individual die results
    modifier: int  # Added/subtracted modifier
    total: int  # Final total
    dice_type: str  # e.g., "d20", "d6"
    num_dice: int  # Number of dice rolled
    is_critical: bool = False  # True if natural 20 on d20
    is_fumble: bool = False  # True if natural 1 on d20
    advantage: bool = False  # Rolled with advantage
    disadvantage: bool = False  # Rolled with disadvantage
    dropped_rolls: List[int] = None  # Rolls that were dropped (advantage/disadvantage)

    def __str__(self):
        result = f"🎲 {self.notation} = "

        if self.advantage or self.disadvantage:
            all_rolls = self.rolls + (self.dropped_rolls or [])
            roll_str = ", ".join([
                f"**{r}**" if r in self.rolls else f"~~{r}~~"
                for r in sorted(all_rolls, reverse=True)
            ])
            result += f"[{roll_str}]"
        else:
            result += f"[{', '.join(map(str, self.rolls))}]"

        if self.modifier != 0:
            sign = "+" if self.modifier > 0 else ""
            result += f" {sign}{self.modifier}"

        result += f" = **{self.total}**"

        if self.is_critical:
            result += " 🎯 **CRITICAL HIT!**"
        elif self.is_fumble:
            result += " 💀 **FUMBLE!**"

        return result


class DiceRoller:
    """Comprehensive dice rolling system for D&D"""

    def __init__(self, seed: Optional[int] = None):
        if seed:
            random.seed(seed)

    def roll(
        self,
        notation: str,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> DiceRoll:
        """
        Roll dice from notation

        Args:
            notation: Dice notation (e.g., "2d6+3", "1d20", "4d6kh3")
            advantage: Roll with advantage (for d20 only)
            disadvantage: Roll with disadvantage (for d20 only)

        Returns:
            DiceRoll object with results

        Examples:
            roll("2d6+3") → Roll 2d6 and add 3
            roll("1d20", advantage=True) → Roll 2d20, take higher
            roll("4d6kh3") → Roll 4d6, keep highest 3
        """
        # Parse notation
        parsed = self._parse_notation(notation)
        if not parsed:
            raise ValueError(f"Invalid dice notation: {notation}")

        num_dice, dice_type, modifier, keep_mode, keep_count = parsed

        # Handle advantage/disadvantage for d20
        if dice_type == 20 and num_dice == 1:
            if advantage and disadvantage:
                # They cancel out
                advantage = disadvantage = False
            elif advantage or disadvantage:
                # Roll 2d20
                roll1 = random.randint(1, dice_type)
                roll2 = random.randint(1, dice_type)

                if advantage:
                    rolls = [max(roll1, roll2)]
                    dropped = [min(roll1, roll2)]
                else:  # disadvantage
                    rolls = [min(roll1, roll2)]
                    dropped = [max(roll1, roll2)]

                total = rolls[0] + modifier
                is_critical = rolls[0] == 20
                is_fumble = rolls[0] == 1

                return DiceRoll(
                    notation=notation,
                    rolls=rolls,
                    modifier=modifier,
                    total=total,
                    dice_type=f"d{dice_type}",
                    num_dice=1,
                    is_critical=is_critical,
                    is_fumble=is_fumble,
                    advantage=advantage,
                    disadvantage=disadvantage,
                    dropped_rolls=dropped
                )

        # Regular dice rolling
        rolls = [random.randint(1, dice_type) for _ in range(num_dice)]

        # Handle keep highest/lowest
        dropped_rolls = None
        if keep_mode and keep_count:
            original_rolls = rolls.copy()
            if keep_mode == "kh":  # Keep highest
                rolls = sorted(rolls, reverse=True)[:keep_count]
            elif keep_mode == "kl":  # Keep lowest
                rolls = sorted(rolls)[:keep_count]
            dropped_rolls = [r for r in original_rolls if r not in rolls]

        # Calculate total
        total = sum(rolls) + modifier

        # Check for critical/fumble (d20 only)
        is_critical = dice_type == 20 and len(rolls) == 1 and rolls[0] == 20
        is_fumble = dice_type == 20 and len(rolls) == 1 and rolls[0] == 1

        return DiceRoll(
            notation=notation,
            rolls=rolls,
            modifier=modifier,
            total=total,
            dice_type=f"d{dice_type}",
            num_dice=num_dice,
            is_critical=is_critical,
            is_fumble=is_fumble,
            dropped_rolls=dropped_rolls
        )

    def roll_attack(
        self,
        ability_modifier: int,
        proficiency_bonus: int = 0,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> DiceRoll:
        """Roll an attack (d20 + modifiers)"""
        modifier = ability_modifier + proficiency_bonus
        notation = f"1d20+{modifier}" if modifier >= 0 else f"1d20{modifier}"
        return self.roll(notation, advantage=advantage, disadvantage=disadvantage)

    def roll_damage(
        self,
        dice_notation: str,
        ability_modifier: int = 0,
        critical: bool = False
    ) -> DiceRoll:
        """
        Roll damage

        Args:
            dice_notation: Base damage (e.g., "1d8", "2d6")
            ability_modifier: Modifier to add
            critical: If True, double the dice (not the modifier)
        """
        # Parse base damage
        parsed = self._parse_notation(dice_notation)
        if not parsed:
            raise ValueError(f"Invalid damage notation: {dice_notation}")

        num_dice, dice_type, base_mod, _, _ = parsed

        # Double dice on critical
        if critical:
            num_dice *= 2

        # Build notation with ability modifier
        total_modifier = base_mod + ability_modifier
        notation = f"{num_dice}d{dice_type}"
        if total_modifier != 0:
            notation += f"+{total_modifier}" if total_modifier > 0 else f"{total_modifier}"

        return self.roll(notation)

    def roll_ability_check(
        self,
        ability_modifier: int,
        proficiency_bonus: int = 0,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> DiceRoll:
        """Roll an ability check or saving throw"""
        return self.roll_attack(ability_modifier, proficiency_bonus, advantage, disadvantage)

    def roll_multiple(self, notation: str, times: int) -> List[DiceRoll]:
        """Roll the same dice multiple times"""
        return [self.roll(notation) for _ in range(times)]

    def roll_stats(self, method: str = "4d6kh3") -> List[int]:
        """
        Roll ability scores

        Args:
            method: Rolling method
                "4d6kh3" - Roll 4d6, keep highest 3 (default)
                "3d6" - Roll 3d6 straight
                "2d6+6" - Roll 2d6+6

        Returns:
            List of 6 ability scores
        """
        scores = []
        for _ in range(6):
            roll = self.roll(method)
            scores.append(roll.total)
        return sorted(scores, reverse=True)

    def _parse_notation(self, notation: str) -> Optional[Tuple[int, int, int, Optional[str], Optional[int]]]:
        """
        Parse dice notation

        Returns:
            (num_dice, dice_type, modifier, keep_mode, keep_count)
            or None if invalid

        Examples:
            "2d6+3" → (2, 6, 3, None, None)
            "1d20" → (1, 20, 0, None, None)
            "4d6kh3" → (4, 6, 0, "kh", 3)
            "3d8-2" → (3, 8, -2, None, None)
        """
        # Clean notation
        notation = notation.strip().lower().replace(" ", "")

        # Pattern: XdY[kh/kl Z][+/-modifier]
        pattern = r'^(\d+)d(\d+)(?:(kh|kl)(\d+))?([+-]\d+)?$'
        match = re.match(pattern, notation)

        if not match:
            return None

        num_dice = int(match.group(1))
        dice_type = int(match.group(2))
        keep_mode = match.group(3)  # "kh" or "kl" or None
        keep_count = int(match.group(4)) if match.group(4) else None
        modifier = int(match.group(5)) if match.group(5) else 0

        return (num_dice, dice_type, modifier, keep_mode, keep_count)


# Global dice roller instance
dice = DiceRoller()


# Convenience functions
def roll(notation: str, advantage: bool = False, disadvantage: bool = False) -> DiceRoll:
    """Roll dice - convenience function"""
    return dice.roll(notation, advantage=advantage, disadvantage=disadvantage)


def d20(modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> DiceRoll:
    """Roll d20 - convenience function"""
    notation = f"1d20+{modifier}" if modifier >= 0 else f"1d20{modifier}"
    return dice.roll(notation, advantage=advantage, disadvantage=disadvantage)


def d6(num: int = 1, modifier: int = 0) -> DiceRoll:
    """Roll d6 - convenience function"""
    notation = f"{num}d6"
    if modifier != 0:
        notation += f"+{modifier}" if modifier > 0 else f"{modifier}"
    return dice.roll(notation)


def d4(num: int = 1, modifier: int = 0) -> DiceRoll:
    """Roll d4 - convenience function"""
    notation = f"{num}d4"
    if modifier != 0:
        notation += f"+{modifier}" if modifier > 0 else f"{modifier}"
    return dice.roll(notation)


def d8(num: int = 1, modifier: int = 0) -> DiceRoll:
    """Roll d8 - convenience function"""
    notation = f"{num}d8"
    if modifier != 0:
        notation += f"+{modifier}" if modifier > 0 else f"{modifier}"
    return dice.roll(notation)


def d10(num: int = 1, modifier: int = 0) -> DiceRoll:
    """Roll d10 - convenience function"""
    notation = f"{num}d10"
    if modifier != 0:
        notation += f"+{modifier}" if modifier > 0 else f"{modifier}"
    return dice.roll(notation)


def d12(num: int = 1, modifier: int = 0) -> DiceRoll:
    """Roll d12 - convenience function"""
    notation = f"{num}d12"
    if modifier != 0:
        notation += f"+{modifier}" if modifier > 0 else f"{modifier}"
    return dice.roll(notation)
