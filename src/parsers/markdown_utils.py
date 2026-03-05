"""Utilities for parsing markdown files"""
import re
from typing import List, Dict, Tuple
from pathlib import Path


def read_markdown(file_path: Path) -> str:
    """Read markdown file content"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def chunk_by_headers(content: str, max_chunk_size: int = 2000) -> List[str]:
    """
    Split markdown content by headers while preserving context

    Args:
        content: Markdown content
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of text chunks
    """
    chunks = []
    lines = content.split('\n')

    current_chunk = []
    current_headers = []  # Stack of headers for context
    current_size = 0

    for line in lines:
        # Check if line is a header
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)

        if header_match:
            level = len(header_match.group(1))
            header_text = header_match.group(2)

            # Update header stack
            current_headers = current_headers[:level-1] + [header_text]

            # If chunk is getting large, save it
            if current_size > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0

                # Add context headers to new chunk
                for i, h in enumerate(current_headers, 1):
                    context_line = f"{'#' * i} {h}"
                    current_chunk.append(context_line)
                    current_size += len(context_line)

        current_chunk.append(line)
        current_size += len(line) + 1  # +1 for newline

    # Add final chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    return chunks


def extract_title(content: str) -> str:
    """Extract the main title from markdown content"""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return match.group(1) if match else "Unknown"


def extract_sections(content: str) -> Dict[str, str]:
    """
    Extract sections from markdown content

    Returns:
        Dict mapping section headers to their content
    """
    sections = {}
    lines = content.split('\n')

    current_header = None
    current_content = []

    for line in lines:
        header_match = re.match(r'^##\s+(.+)$', line)

        if header_match:
            # Save previous section
            if current_header:
                sections[current_header] = '\n'.join(current_content).strip()

            # Start new section
            current_header = header_match.group(1)
            current_content = []
        elif current_header:
            current_content.append(line)

    # Save final section
    if current_header:
        sections[current_header] = '\n'.join(current_content).strip()

    return sections


def extract_table(content: str, table_name: str = None) -> List[Dict[str, str]]:
    """
    Extract table data from markdown

    Args:
        content: Markdown content
        table_name: Optional table name/header to find specific table

    Returns:
        List of dictionaries representing table rows
    """
    lines = content.split('\n')
    tables = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for table header (line with |)
        if '|' in line and i + 1 < len(lines):
            # Check if next line is separator (|---|---|)
            next_line = lines[i + 1]
            if re.match(r'^\|[\s\-:|]+\|$', next_line):
                # Found a table
                headers = [h.strip() for h in line.split('|') if h.strip()]

                # Extract rows
                rows = []
                j = i + 2
                while j < len(lines) and '|' in lines[j]:
                    row_data = [cell.strip() for cell in lines[j].split('|') if cell.strip()]
                    if row_data:
                        row_dict = dict(zip(headers, row_data))
                        rows.append(row_dict)
                    j += 1

                tables.append(rows)
                i = j
                continue

        i += 1

    # Return first table if no specific name requested
    return tables[0] if tables else []


def extract_list_items(content: str, list_type: str = "ul") -> List[str]:
    """
    Extract list items from markdown

    Args:
        content: Markdown content
        list_type: "ul" for unordered (- or *), "ol" for ordered (1.)

    Returns:
        List of item texts
    """
    items = []

    if list_type == "ul":
        pattern = r'^[\s]*[-*]\s+(.+)$'
    else:  # ol
        pattern = r'^[\s]*\d+\.\s+(.+)$'

    for line in content.split('\n'):
        match = re.match(pattern, line)
        if match:
            items.append(match.group(1))

    return items


def parse_stat_block(content: str) -> Dict:
    """
    Parse D&D stat block format (for monsters/NPCs)

    Example:
        ## Goblin
        *Small humanoid (goblinoid), neutral evil*
        **Armor Class** 15
        **Hit Points** 7 (2d6)
        **Speed** 30 ft.

    Returns:
        Dictionary with parsed stats
    """
    stats = {}

    # Extract creature name
    name_match = re.search(r'^##\s+(.+)$', content, re.MULTILINE)
    if name_match:
        stats['name'] = name_match.group(1)

    # Extract type/alignment line (italics)
    type_match = re.search(r'\*(.+?)\*', content)
    if type_match:
        stats['type'] = type_match.group(1)

    # Extract bolded stat lines
    bold_stats = re.findall(r'\*\*(.+?)\*\*\s+(.+)', content)
    for key, value in bold_stats:
        stats[key.lower().replace(' ', '_')] = value.strip()

    return stats
