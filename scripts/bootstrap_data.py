#!/usr/bin/env python3
"""Bootstrap script to initialize the D&D AI DM database"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from config import SRD_DIR, REFERENCE_DB_PATH, VECTOR_DB_DIR
from data.sqlite_db import ReferenceDB
from data.vector_db import MultiVectorDBManager
from parsers.class_parser import parse_class_file
from parsers.race_parser import parse_race_file
from parsers.markdown_utils import read_markdown, chunk_by_headers


def bootstrap():
    """Initialize all data"""
    print("🎲 D&D AI DM - Bootstrap Script")
    print("=" * 50)

    # Check if SRD directory exists
    if not SRD_DIR.exists():
        print(f"\n❌ ERROR: SRD directory not found at {SRD_DIR}")
        print("Please create a symlink or copy the SRD content:")
        print(f"  ln -s /Users/barna/Desktop/DND.SRD.Wiki-main {SRD_DIR}")
        return False

    # Initialize databases
    print("\n📊 Initializing databases...")
    reference_db = ReferenceDB(REFERENCE_DB_PATH)
    vector_manager = MultiVectorDBManager(VECTOR_DB_DIR)

    # Parse and load classes
    print("\n⚔️  Parsing classes...")
    classes_dir = SRD_DIR / "Classes"
    class_count = 0

    if classes_dir.exists():
        for class_file in classes_dir.glob("*.md"):
            try:
                class_data = parse_class_file(class_file)
                reference_db.insert("classes", class_data)
                print(f"  ✓ {class_data['name']}")
                class_count += 1
            except Exception as e:
                print(f"  ✗ {class_file.name}: {e}")
    else:
        print(f"  ⚠️  Classes directory not found: {classes_dir}")

    # Parse and load races
    print("\n🧝 Parsing races...")
    races_dir = SRD_DIR / "Races"
    race_count = 0

    if races_dir.exists():
        for race_file in races_dir.glob("*.md"):
            # Skip index files
            if race_file.stem.lower() in ["index", "readme"]:
                continue

            try:
                race_data = parse_race_file(race_file)
                reference_db.insert("races", race_data)
                print(f"  ✓ {race_data['name']}")
                race_count += 1
            except Exception as e:
                print(f"  ✗ {race_file.name}: {e}")
    else:
        print(f"  ⚠️  Races directory not found: {races_dir}")

    # Index core rules in vector DB
    print("\n📚 Indexing core rules...")
    rules_dir = SRD_DIR / "Gameplay"
    rules_files = ["Combat.md", "Abilities.md", "Adventuring.md"]
    rules_count = 0

    if rules_dir.exists():
        documents = []
        metadatas = []
        ids = []

        for rules_file_name in rules_files:
            rules_file = rules_dir / rules_file_name
            if not rules_file.exists():
                print(f"  ⚠️  {rules_file_name} not found")
                continue

            try:
                content = read_markdown(rules_file)
                chunks = chunk_by_headers(content, max_chunk_size=1500)

                for i, chunk in enumerate(chunks):
                    documents.append(chunk)
                    metadatas.append({
                        "file": str(rules_file),
                        "category": "rules",
                        "filename": rules_file_name
                    })
                    ids.append(f"rules:{rules_file_name}:{i}")

                print(f"  ✓ {rules_file_name} ({len(chunks)} chunks)")
                rules_count += 1
            except Exception as e:
                print(f"  ✗ {rules_file_name}: {e}")

        # Index all documents at once
        if documents:
            vector_manager.index_documents("rules", documents, metadatas, ids)

    else:
        print(f"  ⚠️  Gameplay directory not found: {rules_dir}")

    # Index conditions
    print("\n🔮 Indexing conditions...")
    conditions_file = SRD_DIR / "Gamemastering" / "Conditions.md"

    if conditions_file.exists():
        try:
            content = read_markdown(conditions_file)
            chunks = chunk_by_headers(content, max_chunk_size=1000)

            documents = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "file": str(conditions_file),
                    "category": "rules",
                    "filename": "Conditions.md"
                })
                ids.append(f"rules:Conditions.md:{i}")

            vector_manager.index_documents("rules", documents, metadatas, ids)
            print(f"  ✓ Conditions.md ({len(chunks)} chunks)")
        except Exception as e:
            print(f"  ✗ Conditions.md: {e}")
    else:
        print(f"  ⚠️  Conditions.md not found")

    # Summary
    print("\n" + "=" * 50)
    print("✅ Bootstrap Complete!")
    print(f"\n📊 Summary:")
    print(f"  • Classes loaded: {class_count}")
    print(f"  • Races loaded: {race_count}")
    print(f"  • Core rules indexed: {rules_count} files")
    print(f"  • Vector DB documents: {vector_manager.get_collection_count('rules')}")
    print(f"\n🎮 Ready to play! Run: python src/main.py")

    return True


if __name__ == "__main__":
    success = bootstrap()
    sys.exit(0 if success else 1)
