#!/usr/bin/env python3
"""
Bootstrap Reference Database

Creates reference.db and populates it with D&D 5E SRD content:
- Classes (Bard, Paladin, Fighter, Wizard)
- Class progression (levels 1-20)
- Races (Human, Elf, Tiefling)
- Backgrounds (Charlatan, Soldier)
- Spells (migrate from old entities table or create basic set)
- Items (weapons, armor, basic gear)
- Conditions, skills, damage types
"""

import sqlite3
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Paths
SCHEMA_PATH = project_root / "data" / "schemas" / "reference_db.sql"
REFERENCE_DB_PATH = project_root / "data" / "reference.db"
OLD_REFERENCE_DB_PATH = project_root / "data" / "dnd_reference.db"


def create_database():
    """Create reference.db from schema"""
    print("📦 Creating reference.db...")

    # Remove existing if present
    if REFERENCE_DB_PATH.exists():
        backup_path = REFERENCE_DB_PATH.with_suffix('.db.backup')
        print(f"   Backing up existing database to {backup_path}")
        REFERENCE_DB_PATH.rename(backup_path)

    # Execute schema
    conn = sqlite3.connect(REFERENCE_DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()
        conn.executescript(schema_sql)
    conn.commit()

    print("   ✓ Database created")
    return conn


def populate_classes(conn):
    """Populate classes table with core D&D 5E classes"""
    print("\n📚 Populating classes...")

    classes_data = [
        # Bard - Full caster
        {
            'id': 'class:bard',
            'name': 'Bard',
            'hit_die': 8,
            'primary_ability': 'cha',
            'saving_throw_proficiencies': json.dumps(['dex', 'cha']),
            'armor_proficiencies': json.dumps(['light']),
            'weapon_proficiencies': json.dumps(['simple', 'hand-crossbow', 'longsword', 'rapier', 'shortsword']),
            'skill_proficiencies': json.dumps({'choose': 3, 'from': ['acrobatics', 'animal-handling', 'arcana', 'athletics', 'deception', 'history', 'insight', 'intimidation', 'investigation', 'medicine', 'nature', 'perception', 'performance', 'persuasion', 'religion', 'sleight-of-hand', 'stealth', 'survival']}),
            'tool_proficiencies': json.dumps({'choose': 3, 'from': ['any-musical-instrument']}),
            'is_spellcaster': 1,
            'spellcasting_ability': 'cha',
            'spell_slots_by_level': json.dumps({}),  # Will be in class_progression
            'cantrips_known_by_level': json.dumps({}),
            'spells_known_by_level': json.dumps({}),
            'ritual_casting': 1,
            'spellcasting_type': 'known',
            'spellcasting_progression': 'full',
            'caster_level_multiplier': 1.0,
            'starting_equipment': json.dumps([]),
            'starting_wealth_dice': '5d4 x 10',
            'class_resource_template': json.dumps({'bardic_inspiration': {'die_progression': {'1': 'd6', '5': 'd8', '10': 'd10', '15': 'd12'}, 'uses': 'cha_mod'}}),
            'multiclass_prerequisites': json.dumps({'cha': 13}),
            'multiclass_proficiencies': json.dumps({'armor': ['light'], 'weapons': [], 'skills': {'choose': 1, 'from': ['any']}}),
            'source_book': "Player's Handbook",
            'page': 51,
            'srd': 1
        },

        # Paladin - Half caster
        {
            'id': 'class:paladin',
            'name': 'Paladin',
            'hit_die': 10,
            'primary_ability': 'str',
            'saving_throw_proficiencies': json.dumps(['wis', 'cha']),
            'armor_proficiencies': json.dumps(['light', 'medium', 'heavy', 'shields']),
            'weapon_proficiencies': json.dumps(['simple', 'martial']),
            'skill_proficiencies': json.dumps({'choose': 2, 'from': ['athletics', 'insight', 'intimidation', 'medicine', 'persuasion', 'religion']}),
            'tool_proficiencies': json.dumps({}),
            'is_spellcaster': 1,
            'spellcasting_ability': 'cha',
            'spell_slots_by_level': json.dumps({}),
            'cantrips_known_by_level': json.dumps({}),
            'spells_known_by_level': json.dumps({}),
            'ritual_casting': 0,
            'spellcasting_type': 'prepared',
            'spellcasting_progression': 'half',
            'caster_level_multiplier': 0.5,
            'starting_equipment': json.dumps([]),
            'starting_wealth_dice': '5d4 x 10',
            'class_resource_template': json.dumps({'lay_on_hands_pool': 'level * 5', 'divine_sense': '1 + cha_mod'}),
            'multiclass_prerequisites': json.dumps({'str': 13, 'cha': 13}),
            'multiclass_proficiencies': json.dumps({'armor': ['light', 'medium', 'shields'], 'weapons': ['simple', 'martial'], 'skills': {}}),
            'source_book': "Player's Handbook",
            'page': 82,
            'srd': 1
        },

        # Fighter - Non-caster
        {
            'id': 'class:fighter',
            'name': 'Fighter',
            'hit_die': 10,
            'primary_ability': 'str',
            'saving_throw_proficiencies': json.dumps(['str', 'con']),
            'armor_proficiencies': json.dumps(['light', 'medium', 'heavy', 'shields']),
            'weapon_proficiencies': json.dumps(['simple', 'martial']),
            'skill_proficiencies': json.dumps({'choose': 2, 'from': ['acrobatics', 'animal-handling', 'athletics', 'history', 'insight', 'intimidation', 'perception', 'survival']}),
            'tool_proficiencies': json.dumps({}),
            'is_spellcaster': 0,
            'spellcasting_ability': None,
            'spell_slots_by_level': json.dumps({}),
            'cantrips_known_by_level': json.dumps({}),
            'spells_known_by_level': json.dumps({}),
            'ritual_casting': 0,
            'spellcasting_type': 'none',
            'spellcasting_progression': 'none',
            'caster_level_multiplier': 0.0,
            'starting_equipment': json.dumps([]),
            'starting_wealth_dice': '5d4 x 10',
            'class_resource_template': json.dumps({'second_wind': 1, 'action_surge': 1}),
            'multiclass_prerequisites': json.dumps({'str': 13}),
            'multiclass_proficiencies': json.dumps({'armor': ['light', 'medium', 'heavy', 'shields'], 'weapons': ['simple', 'martial'], 'skills': {}}),
            'source_book': "Player's Handbook",
            'page': 70,
            'srd': 1
        },

        # Wizard - Full caster
        {
            'id': 'class:wizard',
            'name': 'Wizard',
            'hit_die': 6,
            'primary_ability': 'int',
            'saving_throw_proficiencies': json.dumps(['int', 'wis']),
            'armor_proficiencies': json.dumps([]),
            'weapon_proficiencies': json.dumps(['dagger', 'dart', 'sling', 'quarterstaff', 'light-crossbow']),
            'skill_proficiencies': json.dumps({'choose': 2, 'from': ['arcana', 'history', 'insight', 'investigation', 'medicine', 'religion']}),
            'tool_proficiencies': json.dumps({}),
            'is_spellcaster': 1,
            'spellcasting_ability': 'int',
            'spell_slots_by_level': json.dumps({}),
            'cantrips_known_by_level': json.dumps({}),
            'spells_known_by_level': json.dumps({}),
            'ritual_casting': 1,
            'spellcasting_type': 'prepared',
            'spellcasting_progression': 'full',
            'caster_level_multiplier': 1.0,
            'starting_equipment': json.dumps([]),
            'starting_wealth_dice': '4d4 x 10',
            'class_resource_template': json.dumps({'arcane_recovery': 'once per day'}),
            'multiclass_prerequisites': json.dumps({'int': 13}),
            'multiclass_proficiencies': json.dumps({'armor': [], 'weapons': [], 'skills': {}}),
            'source_book': "Player's Handbook",
            'page': 112,
            'srd': 1
        },

        # Warlock - Pact Magic (special case)
        {
            'id': 'class:warlock',
            'name': 'Warlock',
            'hit_die': 8,
            'primary_ability': 'cha',
            'saving_throw_proficiencies': json.dumps(['wis', 'cha']),
            'armor_proficiencies': json.dumps(['light']),
            'weapon_proficiencies': json.dumps(['simple']),
            'skill_proficiencies': json.dumps({'choose': 2, 'from': ['arcana', 'deception', 'history', 'intimidation', 'investigation', 'nature', 'religion']}),
            'tool_proficiencies': json.dumps({}),
            'is_spellcaster': 1,
            'spellcasting_ability': 'cha',
            'spell_slots_by_level': json.dumps({}),
            'cantrips_known_by_level': json.dumps({}),
            'spells_known_by_level': json.dumps({}),
            'ritual_casting': 0,
            'spellcasting_type': 'known',
            'spellcasting_progression': 'pact-magic',  # Special!
            'caster_level_multiplier': 0.0,  # Doesn't contribute to multiclass spell slots
            'starting_equipment': json.dumps([]),
            'starting_wealth_dice': '4d4 x 10',
            'class_resource_template': json.dumps({'eldritch_invocations': 'by_level'}),
            'multiclass_prerequisites': json.dumps({'cha': 13}),
            'multiclass_proficiencies': json.dumps({'armor': ['light'], 'weapons': ['simple'], 'skills': {'choose': 1, 'from': ['arcana', 'deception', 'history', 'intimidation', 'investigation', 'nature', 'religion']}}),
            'source_book': "Player's Handbook",
            'page': 105,
            'srd': 1
        }
    ]

    cursor = conn.cursor()
    for class_data in classes_data:
        cursor.execute("""
            INSERT INTO classes (
                id, name, hit_die, primary_ability,
                saving_throw_proficiencies, armor_proficiencies, weapon_proficiencies,
                skill_proficiencies, tool_proficiencies,
                is_spellcaster, spellcasting_ability, spell_slots_by_level,
                cantrips_known_by_level, spells_known_by_level, ritual_casting, spellcasting_type,
                spellcasting_progression, caster_level_multiplier,
                starting_equipment, starting_wealth_dice, class_resource_template,
                multiclass_prerequisites, multiclass_proficiencies,
                source_book, page, srd
            ) VALUES (
                :id, :name, :hit_die, :primary_ability,
                :saving_throw_proficiencies, :armor_proficiencies, :weapon_proficiencies,
                :skill_proficiencies, :tool_proficiencies,
                :is_spellcaster, :spellcasting_ability, :spell_slots_by_level,
                :cantrips_known_by_level, :spells_known_by_level, :ritual_casting, :spellcasting_type,
                :spellcasting_progression, :caster_level_multiplier,
                :starting_equipment, :starting_wealth_dice, :class_resource_template,
                :multiclass_prerequisites, :multiclass_proficiencies,
                :source_book, :page, :srd
            )
        """, class_data)

    conn.commit()
    print(f"   ✓ Added {len(classes_data)} classes")


def populate_class_progression(conn):
    """Populate class_progression table (levels 1-20 for each class)"""
    print("\n📈 Populating class progression...")

    # Bard progression (levels 1-5 for testing)
    bard_progression = [
        {
            'id': 'progression:bard:1',
            'class_id': 'class:bard',
            'level': 1,
            'hit_points_formula': 'hit_die',  # Max at first level
            'features_gained': json.dumps([
                {'id': 'feature:spellcasting', 'name': 'Spellcasting'},
                {'id': 'feature:bardic-inspiration-d6', 'name': 'Bardic Inspiration (d6)'}
            ]),
            'cantrips_known': 2,
            'spells_known': 4,
            'spell_slots': json.dumps({'1': 2}),
            'class_resources': json.dumps({'bardic_inspiration': {'die': 'd6', 'uses': 'cha_mod'}}),
            'grants_asi': 0,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 52
        },
        {
            'id': 'progression:bard:2',
            'class_id': 'class:bard',
            'level': 2,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([
                {'id': 'feature:jack-of-all-trades', 'name': 'Jack of All Trades'},
                {'id': 'feature:song-of-rest-d6', 'name': 'Song of Rest (d6)'}
            ]),
            'cantrips_known': 2,
            'spells_known': 5,
            'spell_slots': json.dumps({'1': 3}),
            'class_resources': json.dumps({'bardic_inspiration': {'die': 'd6', 'uses': 'cha_mod'}}),
            'grants_asi': 0,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 52
        },
        {
            'id': 'progression:bard:3',
            'class_id': 'class:bard',
            'level': 3,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([
                {'id': 'feature:expertise', 'name': 'Expertise'},
                {'id': 'feature:bard-college', 'name': 'Bard College'}
            ]),
            'cantrips_known': 2,
            'spells_known': 6,
            'spell_slots': json.dumps({'1': 4, '2': 2}),
            'class_resources': json.dumps({'bardic_inspiration': {'die': 'd6', 'uses': 'cha_mod'}}),
            'grants_asi': 0,
            'grants_subclass_choice': 1,  # Choose Bard College at 3
            'source_book': "Player's Handbook",
            'page': 54
        },
        {
            'id': 'progression:bard:4',
            'class_id': 'class:bard',
            'level': 4,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([]),
            'cantrips_known': 3,
            'spells_known': 7,
            'spell_slots': json.dumps({'1': 4, '2': 3}),
            'class_resources': json.dumps({'bardic_inspiration': {'die': 'd6', 'uses': 'cha_mod'}}),
            'grants_asi': 1,  # ASI at level 4
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 54
        },
        {
            'id': 'progression:bard:5',
            'class_id': 'class:bard',
            'level': 5,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([
                {'id': 'feature:font-of-inspiration', 'name': 'Font of Inspiration'}
            ]),
            'cantrips_known': 3,
            'spells_known': 8,
            'spell_slots': json.dumps({'1': 4, '2': 3, '3': 2}),
            'class_resources': json.dumps({'bardic_inspiration': {'die': 'd8', 'uses': 'cha_mod'}}),  # Die increases!
            'grants_asi': 0,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 54
        }
    ]

    # Paladin progression (levels 1-5 for testing)
    paladin_progression = [
        {
            'id': 'progression:paladin:1',
            'class_id': 'class:paladin',
            'level': 1,
            'hit_points_formula': 'hit_die',
            'features_gained': json.dumps([
                {'id': 'feature:divine-sense', 'name': 'Divine Sense'},
                {'id': 'feature:lay-on-hands', 'name': 'Lay on Hands'}
            ]),
            'cantrips_known': 0,
            'spells_known': 0,
            'spell_slots': None,  # No spellcasting yet
            'class_resources': json.dumps({'lay_on_hands_pool': 'level * 5', 'divine_sense': '1 + cha_mod'}),
            'grants_asi': 0,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 84
        },
        {
            'id': 'progression:paladin:2',
            'class_id': 'class:paladin',
            'level': 2,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([
                {'id': 'feature:fighting-style', 'name': 'Fighting Style'},
                {'id': 'feature:spellcasting', 'name': 'Spellcasting'},
                {'id': 'feature:divine-smite', 'name': 'Divine Smite'}
            ]),
            'cantrips_known': 0,
            'spells_known': 2,  # Paladin prepares spells
            'spell_slots': json.dumps({'1': 2}),
            'class_resources': json.dumps({'lay_on_hands_pool': 'level * 5', 'divine_sense': '1 + cha_mod'}),
            'grants_asi': 0,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 84
        },
        {
            'id': 'progression:paladin:3',
            'class_id': 'class:paladin',
            'level': 3,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([
                {'id': 'feature:divine-health', 'name': 'Divine Health'},
                {'id': 'feature:sacred-oath', 'name': 'Sacred Oath'}
            ]),
            'cantrips_known': 0,
            'spells_known': 3,
            'spell_slots': json.dumps({'1': 3}),
            'class_resources': json.dumps({'lay_on_hands_pool': 'level * 5', 'divine_sense': '1 + cha_mod', 'channel_divinity': 1}),
            'grants_asi': 0,
            'grants_subclass_choice': 1,  # Choose Sacred Oath at 3
            'source_book': "Player's Handbook",
            'page': 85
        },
        {
            'id': 'progression:paladin:4',
            'class_id': 'class:paladin',
            'level': 4,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([]),
            'cantrips_known': 0,
            'spells_known': 3,
            'spell_slots': json.dumps({'1': 3}),
            'class_resources': json.dumps({'lay_on_hands_pool': 'level * 5', 'divine_sense': '1 + cha_mod', 'channel_divinity': 1}),
            'grants_asi': 1,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 85
        },
        {
            'id': 'progression:paladin:5',
            'class_id': 'class:paladin',
            'level': 5,
            'hit_points_formula': 'hit_die + con_mod',
            'features_gained': json.dumps([
                {'id': 'feature:extra-attack', 'name': 'Extra Attack'}
            ]),
            'cantrips_known': 0,
            'spells_known': 4,
            'spell_slots': json.dumps({'1': 4, '2': 2}),
            'class_resources': json.dumps({'lay_on_hands_pool': 'level * 5', 'divine_sense': '1 + cha_mod', 'channel_divinity': 1}),
            'grants_asi': 0,
            'grants_subclass_choice': 0,
            'source_book': "Player's Handbook",
            'page': 85
        }
    ]

    all_progression = bard_progression + paladin_progression

    cursor = conn.cursor()
    for prog in all_progression:
        cursor.execute("""
            INSERT INTO class_progression (
                id, class_id, level, hit_points_formula,
                features_gained, cantrips_known, spells_known, spell_slots,
                class_resources, grants_asi, grants_subclass_choice,
                source_book, page
            ) VALUES (
                :id, :class_id, :level, :hit_points_formula,
                :features_gained, :cantrips_known, :spells_known, :spell_slots,
                :class_resources, :grants_asi, :grants_subclass_choice,
                :source_book, :page
            )
        """, prog)

    conn.commit()
    print(f"   ✓ Added {len(all_progression)} progression entries")


def main():
    """Main bootstrap function"""
    print("=" * 60)
    print("🎲 D&D AI DM - Reference Database Bootstrap")
    print("=" * 60)

    conn = create_database()
    populate_classes(conn)
    populate_class_progression(conn)

    # TODO: Add more data in subsequent scripts
    # - populate_races()
    # - populate_backgrounds()
    # - populate_spells()
    # - populate_items()
    # - populate_conditions()
    # - populate_skills()

    conn.close()

    print("\n" + "=" * 60)
    print("✅ Reference database bootstrap complete!")
    print(f"📍 Database location: {REFERENCE_DB_PATH}")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run this script to test: python scripts/test_reference_db.py")
    print("  2. Add more classes (Fighter, Wizard, Warlock)")
    print("  3. Add races, backgrounds, spells, items")


if __name__ == '__main__':
    main()
