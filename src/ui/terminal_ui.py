"""Rich-based Terminal UI for D&D AI DM"""
from datetime import datetime
from typing import List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.prompt import Prompt
from rich import box

from ui.game_state import GameState, Character, Monster, DiceRoll, CombatEvent
from agent.dm_agent_v2 import DMAgentV2
from tools.entity_tools import get_cache_stats


class TerminalUI:
    """Rich-based terminal UI with multiple panels"""

    def __init__(self):
        self.console = Console()
        self.game_state = GameState()
        self.dm_agent: Optional[DMAgentV2] = None
        self.messages: List[tuple] = []  # (timestamp, speaker, message)
        self.layout = self._create_layout()

    def _create_layout(self) -> Layout:
        """Create the layout with multiple panels"""
        layout = Layout()

        # Split into main area and sidebar
        layout.split_row(
            Layout(name="main", ratio=2),
            Layout(name="sidebar", ratio=1)
        )

        # Split main into header, chat, and input
        layout["main"].split_column(
            Layout(name="header", size=3),
            Layout(name="chat", ratio=1),
            Layout(name="status", size=3)
        )

        # Split sidebar into stats and logs
        layout["sidebar"].split_column(
            Layout(name="stats", ratio=1),
            Layout(name="combat", size=12),
            Layout(name="dice_log", ratio=1)
        )

        return layout

    def _render_header(self) -> Panel:
        """Render header panel"""
        title = Text()
        title.append("🎲 D&D AI DUNGEON MASTER V2", style="bold cyan")
        title.append(" | Two-Stage Retrieval | Tool-Based Rules", style="dim")

        return Panel(
            title,
            border_style="cyan",
            box=box.DOUBLE
        )

    def _render_chat(self) -> Panel:
        """Render chat messages"""
        if not self.messages:
            content = Text("Welcome! Type your actions or questions...", style="dim italic")
        else:
            lines = []
            # Show last 20 messages
            for timestamp, speaker, message in self.messages[-20:]:
                time_str = timestamp.strftime("%H:%M:%S")

                if speaker == "You":
                    lines.append(Text(f"[{time_str}] ", style="dim"))
                    lines.append(Text("🧙 YOU: ", style="bold green"))
                    lines.append(Text(message + "\n\n", style="green"))
                elif speaker == "DM":
                    lines.append(Text(f"[{time_str}] ", style="dim"))
                    lines.append(Text("🎲 DM: ", style="bold magenta"))
                    lines.append(Text(message + "\n\n", style="magenta"))
                elif speaker == "System":
                    lines.append(Text(f"[{time_str}] ", style="dim"))
                    lines.append(Text("⚙️  ", style="yellow"))
                    lines.append(Text(message + "\n", style="yellow italic"))

            content = Group(*lines)

        return Panel(
            content,
            title="[bold]💬 Adventure Log[/bold]",
            border_style="blue",
            padding=(1, 2)
        )

    def _render_stats(self) -> Panel:
        """Render character and monster stats"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Info", style="cyan")

        if self.game_state.characters:
            table.add_row("[bold yellow]👥 Party:[/bold yellow]")
            for char in self.game_state.characters:
                hp_color = "green" if char.hp > char.max_hp * 0.5 else "yellow" if char.hp > char.max_hp * 0.25 else "red"
                table.add_row(f"[bold]{char.name}[/bold]")
                table.add_row(f"  Lvl {char.level} {char.class_name}")
                table.add_row(f"  HP: [{hp_color}]{char.hp}/{char.max_hp}[/{hp_color}] | AC: {char.ac}")
                if char.conditions:
                    table.add_row(f"  [{', '.join(char.conditions)}]", style="red italic")
                table.add_row("")

        if self.game_state.monsters:
            table.add_row("[bold red]⚔️  Enemies:[/bold red]")
            for monster in self.game_state.monsters:
                hp_color = "green" if monster.hp > monster.max_hp * 0.5 else "yellow" if monster.hp > monster.max_hp * 0.25 else "red"
                table.add_row(f"[bold]{monster.name}[/bold]")
                table.add_row(f"  HP: [{hp_color}]{monster.hp}/{monster.max_hp}[/{hp_color}] | AC: {monster.ac}")
                table.add_row(f"  CR: {monster.cr}")
                if monster.conditions:
                    table.add_row(f"  [{', '.join(monster.conditions)}]", style="red italic")
                table.add_row("")

        if not self.game_state.characters and not self.game_state.monsters:
            table.add_row("[dim italic]No active characters or monsters[/dim italic]")

        return Panel(
            table,
            title="[bold]📊 Stats[/bold]",
            border_style="yellow"
        )

    def _render_combat(self) -> Panel:
        """Render combat tracker"""
        if not self.game_state.in_combat:
            content = Text("Not in combat", style="dim italic")
        else:
            table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
            table.add_column("Init", style="cyan", width=4)
            table.add_column("Name", style="bold")
            table.add_column("HP", style="green")

            initiative_order = self.game_state.get_initiative_order()

            for name, init, entity_type in initiative_order:
                # Find entity
                entity = None
                if entity_type == "character":
                    entity = next((c for c in self.game_state.characters if c.name == name), None)
                else:
                    entity = next((m for m in self.game_state.monsters if m.name == name), None)

                if entity:
                    # Highlight current turn
                    style = "bold yellow" if name == self.game_state.current_turn else ""

                    hp_str = f"{entity.hp}/{entity.max_hp}"
                    if entity.hp == 0:
                        hp_str = "[red]DEAD[/red]"
                    elif entity.hp < entity.max_hp * 0.25:
                        hp_str = f"[red]{hp_str}[/red]"
                    elif entity.hp < entity.max_hp * 0.5:
                        hp_str = f"[yellow]{hp_str}[/yellow]"

                    marker = "→ " if name == self.game_state.current_turn else "  "
                    table.add_row(
                        str(init),
                        f"{marker}{name}",
                        hp_str,
                        style=style
                    )

            round_text = Text(f"Round {self.game_state.round_number}", style="bold cyan")
            content = Group(round_text, "", table)

        return Panel(
            content,
            title="[bold]⚔️  Initiative[/bold]",
            border_style="red"
        )

    def _render_dice_log(self) -> Panel:
        """Render dice roll log"""
        if not self.game_state.dice_rolls:
            content = Text("No dice rolls yet", style="dim italic")
        else:
            lines = []
            # Show last 10 rolls
            for roll in self.game_state.dice_rolls[-10:]:
                time_str = roll.timestamp.strftime("%H:%M")

                if roll.critical:
                    style = "bold green"
                    icon = "🎉"
                elif roll.fumble:
                    style = "bold red"
                    icon = "💀"
                else:
                    style = "white"
                    icon = "🎲"

                lines.append(Text(f"[{time_str}] {icon} ", style="dim"))
                lines.append(Text(f"{roll.notation} = {roll.result}", style=style))
                lines.append(Text("\n"))

            content = Group(*lines)

        return Panel(
            content,
            title="[bold]🎲 Dice Rolls[/bold]",
            border_style="green"
        )

    def _render_status(self) -> Panel:
        """Render status bar"""
        stats = self.game_state.get_stats_summary()
        cache_stats = get_cache_stats()

        status_text = Text()
        status_text.append(f"Characters: {stats['characters']} ", style="cyan")
        status_text.append(f"| Monsters: {stats['monsters']} ", style="red")

        if stats['in_combat']:
            status_text.append(f"| Round: {stats['round']} ", style="yellow")
            status_text.append(f"| Turn: {stats['current_turn']} ", style="green")

        status_text.append(f"| Cache: {cache_stats['hit_rate']} ", style="magenta")
        status_text.append(f"| Rolls: {stats['total_rolls']}", style="blue")

        return Panel(
            status_text,
            border_style="dim"
        )

    def render(self) -> Layout:
        """Render all panels"""
        self.layout["header"].update(self._render_header())
        self.layout["chat"].update(self._render_chat())
        self.layout["stats"].update(self._render_stats())
        self.layout["combat"].update(self._render_combat())
        self.layout["dice_log"].update(self._render_dice_log())
        self.layout["status"].update(self._render_status())
        return self.layout

    def add_message(self, speaker: str, message: str):
        """Add a message to the chat"""
        self.messages.append((datetime.now(), speaker, message))

    def log_dice_roll(self, roll_type: str, notation: str, result: int, description: str, critical: bool = False, fumble: bool = False):
        """Log a dice roll"""
        roll = DiceRoll(
            timestamp=datetime.now(),
            type=roll_type,
            notation=notation,
            result=result,
            description=description,
            critical=critical,
            fumble=fumble
        )
        self.game_state.log_dice_roll(roll)

    def show_help(self) -> str:
        """Show help commands"""
        help_text = """
[bold cyan]Commands:[/bold cyan]
  [green]/add char <name> <class> <level> <hp> <ac>[/green] - Add character
  [green]/add monster <name> <hp> <ac> <cr>[/green] - Add monster
  [green]/combat start[/green] - Start combat
  [green]/combat end[/green] - End combat
  [green]/init <name> <roll>[/green] - Set initiative
  [green]/damage <name> <amount>[/green] - Apply damage
  [green]/heal <name> <amount>[/green] - Heal character
  [green]/roll <notation>[/green] - Roll dice (e.g., 2d6+3)
  [green]/stats[/green] - Show cache statistics
  [green]/help[/green] - Show this help
  [green]/quit[/green] - Exit

[bold cyan]Examples:[/bold cyan]
  /add char Gandalf Wizard 5 38 15
  /add monster Goblin 7 15 0.25
  /combat start
  /init Gandalf 18
  /roll 1d20+5
  /damage Goblin 15
"""
        return help_text
