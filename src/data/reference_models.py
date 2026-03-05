"""Entity system - Atomic objects with metadata"""
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from functools import lru_cache


@dataclass
class Entity:
    """Base entity class"""
    id: str
    type: str  # spell, monster, item, rule, condition, class_feature
    name: str
    tags: List[str]
    content: str
    metadata: Dict[str, Any]

    def to_dict(self):
        return asdict(self)

    def to_yaml(self):
        return yaml.dump(self.to_dict(), default_flow_style=False)


@dataclass
class Spell(Entity):
    """Spell entity"""
    level: int
    school: str
    classes: List[str]
    casting_time: str
    range: str
    components: str
    duration: str
    description: str
    higher_levels: Optional[str] = None
    damage: Optional[str] = None
    save: Optional[str] = None

    def to_dict(self):
        """Convert to dict with extra fields in metadata"""
        d = {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'tags': self.tags,
            'content': self.content,
            'level': self.level,
            'school': self.school,
            'classes': self.classes,
            'damage': self.damage,
            'save': self.save,
            'metadata': {
                **self.metadata,
                'casting_time': self.casting_time,
                'range': self.range,
                'components': self.components,
                'duration': self.duration,
                'description': self.description,
                'higher_levels': self.higher_levels
            }
        }
        return d

    @staticmethod
    def from_markdown(file_path: Path, content: str) -> 'Spell':
        """Parse spell from markdown"""
        import re

        name = file_path.stem.replace('-', ' ').title()

        # Extract level and school from first line
        # Example: "*3rd-level evocation*"
        level_match = re.search(r'\*(\d+)(?:st|nd|rd|th)?-level\s+(\w+)\*', content)
        level = int(level_match.group(1)) if level_match else 0
        school = level_match.group(2).capitalize() if level_match else "Unknown"

        # Extract metadata
        metadata = {}
        for pattern in [
            (r'\*\*Casting Time[:\s]+\*\*\s*([^\n]+)', 'casting_time'),
            (r'\*\*Range[:\s]+\*\*\s*([^\n]+)', 'range'),
            (r'\*\*Components[:\s]+\*\*\s*([^\n]+)', 'components'),
            (r'\*\*Duration[:\s]+\*\*\s*([^\n]+)', 'duration'),
        ]:
            match = re.search(pattern[0], content, re.IGNORECASE)
            metadata[pattern[1]] = match.group(1).strip() if match else "Unknown"

        # Extract description (everything between duration and higher levels)
        desc_match = re.search(r'\*\*Duration[:\s]+\*\*[^\n]+\n\n(.+?)(?:\*\*\*At Higher Levels|$)', content, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else content

        # Higher levels
        higher_match = re.search(r'\*\*\*At Higher Levels[:\.\s]+\*\*\*\s*(.+)', content, re.DOTALL)
        higher_levels = higher_match.group(1).strip() if higher_match else None

        # Detect damage and save type from description
        damage = None
        save = None

        damage_patterns = [
            r'(\d+d\d+(?:\s*\+\s*\d+)?)\s+(\w+)\s+damage',
            r'deals?\s+(\d+d\d+)(?:\s+(\w+))?\s+damage',
        ]
        for pattern in damage_patterns:
            dmg_match = re.search(pattern, description, re.IGNORECASE)
            if dmg_match:
                damage = dmg_match.group(1)
                break

        save_match = re.search(r'(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+saving throw', description, re.IGNORECASE)
        save = save_match.group(1).capitalize() if save_match else None

        # Extract classes (would need class lists from SRD, for now use common ones)
        classes = []
        for cls in ["Wizard", "Sorcerer", "Warlock", "Cleric", "Druid", "Bard", "Paladin", "Ranger"]:
            if cls.lower() in content.lower():
                classes.append(cls)

        # Generate tags
        tags = [school.lower(), f"level-{level}"]
        if damage:
            tags.append("damage")
        if save:
            tags.append("save")
        if "aoe" in description.lower() or "area" in description.lower():
            tags.append("aoe")
        if "concentration" in metadata['duration'].lower():
            tags.append("concentration")

        return Spell(
            id=f"spell:{name.lower().replace(' ', '_')}",
            type="spell",
            name=name,
            tags=tags,
            content=content,
            metadata=metadata,
            level=level,
            school=school,
            classes=classes,
            casting_time=metadata['casting_time'],
            range=metadata['range'],
            components=metadata['components'],
            duration=metadata['duration'],
            description=description,
            higher_levels=higher_levels,
            damage=damage,
            save=save
        )


@dataclass
class Monster(Entity):
    """Monster entity"""
    cr: float
    size: str
    type_alignment: str
    ac: int
    hp: str
    speed: str
    abilities: Dict[str, int]
    traits: List[str]
    actions: List[str]

    def to_dict(self):
        """Convert to dict with extra fields in metadata"""
        d = {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'tags': self.tags,
            'content': self.content,
            'cr': self.cr,
            'size': self.size,
            'ac': self.ac,
            'hp': self.hp,
            'metadata': {
                **self.metadata,
                'type_alignment': self.type_alignment,
                'speed': self.speed,
                'abilities': self.abilities,
                'traits': self.traits,
                'actions': self.actions
            }
        }
        return d

    @staticmethod
    def from_markdown(file_path: Path, content: str) -> 'Monster':
        """Parse monster from markdown"""
        import re

        name = file_path.stem.replace('-', ' ').title()

        # Extract type/alignment line
        type_match = re.search(r'\*(.+?)\*', content)
        type_alignment = type_match.group(1) if type_match else "Unknown"

        # Extract size
        size = "Medium"
        for s in ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]:
            if s in type_alignment:
                size = s
                break

        # Extract stats
        ac_match = re.search(r'\*\*Armor Class\*\*\s+(\d+)', content)
        ac = int(ac_match.group(1)) if ac_match else 10

        hp_match = re.search(r'\*\*Hit Points\*\*\s+([^\n]+)', content)
        hp = hp_match.group(1).strip() if hp_match else "0"

        speed_match = re.search(r'\*\*Speed\*\*\s+([^\n]+)', content)
        speed = speed_match.group(1).strip() if speed_match else "30 ft."

        # Extract CR
        cr_match = re.search(r'\*\*Challenge\*\*\s+(\d+(?:/\d+)?)', content)
        cr_str = cr_match.group(1) if cr_match else "0"
        cr = eval(cr_str) if '/' in cr_str else float(cr_str)

        # Extract ability scores (would need table parsing, simplified for now)
        abilities = {
            "STR": 10, "DEX": 10, "CON": 10,
            "INT": 10, "WIS": 10, "CHA": 10
        }

        # Extract traits and actions (simplified)
        traits = []
        actions = []

        # Generate tags
        tags = [size.lower(), f"cr-{int(cr)}"]
        if "undead" in type_alignment.lower():
            tags.append("undead")
        if "dragon" in type_alignment.lower() or "dragon" in name.lower():
            tags.append("dragon")

        return Monster(
            id=f"monster:{name.lower().replace(' ', '_')}",
            type="monster",
            name=name,
            tags=tags,
            content=content,
            metadata={"type_alignment": type_alignment},
            cr=cr,
            size=size,
            type_alignment=type_alignment,
            ac=ac,
            hp=hp,
            speed=speed,
            abilities=abilities,
            traits=traits,
            actions=actions
        )


@dataclass
class Rule(Entity):
    """Rule entity"""
    domain: str  # combat, magic, exploration, social
    category: str  # action, condition, mechanic

    @staticmethod
    def from_markdown(section_name: str, content: str, domain: str) -> 'Rule':
        """Parse rule from markdown section"""
        name = section_name.strip('#').strip()
        rule_id = f"rule:{domain}:{name.lower().replace(' ', '_')}"

        # Determine category
        category = "mechanic"
        if "attack" in name.lower() or "damage" in name.lower():
            category = "action"
        elif "condition" in name.lower() or "status" in name.lower():
            category = "condition"

        # Generate tags
        tags = [domain, category]
        if "advantage" in content.lower():
            tags.append("advantage")
        if "saving throw" in content.lower():
            tags.append("saving_throw")

        return Rule(
            id=rule_id,
            type="rule",
            name=name,
            tags=tags,
            content=content,
            metadata={"source_file": domain},
            domain=domain,
            category=category
        )


@dataclass
class Item(Entity):
    """Magic item entity"""
    rarity: str
    attunement: bool
    item_type: str  # weapon, armor, wondrous, potion, etc.

    def to_dict(self):
        """Convert to dict with extra fields in metadata"""
        d = {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'tags': self.tags,
            'content': self.content,
            'rarity': self.rarity,
            'item_type': self.item_type,
            'metadata': {
                **self.metadata,
                'attunement': self.attunement
            }
        }
        return d

    @staticmethod
    def from_markdown(file_path: Path, content: str) -> 'Item':
        """Parse item from markdown"""
        import re

        name = file_path.stem.replace('-', ' ').title()

        # Extract rarity
        rarity = "Common"
        for r in ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact"]:
            if r.lower() in content.lower():
                rarity = r
                break

        # Check attunement
        attunement = "attunement" in content.lower()

        # Determine item type
        item_type = "wondrous"
        if "weapon" in content.lower():
            item_type = "weapon"
        elif "armor" in content.lower():
            item_type = "armor"
        elif "potion" in content.lower():
            item_type = "potion"
        elif "scroll" in content.lower():
            item_type = "scroll"

        tags = [rarity.lower().replace(" ", "_"), item_type]
        if attunement:
            tags.append("attunement")

        return Item(
            id=f"item:{name.lower().replace(' ', '_')}",
            type="item",
            name=name,
            tags=tags,
            content=content,
            metadata={},
            rarity=rarity,
            attunement=attunement,
            item_type=item_type
        )


class EntityCache:
    """LRU cache for entities"""

    def __init__(self, maxsize: int = 100):
        self._cache = {}
        self._access_order = []
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Entity]:
        """Get entity from cache"""
        if key in self._cache:
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            self.hits += 1
            return self._cache[key]

        self.misses += 1
        return None

    def put(self, key: str, entity: Entity):
        """Add entity to cache"""
        if key in self._cache:
            # Update existing
            self._access_order.remove(key)
            self._access_order.append(key)
            self._cache[key] = entity
        else:
            # Add new
            if len(self._cache) >= self.maxsize:
                # Evict least recently used
                lru_key = self._access_order.pop(0)
                del self._cache[lru_key]

            self._cache[key] = entity
            self._access_order.append(key)

    def clear(self):
        """Clear cache"""
        self._cache.clear()
        self._access_order.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }
