"""Atomic parser - Convert SRD content into atomic entities"""
import re
from pathlib import Path
from typing import List

from data.entities import Spell, Monster, Rule, Item
from parsers.markdown_utils import read_markdown, extract_sections


class AtomicParser:
    """Parse SRD content into atomic entities"""

    @staticmethod
    def parse_spell_file(file_path: Path) -> Spell:
        """Parse a spell markdown file into atomic Spell entity"""
        content = read_markdown(file_path)
        return Spell.from_markdown(file_path, content)

    @staticmethod
    def parse_monster_file(file_path: Path) -> Monster:
        """Parse a monster markdown file into atomic Monster entity"""
        content = read_markdown(file_path)
        return Monster.from_markdown(file_path, content)

    @staticmethod
    def parse_item_file(file_path: Path) -> Item:
        """Parse an item markdown file into atomic Item entity"""
        content = read_markdown(file_path)
        return Item.from_markdown(file_path, content)

    @staticmethod
    def parse_rules_file(file_path: Path, domain: str) -> List[Rule]:
        """
        Parse a rules file into atomic Rule entities

        Each ## or ### section becomes a separate Rule entity

        Args:
            file_path: Path to markdown file (e.g., Combat.md)
            domain: Rule domain (combat, magic, exploration, etc.)

        Returns:
            List of Rule entities
        """
        content = read_markdown(file_path)
        rules = []

        # Split by headers
        sections = AtomicParser._split_into_sections(content)

        for section_name, section_content in sections:
            if len(section_content.strip()) < 50:  # Skip very short sections
                continue

            rule = Rule.from_markdown(section_name, section_content, domain)
            rules.append(rule)

        return rules

    @staticmethod
    def _split_into_sections(content: str) -> List[tuple]:
        """
        Split markdown content into sections by headers

        Returns:
            List of (section_name, section_content) tuples
        """
        sections = []
        lines = content.split('\n')

        current_section_name = None
        current_section_lines = []

        for line in lines:
            # Check if line is a header (## or ###)
            header_match = re.match(r'^(#{2,3})\s+(.+)$', line)

            if header_match:
                # Save previous section
                if current_section_name:
                    section_content = '\n'.join(current_section_lines).strip()
                    if section_content:
                        sections.append((current_section_name, section_content))

                # Start new section
                current_section_name = header_match.group(2).strip()
                current_section_lines = [line]  # Include header in content
            else:
                if current_section_name:
                    current_section_lines.append(line)

        # Save final section
        if current_section_name:
            section_content = '\n'.join(current_section_lines).strip()
            if section_content:
                sections.append((current_section_name, section_content))

        return sections

    @staticmethod
    def parse_conditions_file(file_path: Path) -> List[Rule]:
        """Parse Conditions.md into individual condition rules"""
        content = read_markdown(file_path)
        conditions = []

        sections = AtomicParser._split_into_sections(content)

        for section_name, section_content in sections:
            if len(section_content.strip()) < 30:
                continue

            # Create Rule entity for each condition
            condition = Rule(
                id=f"condition:{section_name.lower().replace(' ', '_')}",
                type="condition",
                name=section_name,
                tags=["condition", "status_effect"],
                content=section_content,
                metadata={"source": "Conditions.md"},
                domain="conditions",
                category="status_effect"
            )
            conditions.append(condition)

        return conditions


def test_parsers():
    """Test the atomic parsers"""
    from config import SRD_DIR

    print("Testing Atomic Parsers")
    print("=" * 50)

    parser = AtomicParser()

    # Test spell parsing
    print("\n📜 Testing Spell Parser:")
    spell_file = SRD_DIR / "Spells" / "Fireball.md"
    if spell_file.exists():
        spell = parser.parse_spell_file(spell_file)
        print(f"  ✓ Parsed: {spell.name}")
        print(f"    Level: {spell.level}, School: {spell.school}")
        print(f"    Tags: {spell.tags}")
        print(f"    Damage: {spell.damage}, Save: {spell.save}")
    else:
        print(f"  ⚠️  Fireball.md not found")

    # Test monster parsing
    print("\n🐉 Testing Monster Parser:")
    monster_file = SRD_DIR / "Monsters" / "Goblin.md"
    if monster_file.exists():
        monster = parser.parse_monster_file(monster_file)
        print(f"  ✓ Parsed: {monster.name}")
        print(f"    CR: {monster.cr}, Size: {monster.size}")
        print(f"    AC: {monster.ac}, HP: {monster.hp}")
        print(f"    Tags: {monster.tags}")
    else:
        print(f"  ⚠️  Goblin.md not found")

    # Test rule parsing
    print("\n⚔️  Testing Rule Parser:")
    combat_file = SRD_DIR / "Gameplay" / "Combat.md"
    if combat_file.exists():
        rules = parser.parse_rules_file(combat_file, domain="combat")
        print(f"  ✓ Parsed {len(rules)} rules from Combat.md")
        for rule in rules[:3]:
            print(f"    - {rule.name} (domain: {rule.domain})")
    else:
        print(f"  ⚠️  Combat.md not found")

    # Test conditions
    print("\n🔮 Testing Conditions Parser:")
    conditions_file = SRD_DIR / "Gamemastering" / "Conditions.md"
    if conditions_file.exists():
        conditions = parser.parse_conditions_file(conditions_file)
        print(f"  ✓ Parsed {len(conditions)} conditions")
        for cond in conditions[:3]:
            print(f"    - {cond.name}")
    else:
        print(f"  ⚠️  Conditions.md not found")


if __name__ == "__main__":
    test_parsers()
