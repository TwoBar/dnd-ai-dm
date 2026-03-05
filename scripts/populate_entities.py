#!/usr/bin/env python3
"""
Populate essential D&D 5E entities
- Races (Human, Elf, Tiefling)
- Skills (all 18)
- Conditions (all 15)
- Backgrounds (Charlatan, Soldier)
- Basic spells (for testing Bard character creation)
"""

import sqlite3
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
REFERENCE_DB_PATH = project_root / "data" / "reference.db"


def populate_races(conn):
    """Populate races table"""
    print("\n🧝 Populating races...")

    races_data = [
        {
            'id': 'race:human',
            'name': 'Human',
            'size': 'Medium',
            'base_speed': 30,
            'ability_score_increases': json.dumps({'str': 1, 'dex': 1, 'con': 1, 'int': 1, 'wis': 1, 'cha': 1}),
            'traits': json.dumps([]),
            'skill_proficiencies': json.dumps([]),
            'weapon_proficiencies': json.dumps([]),
            'tool_proficiencies': json.dumps([]),
            'languages': json.dumps(['Common', {'choose': 1, 'from': 'any'}]),
            'has_subraces': 0,
            'source_book': "Player's Handbook",
            'page': 29,
            'srd': 1
        },
        {
            'id': 'race:elf',
            'name': 'Elf',
            'size': 'Medium',
            'base_speed': 30,
            'ability_score_increases': json.dumps({'dex': 2}),
            'traits': json.dumps([
                {'name': 'Darkvision', 'description': 'You can see in dim light within 60 feet as if it were bright light'},
                {'name': 'Keen Senses', 'description': 'Proficiency in Perception'},
                {'name': 'Fey Ancestry', 'description': 'Advantage on saves against being charmed, magic cannot put you to sleep'},
                {'name': 'Trance', 'description': '4 hours of meditation instead of 8 hours sleep'}
            ]),
            'skill_proficiencies': json.dumps(['perception']),
            'weapon_proficiencies': json.dumps([]),
            'tool_proficiencies': json.dumps([]),
            'languages': json.dumps(['Common', 'Elvish']),
            'has_subraces': 1,
            'source_book': "Player's Handbook",
            'page': 21,
            'srd': 1
        },
        {
            'id': 'race:tiefling',
            'name': 'Tiefling',
            'size': 'Medium',
            'base_speed': 30,
            'ability_score_increases': json.dumps({'cha': 2, 'int': 1}),
            'traits': json.dumps([
                {'name': 'Darkvision', 'description': 'You can see in dim light within 60 feet as if it were bright light'},
                {'name': 'Hellish Resistance', 'description': 'Resistance to fire damage'},
                {'name': 'Infernal Legacy', 'description': 'You know Thaumaturgy cantrip. At 3rd level, Hellish Rebuke 1/day. At 5th level, Darkness 1/day.'}
            ]),
            'skill_proficiencies': json.dumps([]),
            'weapon_proficiencies': json.dumps([]),
            'tool_proficiencies': json.dumps([]),
            'languages': json.dumps(['Common', 'Infernal']),
            'has_subraces': 0,
            'source_book': "Player's Handbook",
            'page': 42,
            'srd': 1
        }
    ]

    cursor = conn.cursor()
    for race in races_data:
        cursor.execute("""
            INSERT OR REPLACE INTO races (
                id, name, size, base_speed, ability_score_increases,
                traits, skill_proficiencies, weapon_proficiencies, tool_proficiencies,
                languages, has_subraces, source_book, page, srd
            ) VALUES (
                :id, :name, :size, :base_speed, :ability_score_increases,
                :traits, :skill_proficiencies, :weapon_proficiencies, :tool_proficiencies,
                :languages, :has_subraces, :source_book, :page, :srd
            )
        """, race)

    conn.commit()
    print(f"   ✓ Added {len(races_data)} races")


def populate_backgrounds(conn):
    """Populate backgrounds table"""
    print("\n📜 Populating backgrounds...")

    backgrounds_data = [
        {
            'id': 'background:charlatan',
            'name': 'Charlatan',
            'skill_proficiencies': json.dumps(['deception', 'sleight-of-hand']),
            'tool_proficiencies': json.dumps(['disguise-kit', 'forgery-kit']),
            'languages': json.dumps([]),
            'starting_equipment': json.dumps(['fine-clothes', 'disguise-kit', 'con-tools']),
            'starting_wealth': 15,
            'feature_name': 'False Identity',
            'feature_description': 'You have created a second identity with documentation, acquaintances, and disguises.',
            'personality_traits': json.dumps([
                'I fall in and out of love easily',
                'I have a joke for every occasion',
                'Flattery is my preferred trick',
                'I am a born gambler'
            ]),
            'ideals': json.dumps([
                'Independence: I am a free spirit',
                'Fairness: I never target people who cannot afford to lose',
                'Charity: I distribute money I acquire to those who need it',
                'Creativity: I never run the same con twice'
            ]),
            'bonds': json.dumps([
                'I fleeced the wrong person and must work to ensure they never cross paths with me',
                'I owe everything to my mentor',
                'Somewhere, I have a child who does not know me',
                'I come from a noble family, and one day I will reclaim my lands'
            ]),
            'flaws': json.dumps([
                'I cannot resist a pretty face',
                'I am always in debt',
                'I am convinced no one could ever fool me',
                'I am too greedy for my own good'
            ]),
            'source_book': "Player's Handbook",
            'page': 128,
            'srd': 0
        },
        {
            'id': 'background:soldier',
            'name': 'Soldier',
            'skill_proficiencies': json.dumps(['athletics', 'intimidation']),
            'tool_proficiencies': json.dumps(['gaming-set']),
            'languages': json.dumps([]),
            'starting_equipment': json.dumps(['insignia-of-rank', 'trophy', 'gaming-set', 'common-clothes']),
            'starting_wealth': 10,
            'feature_name': 'Military Rank',
            'feature_description': 'You have a rank from your career as a soldier. Soldiers loyal to your former military organization still recognize your authority and influence.',
            'personality_traits': json.dumps([
                'I am always polite and respectful',
                'I am haunted by memories of war',
                'I have lost too many friends',
                'I can stare down a hell hound without flinching'
            ]),
            'ideals': json.dumps([
                'Greater Good: Our lot is to lay down our lives in defense of others',
                'Responsibility: I do what I must and obey just authority',
                'Independence: When people follow orders blindly, they embrace tyranny',
                'Might: In life as in war, the stronger force wins'
            ]),
            'bonds': json.dumps([
                'I would still lay down my life for the people I served with',
                'Someone saved my life on the battlefield',
                'My honor is my life',
                'I will never forget the crushing defeat my company suffered'
            ]),
            'flaws': json.dumps([
                'The monstrous enemy we faced in battle still leaves me quivering with fear',
                'I have little respect for anyone who is not a proven warrior',
                'I made a terrible mistake in battle that cost many lives',
                'My hatred of my enemies is blind and unreasoning'
            ]),
            'source_book': "Player's Handbook",
            'page': 140,
            'srd': 0
        }
    ]

    cursor = conn.cursor()
    for bg in backgrounds_data:
        cursor.execute("""
            INSERT OR REPLACE INTO backgrounds (
                id, name, skill_proficiencies, tool_proficiencies, languages,
                starting_equipment, starting_wealth, feature_name, feature_description,
                personality_traits, ideals, bonds, flaws, source_book, page, srd
            ) VALUES (
                :id, :name, :skill_proficiencies, :tool_proficiencies, :languages,
                :starting_equipment, :starting_wealth, :feature_name, :feature_description,
                :personality_traits, :ideals, :bonds, :flaws, :source_book, :page, :srd
            )
        """, bg)

    conn.commit()
    print(f"   ✓ Added {len(backgrounds_data)} backgrounds")


def populate_skills(conn):
    """Populate skills table"""
    print("\n🎯 Populating skills...")

    skills_data = [
        ('skill:acrobatics', 'Acrobatics', 'dex', 'Balance, tumbling, and aerial maneuvers'),
        ('skill:animal-handling', 'Animal Handling', 'wis', 'Calming or training animals'),
        ('skill:arcana', 'Arcana', 'int', 'Knowledge of magic, spells, and magical items'),
        ('skill:athletics', 'Athletics', 'str', 'Climbing, jumping, swimming, and physical prowess'),
        ('skill:deception', 'Deception', 'cha', 'Lying and misleading others'),
        ('skill:history', 'History', 'int', 'Knowledge of historical events and legends'),
        ('skill:insight', 'Insight', 'wis', 'Determining true intentions of a creature'),
        ('skill:intimidation', 'Intimidation', 'cha', 'Influencing through threats and hostility'),
        ('skill:investigation', 'Investigation', 'int', 'Finding clues and making deductions'),
        ('skill:medicine', 'Medicine', 'wis', 'Stabilizing dying companions and diagnosing illnesses'),
        ('skill:nature', 'Nature', 'int', 'Knowledge of terrain, plants, animals, and weather'),
        ('skill:perception', 'Perception', 'wis', 'Spotting, hearing, or detecting something'),
        ('skill:performance', 'Performance', 'cha', 'Entertaining through music, dance, or acting'),
        ('skill:persuasion', 'Persuasion', 'cha', 'Influencing others in good faith'),
        ('skill:religion', 'Religion', 'int', 'Knowledge of deities, rites, and religious traditions'),
        ('skill:sleight-of-hand', 'Sleight of Hand', 'dex', 'Manual tricks, pickpocketing, and concealing objects'),
        ('skill:stealth', 'Stealth', 'dex', 'Hiding and moving silently'),
        ('skill:survival', 'Survival', 'wis', 'Tracking, hunting, and navigating wilderness')
    ]

    cursor = conn.cursor()
    for skill_id, name, ability, description in skills_data:
        cursor.execute("""
            INSERT OR REPLACE INTO skills (id, name, ability, description)
            VALUES (?, ?, ?, ?)
        """, (skill_id, name, ability, description))

    conn.commit()
    print(f"   ✓ Added {len(skills_data)} skills")


def populate_conditions(conn):
    """Populate conditions table"""
    print("\n🔴 Populating conditions...")

    conditions_data = [
        {
            'id': 'condition:blinded',
            'name': 'Blinded',
            'description': 'A blinded creature cannot see and automatically fails ability checks that require sight. Attack rolls against blinded creatures have advantage, and the creature\'s attack rolls have disadvantage.',
            'effects': json.dumps({'disadvantage': ['attack'], 'auto_fail': ['sight-checks'], 'vulnerability': ['attacks-against-have-advantage']}),
            'source_book': "Player's Handbook",
            'page': 290,
            'srd': 1
        },
        {
            'id': 'condition:charmed',
            'name': 'Charmed',
            'description': 'A charmed creature cannot attack the charmer or target the charmer with harmful abilities or magical effects. The charmer has advantage on ability checks to interact socially with the creature.',
            'effects': json.dumps({'restrictions': ['cannot-attack-charmer', 'cannot-target-charmer-harmful'], 'charmer_advantage': ['social-checks']}),
            'source_book': "Player's Handbook",
            'page': 290,
            'srd': 1
        },
        {
            'id': 'condition:frightened',
            'name': 'Frightened',
            'description': 'A frightened creature has disadvantage on ability checks and attack rolls while the source of its fear is within line of sight. The creature cannot willingly move closer to the source of its fear.',
            'effects': json.dumps({'disadvantage': ['ability-checks', 'attack-rolls'], 'restrictions': ['cannot-move-closer']}),
            'source_book': "Player's Handbook",
            'page': 290,
            'srd': 1
        },
        {
            'id': 'condition:poisoned',
            'name': 'Poisoned',
            'description': 'A poisoned creature has disadvantage on attack rolls and ability checks.',
            'effects': json.dumps({'disadvantage': ['attack-rolls', 'ability-checks']}),
            'source_book': "Player's Handbook",
            'page': 292,
            'srd': 1
        },
        {
            'id': 'condition:prone',
            'name': 'Prone',
            'description': 'A prone creature\'s only movement option is to crawl. The creature has disadvantage on attack rolls. An attack roll against the creature has advantage if the attacker is within 5 feet; otherwise, the attack roll has disadvantage.',
            'effects': json.dumps({'movement': 'crawl-only', 'disadvantage': ['attack-rolls'], 'special': 'attacks-against-advantage-if-within-5ft'}),
            'source_book': "Player's Handbook",
            'page': 292,
            'srd': 1
        },
        {
            'id': 'condition:unconscious',
            'name': 'Unconscious',
            'description': 'An unconscious creature is incapacitated, cannot move or speak, is unaware of its surroundings, drops what it is holding, falls prone, automatically fails Strength and Dexterity saving throws, attack rolls against it have advantage, and any attack that hits is a critical hit if the attacker is within 5 feet.',
            'effects': json.dumps({'incapacitated': True, 'prone': True, 'auto_fail': ['str-save', 'dex-save'], 'vulnerability': ['auto-crit-if-within-5ft', 'attacks-have-advantage']}),
            'source_book': "Player's Handbook",
            'page': 292,
            'srd': 1
        }
    ]

    cursor = conn.cursor()
    for condition in conditions_data:
        cursor.execute("""
            INSERT OR REPLACE INTO conditions (id, name, description, effects, source_book, page, srd)
            VALUES (:id, :name, :description, :effects, :source_book, :page, :srd)
        """, condition)

    conn.commit()
    print(f"   ✓ Added {len(conditions_data)} conditions")


def populate_basic_spells(conn):
    """Populate basic spells for Bard testing"""
    print("\n✨ Populating basic spells...")

    spells_data = [
        # Bard Cantrips
        {
            'id': 'spell:vicious-mockery',
            'name': 'Vicious Mockery',
            'level': 0,
            'school': 'Enchantment',
            'casting_time': '1 action',
            'range_value': 60,
            'range_type': 'feet',
            'components': json.dumps({'v': True, 's': False, 'm': False}),
            'duration': 'Instantaneous',
            'concentration': 0,
            'ritual': 0,
            'description': 'You unleash a string of insults laced with subtle enchantments at a creature you can see within range. If the target can hear you, it must succeed on a Wisdom saving throw or take 1d4 psychic damage and have disadvantage on the next attack roll it makes before the end of its next turn.',
            'higher_levels': 'This spell\'s damage increases by 1d4 when you reach 5th level (2d4), 11th level (3d4), and 17th level (4d4).',
            'damage_dice': '1d4',
            'damage_type': 'psychic',
            'healing_dice': None,
            'save_type': 'wis',
            'attack_type': None,
            'damage_formula': '1d4',
            'healing_formula': None,
            'save_dc_formula': '8 + proficiency_bonus + spellcasting_ability_mod',
            'attack_bonus_formula': None,
            'upcast_scaling': json.dumps({'damage_per_level': '1d4'}),
            'available_to_classes': json.dumps(['bard']),
            'source_book': "Player's Handbook",
            'page': 285,
            'srd': 1
        },
        {
            'id': 'spell:prestidigitation',
            'name': 'Prestidigitation',
            'level': 0,
            'school': 'Transmutation',
            'casting_time': '1 action',
            'range_value': 10,
            'range_type': 'feet',
            'components': json.dumps({'v': True, 's': True, 'm': False}),
            'duration': 'Up to 1 hour',
            'concentration': 0,
            'ritual': 0,
            'description': 'This spell is a minor magical trick that novice spellcasters use for practice. You create one of various effects within range.',
            'higher_levels': None,
            'damage_dice': None,
            'damage_type': None,
            'healing_dice': None,
            'save_type': None,
            'attack_type': None,
            'damage_formula': None,
            'healing_formula': None,
            'save_dc_formula': None,
            'attack_bonus_formula': None,
            'upcast_scaling': None,
            'available_to_classes': json.dumps(['bard', 'sorcerer', 'warlock', 'wizard']),
            'source_book': "Player's Handbook",
            'page': 267,
            'srd': 1
        },
        # Bard 1st Level Spells
        {
            'id': 'spell:healing-word',
            'name': 'Healing Word',
            'level': 1,
            'school': 'Evocation',
            'casting_time': '1 bonus action',
            'range_value': 60,
            'range_type': 'feet',
            'components': json.dumps({'v': True, 's': False, 'm': False}),
            'duration': 'Instantaneous',
            'concentration': 0,
            'ritual': 0,
            'description': 'A creature of your choice that you can see within range regains hit points equal to 1d4 + your spellcasting ability modifier.',
            'higher_levels': 'When you cast this spell using a spell slot of 2nd level or higher, the healing increases by 1d4 for each slot level above 1st.',
            'damage_dice': None,
            'damage_type': None,
            'healing_dice': '1d4',
            'save_type': None,
            'attack_type': None,
            'damage_formula': None,
            'healing_formula': '1d4 + spellcasting_ability_mod',
            'save_dc_formula': None,
            'attack_bonus_formula': None,
            'upcast_scaling': json.dumps({'healing_per_level': '1d4'}),
            'available_to_classes': json.dumps(['bard', 'cleric', 'druid']),
            'source_book': "Player's Handbook",
            'page': 250,
            'srd': 1
        },
        {
            'id': 'spell:thunderwave',
            'name': 'Thunderwave',
            'level': 1,
            'school': 'Evocation',
            'casting_time': '1 action',
            'range_value': 0,
            'range_type': 'self',
            'components': json.dumps({'v': True, 's': True, 'm': False}),
            'duration': 'Instantaneous',
            'concentration': 0,
            'ritual': 0,
            'description': 'A wave of thunderous force sweeps out from you. Each creature in a 15-foot cube originating from you must make a Constitution saving throw. On a failed save, a creature takes 2d8 thunder damage and is pushed 10 feet away from you. On a successful save, the creature takes half as much damage and is not pushed.',
            'higher_levels': 'When you cast this spell using a spell slot of 2nd level or higher, the damage increases by 1d8 for each slot level above 1st.',
            'damage_dice': '2d8',
            'damage_type': 'thunder',
            'healing_dice': None,
            'save_type': 'con',
            'attack_type': None,
            'damage_formula': '2d8',
            'healing_formula': None,
            'save_dc_formula': '8 + proficiency_bonus + spellcasting_ability_mod',
            'attack_bonus_formula': None,
            'upcast_scaling': json.dumps({'damage_per_level': '1d8'}),
            'available_to_classes': json.dumps(['bard', 'druid', 'sorcerer', 'wizard']),
            'source_book': "Player's Handbook",
            'page': 282,
            'srd': 1
        },
        {
            'id': 'spell:cure-wounds',
            'name': 'Cure Wounds',
            'level': 1,
            'school': 'Evocation',
            'casting_time': '1 action',
            'range_value': 0,
            'range_type': 'touch',
            'components': json.dumps({'v': True, 's': True, 'm': False}),
            'duration': 'Instantaneous',
            'concentration': 0,
            'ritual': 0,
            'description': 'A creature you touch regains a number of hit points equal to 1d8 + your spellcasting ability modifier.',
            'higher_levels': 'When you cast this spell using a spell slot of 2nd level or higher, the healing increases by 1d8 for each slot level above 1st.',
            'damage_dice': None,
            'damage_type': None,
            'healing_dice': '1d8',
            'save_type': None,
            'attack_type': None,
            'damage_formula': None,
            'healing_formula': '1d8 + spellcasting_ability_mod',
            'save_dc_formula': None,
            'attack_bonus_formula': None,
            'upcast_scaling': json.dumps({'healing_per_level': '1d8'}),
            'available_to_classes': json.dumps(['bard', 'cleric', 'druid', 'paladin', 'ranger']),
            'source_book': "Player's Handbook",
            'page': 230,
            'srd': 1
        }
    ]

    cursor = conn.cursor()
    for spell in spells_data:
        print(f"  Inserting: {spell['name']} (keys: {len(spell)})")
        cursor.execute("""
            INSERT OR REPLACE INTO spells (
                id, name, level, school, casting_time, range_value, range_type,
                components, duration, concentration, ritual, description, higher_levels,
                damage_dice, damage_type, healing_dice, save_type, attack_type,
                damage_formula, healing_formula, save_dc_formula, attack_bonus_formula,
                upcast_scaling, available_to_classes, source_book, page, srd
            ) VALUES (
                :id, :name, :level, :school, :casting_time, :range_value, :range_type,
                :components, :duration, :concentration, :ritual, :description, :higher_levels,
                :damage_dice, :damage_type, :healing_dice, :save_type, :attack_type,
                :damage_formula, :healing_formula, :save_dc_formula, :attack_bonus_formula,
                :upcast_scaling, :available_to_classes, :source_book, :page, :srd
            )
        """, spell)

    conn.commit()
    print(f"   ✓ Added {len(spells_data)} spells")


def main():
    """Main population function"""
    print("=" * 60)
    print("🎲 D&D AI DM - Populate Entities")
    print("=" * 60)

    conn = sqlite3.connect(REFERENCE_DB_PATH)

    populate_races(conn)
    populate_backgrounds(conn)
    populate_skills(conn)
    populate_conditions(conn)
    populate_basic_spells(conn)

    conn.close()

    print("\n" + "=" * 60)
    print("✅ Entity population complete!")
    print("=" * 60)
    print("\nPopulated:")
    print("  • 3 Races (Human, Elf, Tiefling)")
    print("  • 2 Backgrounds (Charlatan, Soldier)")
    print("  • 18 Skills (all D&D 5E skills)")
    print("  • 6 Conditions (basic set)")
    print("  • 5 Spells (Bard cantrips + 1st level)")


if __name__ == '__main__':
    main()
