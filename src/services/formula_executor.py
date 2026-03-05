"""
Formula Executor - Pure computation engine

Handles:
- Formula evaluation with context
- Modifier application (flat, dice, advantage/disadvantage, multipliers)
- Dice notation processing
- NO database access (pure computation)

Separation of concerns:
- FormulaService: Business logic, database, entity coordination
- FormulaExecutor: Pure computation
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from parsers.formula_parser import FormulaParser
from entities.entity import Modifier

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of formula execution with modifiers applied"""
    value: Any              # Final computed value
    base_value: Any         # Value before modifiers
    modifiers_applied: List[Modifier]
    has_advantage: bool = False
    has_disadvantage: bool = False
    breakdown: str = ""     # Human-readable breakdown


class FormulaExecutor:
    """
    Pure computation - applies modifiers to base formulas.

    No business logic, no database access.
    Just math and modifier application.

    Usage:
        executor = FormulaExecutor(parser)
        result = executor.execute(
            formula="8 + proficiency_bonus + cha_mod",
            context={'proficiency_bonus': 3, 'cha_mod': 3},
            modifiers=[Modifier(type='flat', value=2, ...)]
        )
        # result.value = 16 (8 + 3 + 3 + 2)
    """

    def __init__(self, parser: FormulaParser):
        """
        Initialize executor

        Args:
            parser: FormulaParser instance for formula evaluation
        """
        self.parser = parser

    def execute(
        self,
        formula: str,
        entity_context: Dict[str, Any],
        modifiers: List[Modifier]
    ) -> ExecutionResult:
        """
        Execute formula with modifiers applied.

        Args:
            formula: Base formula (e.g., "8 + proficiency_bonus + cha_mod")
            entity_context: Entity stats (ability scores, level, etc.)
            modifiers: List of modifiers to apply

        Returns:
            ExecutionResult with final value and metadata
        """
        # 1. Evaluate base formula
        base_value = self.parser.evaluate(formula, entity_context)

        # Track what was applied
        breakdown_parts = [f"Base: {base_value}"]

        # 2. Apply flat modifiers (simple addition)
        flat_modifiers = [m for m in modifiers if m.type == 'flat']
        flat_bonus = sum(m.value for m in flat_modifiers)

        result_value = base_value
        if isinstance(base_value, (int, float)):
            result_value = base_value + flat_bonus
            if flat_bonus != 0:
                breakdown_parts.append(f"Flat bonuses: {flat_bonus}")
                for m in flat_modifiers:
                    breakdown_parts.append(f"  +{m.value} ({m.source})")
        else:
            # If base is already dice notation, still track
            if flat_bonus != 0:
                breakdown_parts.append(f"Flat bonuses: {flat_bonus}")

        # 3. Append dice modifiers (for dice notation results)
        dice_modifiers = [m for m in modifiers if m.type == 'dice']
        if dice_modifiers:
            breakdown_parts.append(f"Dice modifiers:")
            for m in dice_modifiers:
                breakdown_parts.append(f"  +{m.value} ({m.source})")

            # If result is dice notation, append dice modifiers
            if isinstance(result_value, str) and 'd' in result_value:
                for dice_mod in dice_modifiers:
                    result_value += f"+{dice_mod.value}"
            # If result is int but we have dice modifiers, convert to dice notation
            elif isinstance(result_value, int):
                dice_parts = [str(result_value)] + [m.value for m in dice_modifiers]
                result_value = '+'.join(str(p) for p in dice_parts)

        # 4. Check for advantage/disadvantage
        has_advantage = any(m.type == 'advantage' and m.value for m in modifiers)
        has_disadvantage = any(m.type == 'disadvantage' and m.value for m in modifiers)

        if has_advantage:
            breakdown_parts.append("Advantage granted")
            for m in modifiers:
                if m.type == 'advantage' and m.value:
                    breakdown_parts.append(f"  from {m.source}")

        if has_disadvantage:
            breakdown_parts.append("Disadvantage applied")
            for m in modifiers:
                if m.type == 'disadvantage' and m.value:
                    breakdown_parts.append(f"  from {m.source}")

        # 5. Apply multipliers (last)
        multiplier_mods = [m for m in modifiers if m.type == 'multiplier']
        multiplier = 1.0
        for m in multiplier_mods:
            multiplier *= m.value
            breakdown_parts.append(f"Multiplier: x{m.value} ({m.source})")

        if multiplier != 1.0 and isinstance(result_value, (int, float)):
            result_value = int(result_value * multiplier)

        # Build breakdown string
        breakdown = '\n'.join(breakdown_parts)

        logger.debug(f"Formula execution: {formula} = {result_value}")
        logger.debug(f"Breakdown:\n{breakdown}")

        return ExecutionResult(
            value=result_value,
            base_value=base_value,
            modifiers_applied=modifiers,
            has_advantage=has_advantage,
            has_disadvantage=has_disadvantage,
            breakdown=breakdown
        )

    def execute_simple(self, formula: str, context: Dict[str, Any]) -> Any:
        """
        Execute formula without modifiers (simple evaluation)

        Args:
            formula: Formula to evaluate
            context: Variable context

        Returns:
            Computed value
        """
        return self.parser.evaluate(formula, context)
