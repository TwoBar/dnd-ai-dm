"""
Formula Parser for D&D 5E

Converts text formulas into computed values:
- "8 + proficiency_bonus + cha_mod" → 12
- "1d8 + con_mod" → Dice notation
- "floor((level - 1) / 4) + 2" → 3

Supports:
- Ability modifiers (str_mod, dex_mod, etc.)
- Character stats (level, proficiency_bonus)
- Dice notation (1d20, 2d6+3)
- Math operations (+, -, *, /, //, %, **)
- Functions (floor, ceil, max, min)
- Parentheses for grouping
"""

import re
import math
from typing import Dict, Any, Union, Optional


class FormulaParser:
    """
    Parses and evaluates D&D formulas

    Usage:
        parser = FormulaParser()
        context = {
            'level': 5,
            'cha': 16,
            'cha_mod': 3,
            'proficiency_bonus': 3
        }

        result = parser.evaluate("8 + proficiency_bonus + cha_mod", context)
        # Returns: 14
    """

    # Standard D&D formulas
    STANDARD_FORMULAS = {
        'proficiency_bonus': 'floor((level - 1) / 4) + 2',
        'spell_save_dc': '8 + proficiency_bonus + spellcasting_ability_mod',
        'spell_attack_bonus': 'proficiency_bonus + spellcasting_ability_mod',
        'initiative': 'dex_mod',
        'passive_perception': '10 + perception_bonus',
    }

    def __init__(self):
        """Initialize formula parser"""
        self.dice_pattern = re.compile(r'(\d+)d(\d+)(?:kh(\d+))?(?:kl(\d+))?')

    def evaluate(self, formula: str, context: Dict[str, Any]) -> Union[int, str]:
        """
        Evaluate a formula with given context

        Args:
            formula: Text formula to evaluate
            context: Dictionary of variable values

        Returns:
            Computed value (int) or dice notation (str) if formula contains dice

        Examples:
            evaluate("8 + proficiency_bonus + cha_mod", {'proficiency_bonus': 3, 'cha_mod': 2})
            # Returns: 13

            evaluate("1d8 + con_mod", {'con_mod': 2})
            # Returns: "1d8+2" (dice notation for later rolling)
        """
        if not formula:
            return 0

        # Check if formula contains dice notation
        if 'd' in formula and self.dice_pattern.search(formula):
            return self._process_dice_formula(formula, context)

        # Otherwise, evaluate as math expression
        return self._evaluate_math(formula, context)

    def _process_dice_formula(self, formula: str, context: Dict[str, Any]) -> str:
        """
        Process formula containing dice notation

        Args:
            formula: Formula with dice (e.g., "1d8 + con_mod")
            context: Variable values

        Returns:
            Processed dice notation (e.g., "1d8+2")
        """
        # Replace variables with their values (use word boundaries)
        processed = formula
        for var, value in context.items():
            # Use regex with word boundaries to avoid partial matches
            processed = re.sub(r'\b' + re.escape(var) + r'\b', str(value), processed)

        # Simplify: "1d8 + 2" → "1d8+2"
        processed = processed.replace(' ', '')

        return processed

    def _evaluate_math(self, formula: str, context: Dict[str, Any]) -> int:
        """
        Evaluate mathematical expression

        Args:
            formula: Math formula (e.g., "8 + proficiency_bonus + cha_mod")
            context: Variable values

        Returns:
            Computed integer value
        """
        # Expand standard formulas recursively
        expanded = self._expand_formula(formula, context)

        # Replace variables with values
        expression = expanded
        for var, value in context.items():
            # Use word boundaries to avoid partial matches
            expression = re.sub(r'\b' + re.escape(var) + r'\b', str(value), expression)

        # Add safe functions
        safe_dict = {
            'floor': math.floor,
            'ceil': math.ceil,
            'max': max,
            'min': min,
            'abs': abs,
            'round': round,
        }

        try:
            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            return int(result)
        except Exception as e:
            raise ValueError(f"Failed to evaluate formula '{formula}': {e}")

    def _expand_formula(self, formula: str, context: Dict[str, Any], depth: int = 0) -> str:
        """
        Recursively expand standard formulas

        Args:
            formula: Formula possibly containing standard formula names
            context: Variable values
            depth: Recursion depth (prevent infinite loops)

        Returns:
            Expanded formula
        """
        if depth > 10:
            raise ValueError("Formula expansion depth exceeded (circular reference?)")

        expanded = formula
        for name, definition in self.STANDARD_FORMULAS.items():
            if name in expanded:
                # Recursively expand the definition
                expanded_def = self._expand_formula(definition, context, depth + 1)
                expanded = expanded.replace(name, f"({expanded_def})")

        return expanded

    def get_ability_modifier(self, ability_score: int) -> int:
        """
        Calculate ability modifier from ability score

        Args:
            ability_score: Ability score (1-30)

        Returns:
            Ability modifier

        Examples:
            get_ability_modifier(10) → 0
            get_ability_modifier(16) → 3
            get_ability_modifier(8) → -1
        """
        return math.floor((ability_score - 10) / 2)

    def compute_all_modifiers(self, ability_scores: Dict[str, int]) -> Dict[str, int]:
        """
        Compute all ability modifiers from ability scores

        Args:
            ability_scores: Dictionary like {'str': 10, 'dex': 14, 'con': 12, ...}

        Returns:
            Dictionary like {'str_mod': 0, 'dex_mod': 2, 'con_mod': 1, ...}
        """
        modifiers = {}
        for ability, score in ability_scores.items():
            modifiers[f"{ability}_mod"] = self.get_ability_modifier(score)
        return modifiers

    def build_context(self, creature_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build evaluation context from creature data

        Args:
            creature_data: Dictionary containing creature properties

        Returns:
            Context dictionary for formula evaluation

        Example:
            creature_data = {
                'str': 10, 'dex': 14, 'con': 12,
                'int': 13, 'wis': 8, 'cha': 15,
                'level': 5,
                'spellcasting_ability': 'cha'
            }

            context = build_context(creature_data)
            # Returns: {
            #   'str': 10, 'str_mod': 0,
            #   'dex': 14, 'dex_mod': 2,
            #   ...
            #   'level': 5,
            #   'proficiency_bonus': 3,
            #   'spellcasting_ability_mod': 3,
            #   ...
            # }
        """
        context = {}

        # Copy raw stats
        for key in ['str', 'dex', 'con', 'int', 'wis', 'cha', 'level']:
            if key in creature_data:
                context[key] = creature_data[key]

        # Compute ability modifiers
        ability_scores = {
            key: creature_data.get(key, 10)
            for key in ['str', 'dex', 'con', 'int', 'wis', 'cha']
        }
        modifiers = self.compute_all_modifiers(ability_scores)
        context.update(modifiers)

        # Compute proficiency bonus
        if 'level' in creature_data:
            context['proficiency_bonus'] = math.floor((creature_data['level'] - 1) / 4) + 2

        # Compute spellcasting ability modifier
        if 'spellcasting_ability' in creature_data:
            ability = creature_data['spellcasting_ability']
            context['spellcasting_ability_mod'] = modifiers.get(f"{ability}_mod", 0)

        # Add any custom variables
        for key, value in creature_data.items():
            if key not in context and isinstance(value, (int, float)):
                context[key] = value

        return context


# Example usage and tests
if __name__ == "__main__":
    parser = FormulaParser()

    # Test character: Level 5 Bard
    joe_data = {
        'str': 10,
        'dex': 14,
        'con': 12,
        'int': 13,
        'wis': 8,
        'cha': 15,
        'level': 5,
        'spellcasting_ability': 'cha'
    }

    context = parser.build_context(joe_data)

    print("Test Character: Joe Flutello (Level 5 Bard)")
    print("=" * 50)
    print(f"Ability Scores: STR {joe_data['str']} DEX {joe_data['dex']} CON {joe_data['con']}")
    print(f"                INT {joe_data['int']} WIS {joe_data['wis']} CHA {joe_data['cha']}")
    print()

    # Test formulas
    test_formulas = [
        ("Proficiency Bonus", "proficiency_bonus", None),
        ("Max HP (d8 hit die)", "8 + con_mod", None),
        ("Spell Save DC", "8 + proficiency_bonus + cha_mod", None),
        ("Spell Attack Bonus", "proficiency_bonus + cha_mod", None),
        ("Initiative", "dex_mod", None),
        ("AC (leather + dex)", "11 + dex_mod", None),
        ("Healing Word (dice)", "1d4 + cha_mod", None),
    ]

    print("Computed Values:")
    print("-" * 50)
    for name, formula, _ in test_formulas:
        try:
            result = parser.evaluate(formula, context)
            print(f"{name:25} = {result:>5}  (formula: {formula})")
        except Exception as e:
            print(f"{name:25} = ERROR: {e}")

    print()
    print("Context Variables:")
    print("-" * 50)
    for key, value in sorted(context.items()):
        print(f"  {key:30} = {value}")
