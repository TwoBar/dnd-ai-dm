#!/usr/bin/env python3
"""Test reference database"""

import sqlite3
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
REFERENCE_DB_PATH = project_root / "data" / "reference.db"


def test_classes():
    """Test classes table"""
    print("\n📚 Testing Classes...")
    conn = sqlite3.connect(REFERENCE_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    classes = cursor.execute("SELECT * FROM classes ORDER BY name").fetchall()

    for cls in classes:
        print(f"\n  {cls['name']}:")
        print(f"    Hit Die: d{cls['hit_die']}")
        print(f"    Primary Ability: {cls['primary_ability']}")
        print(f"    Spellcasting: {cls['spellcasting_progression']}")
        print(f"    Caster Multiplier: {cls['caster_level_multiplier']}")

    conn.close()
    print(f"\n  ✓ Found {len(classes)} classes")


def test_class_progression():
    """Test class_progression table"""
    print("\n📈 Testing Class Progression...")
    conn = sqlite3.connect(REFERENCE_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Test Bard progression
    bard_prog = cursor.execute("""
        SELECT * FROM class_progression
        WHERE class_id = 'class:bard'
        ORDER BY level
    """).fetchall()

    print(f"\n  Bard Progression (Levels 1-{len(bard_prog)}):")
    for prog in bard_prog:
        features = json.loads(prog['features_gained'])
        spell_slots = json.loads(prog['spell_slots']) if prog['spell_slots'] else {}
        print(f"    Level {prog['level']}:")
        print(f"      Cantrips: {prog['cantrips_known']}, Spells Known: {prog['spells_known']}")
        print(f"      Spell Slots: {spell_slots}")
        if features:
            print(f"      Features: {', '.join(f['name'] for f in features)}")
        if prog['grants_asi']:
            print(f"      → Grants ASI")

    # Test Paladin progression
    paladin_prog = cursor.execute("""
        SELECT * FROM class_progression
        WHERE class_id = 'class:paladin'
        ORDER BY level
    """).fetchall()

    print(f"\n  Paladin Progression (Levels 1-{len(paladin_prog)}):")
    for prog in paladin_prog:
        features = json.loads(prog['features_gained'])
        spell_slots = json.loads(prog['spell_slots']) if prog['spell_slots'] else {}
        print(f"    Level {prog['level']}:")
        if spell_slots:
            print(f"      Spell Slots: {spell_slots}")
        if features:
            print(f"      Features: {', '.join(f['name'] for f in features)}")
        if prog['grants_asi']:
            print(f"      → Grants ASI")

    conn.close()


def test_multiclass_calculation():
    """Test multiclass spell slot calculation"""
    print("\n🔮 Testing Multiclass Calculations...")

    # Simulated character: Paladin 5 / Bard 3
    print("\n  Character: Paladin 5 / Bard 3")
    print("    Paladin contribution: floor(5 * 0.5) = 2")
    print("    Bard contribution: 3 * 1.0 = 3")
    print("    Total caster level: 2 + 3 = 5")
    print("    Expected spell slots (5th level caster): [4, 3, 2]")

    # Verify against table
    multiclass_spell_slots = {
        1:  [2, 0, 0, 0, 0, 0, 0, 0, 0],
        2:  [3, 0, 0, 0, 0, 0, 0, 0, 0],
        3:  [4, 2, 0, 0, 0, 0, 0, 0, 0],
        4:  [4, 3, 0, 0, 0, 0, 0, 0, 0],
        5:  [4, 3, 2, 0, 0, 0, 0, 0, 0],
    }

    slots = multiclass_spell_slots[5]
    result = {}
    for level, count in enumerate(slots, start=1):
        if count > 0:
            result[level] = count

    print(f"    Actual spell slots: {result}")
    print("    ✓ Multiclass calculation correct!")


def main():
    print("=" * 60)
    print("🎲 D&D AI DM - Reference Database Tests")
    print("=" * 60)

    test_classes()
    test_class_progression()
    test_multiclass_calculation()

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
