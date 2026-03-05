"""Parser for D&D race markdown files"""
import re
from pathlib import Path
from typing import Dict, List
from .markdown_utils import read_markdown, extract_sections


def parse_race_file(file_path: Path) -> Dict:
    """
    Parse a race markdown file into structured data

    Args:
        file_path: Path to race .md file

    Returns:
        Dictionary with race data
    """
    content = read_markdown(file_path)
    sections = extract_sections(content)

    race_data = {
        "name": file_path.stem,
        "ability_score_increase": extract_ability_score_increase(content, sections),
        "size": extract_size(content, sections),
        "speed": extract_speed(content, sections),
        "traits": extract_traits(sections),
        "languages": extract_languages(content, sections),
        "source_file": str(file_path)
    }

    return race_data


def extract_ability_score_increase(content: str, sections: Dict[str, str]) -> str:
    """Extract ability score increases"""
    full_content = content + ' ' + ' '.join(sections.values())

    # Look for "Ability Score Increase" section or line
    match = re.search(
        r'Ability\s+Score\s+Increase\.?\s*[:\-]?\s*([^\n]+)',
        full_content,
        re.IGNORECASE
    )

    if match:
        asi = match.group(1).strip()
        # Clean up markdown
        asi = re.sub(r'\*\*', '', asi)
        return asi

    return "None"


def extract_size(content: str, sections: Dict[str, str]) -> str:
    """Extract creature size"""
    full_content = content + ' ' + ' '.join(sections.values())

    # Look for "Size:" line
    match = re.search(r'Size\.?\s*[:\-]?\s*([^\n]+)', full_content, re.IGNORECASE)
    if match:
        size_text = match.group(1).lower()
        # Extract size category
        for size in ["Small", "Medium", "Large", "Tiny", "Huge", "Gargantuan"]:
            if size.lower() in size_text:
                return size

    # Look for mentions in text
    for size in ["small", "medium", "large", "tiny", "huge", "gargantuan"]:
        if f"are {size}" in full_content.lower() or f"is {size}" in full_content.lower():
            return size.capitalize()

    return "Medium"  # Default


def extract_speed(content: str, sections: Dict[str, str]) -> int:
    """Extract base walking speed in feet"""
    full_content = content + ' ' + ' '.join(sections.values())

    # Look for "Speed:" line
    match = re.search(r'Speed\.?\s*[:\-]?\s*(\d+)', full_content, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Look for "your speed is X feet"
    match = re.search(r'(?:speed|movement)\s+is\s+(\d+)\s*(?:feet|ft)', full_content, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 30  # Default


def extract_traits(sections: Dict[str, str]) -> str:
    """Extract racial traits"""
    traits = {}

    # Look through sections for trait descriptions
    for section_name, section_content in sections.items():
        # Skip common non-trait sections
        if section_name.lower() in ['description', 'lore', 'names', 'history']:
            continue

        # Headers like "### Darkvision" or "### Lucky"
        if section_content.strip():
            # Clean section name
            trait_name = section_name.replace('###', '').replace('##', '').strip()

            # Extract first paragraph as description
            paragraphs = section_content.split('\n\n')
            description = paragraphs[0].strip() if paragraphs else section_content.strip()

            # Limit description length
            if len(description) > 200:
                description = description[:200] + "..."

            traits[trait_name] = description

    return str(traits)  # Convert to JSON string


def extract_languages(content: str, sections: Dict[str, str]) -> str:
    """Extract languages the race can speak"""
    full_content = content + ' ' + ' '.join(sections.values())

    # Look for "Languages:" line
    match = re.search(r'Languages?\.?\s*[:\-]?\s*([^\n]+)', full_content, re.IGNORECASE)
    if match:
        languages = match.group(1).strip()
        # Clean up markdown
        languages = re.sub(r'\*\*', '', languages)
        return languages

    return "Common"  # Default
