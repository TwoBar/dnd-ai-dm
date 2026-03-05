#!/usr/bin/env python3
"""Test Multiclass Calculator"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.game.multiclass_calculator import MulticlassCalculator

REFERENCE_DB_PATH = project_root / "data" / "reference.db"


def test_proficiency_bonus():
    """Test proficiency bonus calculation"""
    print("\n📊 Testing Proficiency Bonus...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    tests = [
        (1, 2), (4, 2), (5, 3), (8, 3),
        (9, 4), (12, 4), (13, 5), (16, 5),
        (17, 6), (20, 6)
    ]

    for level, expected in tests:
        result = calc.calculate_proficiency_bonus(level)
        status = "✓" if result == expected else "✗"
        print(f"  {status} Level {level}: {result} (expected {expected})")


def test_pact_magic():
    """Test Warlock Pact Magic"""
    print("\n🔮 Testing Pact Magic (Warlock)...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    tests = [
        (1, {"count": 1, "level": 1, "used": 0}),
        (3, {"count": 2, "level": 2, "used": 0}),
        (5, {"count": 2, "level": 3, "used": 0}),
        (11, {"count": 3, "level": 5, "used": 0}),
        (17, {"count": 4, "level": 5, "used": 0}),
    ]

    for warlock_level, expected in tests:
        result = calc.calculate_pact_magic_slots(warlock_level)
        status = "✓" if result == expected else "✗"
        print(f"  {status} Warlock {warlock_level}: {result}")


def test_multiclass_spell_slots():
    """Test multiclass spell slot calculation"""
    print("\n✨ Testing Multiclass Spell Slots...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    # Test case 1: Paladin 5 / Bard 3
    print("\n  Character: Paladin 5 / Bard 3")
    class_levels = {'class:paladin': 5, 'class:bard': 3}
    slots = calc.calculate_multiclass_spell_slots(class_levels)
    print(f"    Paladin contribution: floor(5 × 0.5) = 2")
    print(f"    Bard contribution: 3 × 1.0 = 3")
    print(f"    Total caster level: 2 + 3 = 5")
    print(f"    Spell slots: {slots}")
    expected = {1: 4, 2: 3, 3: 2}
    status = "✓" if slots == expected else "✗"
    print(f"    {status} Expected: {expected}")

    # Test case 2: Wizard 11 (pure caster)
    print("\n  Character: Wizard 11")
    class_levels = {'class:wizard': 11}
    slots = calc.calculate_multiclass_spell_slots(class_levels)
    print(f"    Wizard contribution: 11 × 1.0 = 11")
    print(f"    Spell slots: {slots}")
    expected = {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1}
    status = "✓" if slots == expected else "✗"
    print(f"    {status} Expected: {expected}")

    # Test case 3: Fighter 8 / Wizard 3 (Eldritch Knight)
    print("\n  Character: Fighter 8 (Eldritch Knight) / Wizard 3")
    class_levels = {'class:fighter': 8, 'class:wizard': 3}
    slots = calc.calculate_multiclass_spell_slots(class_levels)
    print(f"    Fighter contribution: floor(8 × 0.33) = 2")
    print(f"    Wizard contribution: 3 × 1.0 = 3")
    print(f"    Total caster level: 2 + 3 = 5")
    print(f"    Spell slots: {slots}")
    expected = {1: 4, 2: 3, 3: 2}
    status = "✓" if slots == expected else "✗"
    print(f"    {status} Expected: {expected}")


def test_extra_attack():
    """Test Extra Attack stacking"""
    print("\n⚔️  Testing Extra Attack...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    tests = [
        ({'class:fighter': 4}, 1, "Fighter 4 (no Extra Attack yet)"),
        ({'class:fighter': 5}, 2, "Fighter 5 (Extra Attack)"),
        ({'class:fighter': 11}, 3, "Fighter 11 (Extra Attack 2)"),
        ({'class:fighter': 20}, 4, "Fighter 20 (Extra Attack 3)"),
        ({'class:barbarian': 5}, 2, "Barbarian 5 (Extra Attack)"),
        ({'class:fighter': 5, 'class:barbarian': 5}, 2, "Fighter 5 / Barbarian 5 (doesn't stack)"),
        ({'class:fighter': 11, 'class:barbarian': 5}, 3, "Fighter 11 / Barbarian 5 (Fighter takes precedence)"),
    ]

    for class_levels, expected, description in tests:
        result = calc.calculate_extra_attack(class_levels)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {description}: {result} attacks")


def test_channel_divinity():
    """Test Channel Divinity uses"""
    print("\n🙏 Testing Channel Divinity...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    tests = [
        ({'class:cleric': 2}, 1, "Cleric 2"),
        ({'class:cleric': 6}, 2, "Cleric 6"),
        ({'class:cleric': 18}, 3, "Cleric 18"),
        ({'class:paladin': 3}, 1, "Paladin 3"),
        ({'class:cleric': 6, 'class:paladin': 3}, 3, "Cleric 6 / Paladin 3 (stacks!)"),
    ]

    for class_levels, expected_uses, description in tests:
        result = calc.calculate_channel_divinity(class_levels)
        status = "✓" if result['uses'] == expected_uses else "✗"
        print(f"  {status} {description}: {result['uses']} uses")


def test_unarmored_defense():
    """Test Unarmored Defense conflicts"""
    print("\n🛡️  Testing Unarmored Defense...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    tests = [
        (False, False, None, 'none', "No Barbarian or Monk"),
        (True, False, None, 'barbarian', "Barbarian only"),
        (False, True, None, 'monk', "Monk only"),
        (True, True, 'barbarian', 'barbarian', "Barbarian + Monk, choose Barbarian"),
        (True, True, 'monk', 'monk', "Barbarian + Monk, choose Monk"),
    ]

    for has_barb, has_monk, choice, expected, description in tests:
        try:
            result = calc.resolve_unarmored_defense(has_barb, has_monk, choice)
            status = "✓" if result == expected else "✗"
            print(f"  {status} {description}: {result}")
        except ValueError as e:
            print(f"  ✗ {description}: ERROR - {e}")

    # Test error case
    try:
        calc.resolve_unarmored_defense(True, True, None)
        print(f"  ✗ Barbarian + Monk, no choice: Should raise ValueError")
    except ValueError:
        print(f"  ✓ Barbarian + Monk, no choice: Correctly raises ValueError")


def test_prerequisites():
    """Test multiclass prerequisites"""
    print("\n📋 Testing Multiclass Prerequisites...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    ability_scores = {
        'str': 15, 'dex': 10, 'con': 14,
        'int': 8, 'wis': 12, 'cha': 13
    }

    tests = [
        ('class:paladin', True, "Paladin (needs STR 13, CHA 13)"),
        ('class:bard', True, "Bard (needs CHA 13)"),
        ('class:wizard', False, "Wizard (needs INT 13, has 8)"),
        ('class:fighter', True, "Fighter (needs STR 13 OR DEX 13, has STR 15)"),
        ('class:monk', False, "Monk (needs DEX 13 AND WIS 13, has DEX 10)"),
    ]

    for class_id, should_pass, description in tests:
        meets, message = calc.check_multiclass_prerequisites(class_id, ability_scores)
        status = "✓" if meets == should_pass else "✗"
        print(f"  {status} {description}: {message}")


def test_spellcasting_abilities():
    """Test spellcasting ability tracking"""
    print("\n🎓 Testing Spellcasting Abilities...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    class_levels = {'class:bard': 3, 'class:paladin': 5, 'class:wizard': 2}
    abilities = calc.get_spellcasting_abilities(class_levels)

    print(f"  Character: Bard 3 / Paladin 5 / Wizard 2")
    print(f"  Spellcasting abilities: {abilities}")

    expected = {'class:bard': 'cha', 'class:paladin': 'cha', 'class:wizard': 'int'}
    status = "✓" if abilities == expected else "✗"
    print(f"  {status} Expected: {expected}")


def test_prepared_spells():
    """Test prepared spell calculation"""
    print("\n📖 Testing Prepared Spells...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    tests = [
        ('class:cleric', 5, 3, 8, "Cleric 5, WIS +3"),
        ('class:wizard', 10, 4, 14, "Wizard 10, INT +4"),
        ('class:paladin', 3, 2, 5, "Paladin 3, CHA +2"),
        ('class:bard', 5, 3, None, "Bard (known caster, doesn't prepare)"),
    ]

    for class_id, class_level, ability_mod, expected, description in tests:
        result = calc.calculate_prepared_spells(class_id, class_level, ability_mod)
        if expected is None:
            status = "✓" if result is None else "✗"
            print(f"  {status} {description}: {result}")
        else:
            status = "✓" if result == expected else "✗"
            print(f"  {status} {description}: {result} spells")


def test_fighting_style():
    """Test Fighting Style duplicate checking"""
    print("\n🗡️  Testing Fighting Style Duplicates...")
    calc = MulticlassCalculator(str(REFERENCE_DB_PATH))

    existing = ['Defense', 'Dueling']

    tests = [
        ('Archery', True, "Archery (new style)"),
        ('Defense', False, "Defense (already have it)"),
        ('Great Weapon Fighting', True, "Great Weapon Fighting (new style)"),
        ('Dueling', False, "Dueling (already have it)"),
    ]

    for new_style, should_allow, description in tests:
        result = calc.check_fighting_style_duplicate(existing, new_style)
        status = "✓" if result == should_allow else "✗"
        allowed = "allowed" if result else "duplicate (not allowed)"
        print(f"  {status} {description}: {allowed}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("🎲 D&D AI DM - Multiclass Calculator Tests")
    print("=" * 60)

    test_proficiency_bonus()
    test_pact_magic()
    test_multiclass_spell_slots()
    test_extra_attack()
    test_channel_divinity()
    test_unarmored_defense()
    test_prerequisites()
    test_spellcasting_abilities()
    test_prepared_spells()
    test_fighting_style()

    print("\n" + "=" * 60)
    print("✅ All multiclass tests complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
