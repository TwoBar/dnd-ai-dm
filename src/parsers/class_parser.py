"""Parser for D&D class markdown files"""
import re
from pathlib import Path
from typing import Dict, List
from .markdown_utils import read_markdown, extract_sections, extract_table


def parse_class_file(file_path: Path) -> Dict:
    """
    Parse a class markdown file into structured data

    Args:
        file_path: Path to class .md file

    Returns:
        Dictionary with class data
    """
    content = read_markdown(file_path)
    sections = extract_sections(content)

    class_data = {
        "name": file_path.stem,  # Filename without extension
        "hit_die": extract_hit_die(content),
        "primary_ability": extract_primary_ability(sections),
        "saves": extract_saving_throws(sections),
        "proficiencies": extract_proficiencies(sections),
        "features": extract_features(content, sections),
        "spellcasting": extract_spellcasting(sections),
        "source_file": str(file_path)
    }

    return class_data


def extract_hit_die(content: str) -> str:
    """Extract hit die (e.g., '1d10')"""
    # Look for "Hit Dice: 1d10 per level" or similar
    match = re.search(r'Hit\s+Dic?e?:?\s*(\d+d\d+)', content, re.IGNORECASE)
    if match:
        return match.group(1)

    # Look for "Hit Points at 1st Level: 10 + Constitution modifier"
    match = re.search(r'Hit\s+Points\s+at\s+1st\s+Level:?\s*(\d+)', content, re.IGNORECASE)
    if match:
        hp = int(match.group(1))
        # Reverse calculate: d6=6, d8=8, d10=10, d12=12
        return f"1d{hp}"

    return "1d8"  # Default


def extract_primary_ability(sections: Dict[str, str]) -> str:
    """Extract primary ability (e.g., 'Strength' or 'Intelligence')"""
    # Look in various sections
    for section_name in ["Class Features", "Quick Build", sections.get(list(sections.keys())[0], "")]:
        section_content = sections.get(section_name, "")

        # Look for "primary ability" mentions
        match = re.search(r'primary\s+(?:ability|stat)?\s*(?:is|:)?\s*(\w+)', section_content, re.IGNORECASE)
        if match:
            ability = match.group(1).capitalize()
            if ability in ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]:
                return ability

        # Look for "highest ability score in X"
        match = re.search(r'highest\s+(?:ability\s+)?score\s+in\s+(\w+)', section_content, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()

    return "Unknown"


def extract_saving_throws(sections: Dict[str, str]) -> str:
    """Extract proficient saving throws"""
    # Look for "Saving Throws:" line
    full_content = ' '.join(sections.values())

    match = re.search(r'Saving\s+Throws?:?\s*([^\n]+)', full_content, re.IGNORECASE)
    if match:
        saves = match.group(1).strip()
        # Clean up common variations
        saves = re.sub(r'\*\*', '', saves)  # Remove markdown bold
        saves = re.sub(r'and', ',', saves, flags=re.IGNORECASE)
        return saves.strip()

    return "None"


def extract_proficiencies(sections: Dict[str, str]) -> Dict[str, str]:
    """Extract proficiencies (armor, weapons, tools, skills)"""
    proficiencies = {
        "armor": "None",
        "weapons": "None",
        "tools": "None",
        "skills": "None"
    }

    full_content = ' '.join(sections.values())

    # Extract each proficiency type
    for prof_type in ["Armor", "Weapons", "Tools", "Skills"]:
        pattern = rf'{prof_type}:?\s*([^\n]+?)(?:\n|\*\*)'
        match = re.search(pattern, full_content, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'\*\*', '', value)  # Remove markdown
            proficiencies[prof_type.lower()] = value

    return str(proficiencies)  # Convert to JSON string for storage


def extract_features(content: str, sections: Dict[str, str]) -> str:
    """Extract class features by level"""
    features = {}

    # Look for class features table
    table_data = None

    # Try to find table in common section names
    for section_name in ["Class Features", "The " + sections.get("name", ""), ""]:
        section_content = sections.get(section_name, content)
        if '|' in section_content:
            # Try to extract table
            lines = section_content.split('\n')
            for i, line in enumerate(lines):
                if 'Level' in line and 'Features' in line and '|' in line:
                    # Found feature table, parse next lines
                    j = i + 2  # Skip header separator
                    while j < len(lines) and '|' in lines[j]:
                        cols = [c.strip() for c in lines[j].split('|') if c.strip()]
                        if len(cols) >= 2:
                            try:
                                level = int(re.search(r'\d+', cols[0]).group())
                                feature_list = cols[1]
                                features[level] = feature_list
                            except (AttributeError, ValueError):
                                pass
                        j += 1
                    break

    # If no table found, extract from headers
    if not features:
        # Look for headers like "### 1st Level" or "## Level 1"
        for match in re.finditer(r'#{2,}\s*(?:Level\s+)?(\d+)(?:st|nd|rd|th)?\s*(?:Level)?[:\s]*([^\n]+)?', content):
            level = int(match.group(1))
            feature_name = match.group(2) if match.group(2) else f"Level {level} Features"
            features[level] = feature_name.strip()

    return str(features)  # Convert to JSON string


def extract_spellcasting(sections: Dict[str, str]) -> str:
    """Extract spellcasting information if the class has it"""
    full_content = ' '.join(sections.values()).lower()

    if 'spellcasting' not in full_content:
        return "None"

    spellcasting_info = {
        "has_spellcasting": True,
        "ability": "Unknown"
    }

    # Try to find spellcasting ability
    match = re.search(r'(?:uses?|is)\s+(\w+)\s+as\s+(?:your|their|its)\s+spellcasting\s+ability', full_content)
    if match:
        spellcasting_info["ability"] = match.group(1).capitalize()

    return str(spellcasting_info)
