#!/usr/bin/env python3
"""Bootstrap script - Parse SRD into atomic entities with two-stage retrieval"""
import sys
from pathlib import Path
from glob import glob

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from config import SRD_DIR, REFERENCE_DB_PATH, VECTOR_DB_DIR
from data.entity_manager import EntityManager
from parsers.atomic_parser import AtomicParser


def bootstrap_atomic():
    """
    Parse SRD content into atomic entities

    Process:
    1. Parse spells → atomic Spell objects
    2. Parse monsters → atomic Monster objects
    3. Parse rules → atomic Rule objects
    4. Parse conditions → atomic Condition objects
    5. Index all with two-stage retrieval (metadata + embeddings)
    """
    print("🎲 D&D AI DM - Atomic Bootstrap")
    print("=" * 60)
    print("\nThis will parse ALL SRD content into atomic entities:")
    print("  • Spells (322 files)")
    print("  • Monsters (319 files)")
    print("  • Items (242 files)")
    print("  • Rules (Combat, Abilities, etc.)")
    print("  • Conditions (14 status effects)")
    print("\nTwo-stage indexing:")
    print("  Stage 1: Metadata index (SQL) - Fast filtering")
    print("  Stage 2: Embeddings (Vector DB) - Semantic search")

    if SRD_DIR.name == "DND.SRD.Wiki-main":
        # Need to navigate to actual SRD content
        actual_srd = SRD_DIR
    else:
        actual_srd = SRD_DIR

    if not actual_srd.exists():
        print(f"\n❌ ERROR: SRD directory not found at {actual_srd}")
        print(f"Please ensure the symlink is correct:")
        print(f"  cd {project_root}/data")
        print(f"  ln -s /path/to/DND.SRD.Wiki-main srd")
        return False

    print(f"\n📂 SRD Directory: {actual_srd}")

    # Initialize entity manager
    print("\n📊 Initializing entity manager...")
    entity_manager = EntityManager(REFERENCE_DB_PATH, VECTOR_DB_DIR)
    parser = AtomicParser()

    # Parse spells
    print("\n📜 Parsing Spells...")
    spells_dir = actual_srd / "Spells"
    spell_count = 0
    spell_errors = 0

    if spells_dir.exists():
        spell_files = list(spells_dir.glob("*.md"))
        # Exclude index/list files
        spell_files = [f for f in spell_files if f.stem not in ["index", "Spell Lists", "Spells"]]

        print(f"  Found {len(spell_files)} spell files")

        for i, spell_file in enumerate(spell_files, 1):
            try:
                spell = parser.parse_spell_file(spell_file)
                entity_manager.index_entity(spell)

                if i % 10 == 0:
                    print(f"    Indexed {i}/{len(spell_files)} spells...", flush=True)

                spell_count += 1
            except Exception as e:
                spell_errors += 1
                if spell_errors <= 5:  # Show first 5 errors
                    print(f"  ✗ {spell_file.name}: {e}", flush=True)

        print(f"  ✓ Indexed {spell_count} spells ({spell_errors} errors)")
    else:
        print(f"  ⚠️  Spells directory not found: {spells_dir}")

    # Parse monsters
    print("\n🐉 Parsing Monsters...")
    monsters_dir = actual_srd / "Monsters"
    monster_count = 0
    monster_errors = 0

    if monsters_dir.exists():
        monster_files = list(monsters_dir.glob("*.md"))
        # Exclude index files
        monster_files = [f for f in monster_files if "#" not in f.stem and f.stem not in ["index"]]

        print(f"  Found {len(monster_files)} monster files")

        for i, monster_file in enumerate(monster_files, 1):
            try:
                monster = parser.parse_monster_file(monster_file)
                entity_manager.index_entity(monster)

                if i % 10 == 0:
                    print(f"    Indexed {i}/{len(monster_files)} monsters...", flush=True)

                monster_count += 1
            except Exception as e:
                monster_errors += 1
                if monster_errors <= 5:
                    print(f"  ✗ {monster_file.name}: {e}", flush=True)

        print(f"  ✓ Indexed {monster_count} monsters ({monster_errors} errors)")
    else:
        print(f"  ⚠️  Monsters directory not found: {monsters_dir}")

    # Parse items
    print("\n💎 Parsing Magic Items...")
    items_dir = actual_srd / "Treasure"
    item_count = 0
    item_errors = 0

    if items_dir.exists():
        item_files = list(items_dir.glob("*.md"))
        # Exclude index files
        item_files = [f for f in item_files if f.stem not in ["index", "Treasure"]]

        print(f"  Found {len(item_files)} item files")

        for i, item_file in enumerate(item_files, 1):
            try:
                item = parser.parse_item_file(item_file)
                entity_manager.index_entity(item)

                if i % 10 == 0:
                    print(f"    Indexed {i}/{len(item_files)} items...", flush=True)

                item_count += 1
            except Exception as e:
                item_errors += 1
                if item_errors <= 5:
                    print(f"  ✗ {item_file.name}: {e}", flush=True)

        print(f"  ✓ Indexed {item_count} items ({item_errors} errors)")
    else:
        print(f"  ⚠️  Treasure directory not found: {items_dir}")

    # Parse rules
    print("\n⚔️  Parsing Rules...")
    rules_files = [
        (actual_srd / "Gameplay" / "Combat.md", "combat"),
        (actual_srd / "Gameplay" / "Abilities.md", "abilities"),
        (actual_srd / "Gameplay" / "Adventuring.md", "exploration"),
    ]

    rule_count = 0
    for rules_file, domain in rules_files:
        if rules_file.exists():
            try:
                rules = parser.parse_rules_file(rules_file, domain)
                for rule in rules:
                    entity_manager.index_entity(rule)
                    rule_count += 1

                print(f"  ✓ {rules_file.name}: {len(rules)} rules ({domain})")
            except Exception as e:
                print(f"  ✗ {rules_file.name}: {e}")
        else:
            print(f"  ⚠️  {rules_file.name} not found")

    # Parse conditions
    print("\n🔮 Parsing Conditions...")
    conditions_file = actual_srd / "Gamemastering" / "Conditions.md"
    condition_count = 0

    if conditions_file.exists():
        try:
            conditions = parser.parse_conditions_file(conditions_file)
            for condition in conditions:
                entity_manager.index_entity(condition)
                condition_count += 1

            print(f"  ✓ Indexed {len(conditions)} conditions")
        except Exception as e:
            print(f"  ✗ Conditions.md: {e}")
    else:
        print(f"  ⚠️  Conditions.md not found")

    # Summary
    print("\n" + "=" * 60)
    print("✅ Atomic Bootstrap Complete!")
    print(f"\n📊 Summary:")
    print(f"  • Spells: {spell_count} ({spell_errors} errors)")
    print(f"  • Monsters: {monster_count} ({monster_errors} errors)")
    print(f"  • Items: {item_count} ({item_errors} errors)")
    print(f"  • Rules: {rule_count}")
    print(f"  • Conditions: {condition_count}")
    print(f"  • Total entities: {spell_count + monster_count + item_count + rule_count + condition_count}")

    # Cache stats
    print(f"\n💾 Cache Statistics:")
    cache_stats = entity_manager.cache_stats()
    for key, value in cache_stats.items():
        print(f"  • {key}: {value}")

    print(f"\n🎮 Ready to play! Run: python src/main.py")
    print("\nTwo-stage retrieval is now active:")
    print("  Stage 1: Metadata filtering (instant)")
    print("  Stage 2: Embedding similarity (only on filtered results)")
    print("\nExample queries:")
    print("  get_spell('Fireball') → Instant metadata lookup")
    print("  search_spells('fire damage', level=3) → Filter by level, then embed")
    print("  get_monster('Goblin') → Instant metadata lookup")

    return True


if __name__ == "__main__":
    success = bootstrap_atomic()
    sys.exit(0 if success else 1)
