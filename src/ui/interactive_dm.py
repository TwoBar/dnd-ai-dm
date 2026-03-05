#!/usr/bin/env python3
"""Interactive DM with Rich UI"""
import re
from datetime import datetime

from rich.console import Console
from rich.prompt import Prompt
from rich.live import Live

from ui.terminal_ui import TerminalUI
from ui.game_state import Character, Monster, DiceRoll
from agent.dm_agent_v2 import DMAgentV2
from tools.dice_tools import roll_dice, roll_attack, roll_damage, roll_saving_throw


class InteractiveDM:
    """Interactive DM session with UI"""

    def __init__(self):
        self.console = Console()
        self.ui = TerminalUI()
        self.dm_agent = DMAgentV2()
        self.ui.dm_agent = self.dm_agent
        self.running = True

    def parse_command(self, user_input: str) -> bool:
        """
        Parse and execute commands

        Returns:
            True if command was handled, False if it should be sent to DM
        """
        if not user_input.startswith("/"):
            return False

        parts = user_input.split()
        cmd = parts[0].lower()

        try:
            if cmd == "/quit" or cmd == "/exit":
                self.running = False
                return True

            elif cmd == "/help":
                help_text = self.ui.show_help()
                self.ui.add_message("System", help_text)
                return True

            elif cmd == "/stats":
                from tools.entity_tools import get_cache_stats
                stats = get_cache_stats()
                context_size = self.dm_agent.get_context_size()
                stats_msg = f"""Cache Statistics:
  Size: {stats['size']}/100
  Hits: {stats['hits']}
  Misses: {stats['misses']}
  Hit Rate: {stats['hit_rate']}

Context Size: ~{context_size} tokens"""
                self.ui.add_message("System", stats_msg)
                return True

            elif cmd == "/add":
                return self._handle_add(parts[1:])

            elif cmd == "/combat":
                return self._handle_combat(parts[1:])

            elif cmd == "/init":
                return self._handle_initiative(parts[1:])

            elif cmd == "/damage":
                return self._handle_damage(parts[1:])

            elif cmd == "/heal":
                return self._handle_heal(parts[1:])

            elif cmd == "/roll":
                return self._handle_roll(parts[1:])

            elif cmd == "/next":
                self.ui.game_state.next_turn()
                turn = self.ui.game_state.current_turn
                self.ui.add_message("System", f"It's now {turn}'s turn!")
                return True

            elif cmd == "/condition":
                return self._handle_condition(parts[1:])

            else:
                self.ui.add_message("System", f"Unknown command: {cmd}. Type /help for available commands.")
                return True

        except Exception as e:
            self.ui.add_message("System", f"Error executing command: {e}")
            return True

    def _handle_add(self, args: list) -> bool:
        """Handle /add command"""
        if len(args) < 2:
            self.ui.add_message("System", "Usage: /add char <name> <class> <level> <hp> <ac> OR /add monster <name> <hp> <ac> <cr>")
            return True

        entity_type = args[0].lower()

        if entity_type in ["char", "character"]:
            # /add char Gandalf Wizard 5 38 15
            if len(args) < 6:
                self.ui.add_message("System", "Usage: /add char <name> <class> <level> <hp> <ac>")
                return True

            name = args[1]
            class_name = args[2]
            level = int(args[3])
            hp = int(args[4])
            ac = int(args[5])

            char = Character(name=name, class_name=class_name, level=level, hp=hp, max_hp=hp, ac=ac)
            self.ui.game_state.add_character(char)
            self.ui.add_message("System", f"Added character: {char.to_display()}")

        elif entity_type in ["mon", "monster"]:
            # /add monster Goblin 7 15 0.25
            if len(args) < 5:
                self.ui.add_message("System", "Usage: /add monster <name> <hp> <ac> <cr>")
                return True

            name = args[1]
            hp = int(args[2])
            ac = int(args[3])
            cr = float(args[4])

            monster = Monster(name=name, hp=hp, max_hp=hp, ac=ac, cr=cr)
            self.ui.game_state.add_monster(monster)
            self.ui.add_message("System", f"Added monster: {monster.to_display()}")

        else:
            self.ui.add_message("System", f"Unknown entity type: {entity_type}. Use 'char' or 'monster'.")

        return True

    def _handle_combat(self, args: list) -> bool:
        """Handle /combat command"""
        if not args:
            self.ui.add_message("System", "Usage: /combat start|end")
            return True

        action = args[0].lower()

        if action == "start":
            self.ui.game_state.start_combat()
            self.ui.add_message("System", "⚔️  Combat started! Roll initiative for all combatants.")
        elif action == "end":
            self.ui.game_state.end_combat()
            self.ui.add_message("System", "Combat ended.")
        else:
            self.ui.add_message("System", f"Unknown combat action: {action}. Use 'start' or 'end'.")

        return True

    def _handle_initiative(self, args: list) -> bool:
        """Handle /init command"""
        # /init Gandalf 18
        if len(args) < 2:
            self.ui.add_message("System", "Usage: /init <name> <roll>")
            return True

        name = args[0]
        init_roll = int(args[1])

        # Find character or monster
        for char in self.ui.game_state.characters:
            if char.name.lower() == name.lower():
                char.initiative = init_roll
                self.ui.add_message("System", f"{name} rolled {init_roll} for initiative.")
                return True

        for monster in self.ui.game_state.monsters:
            if monster.name.lower() == name.lower():
                monster.initiative = init_roll
                self.ui.add_message("System", f"{name} rolled {init_roll} for initiative.")
                return True

        self.ui.add_message("System", f"Character or monster '{name}' not found.")
        return True

    def _handle_damage(self, args: list) -> bool:
        """Handle /damage command"""
        # /damage Goblin 15
        if len(args) < 2:
            self.ui.add_message("System", "Usage: /damage <name> <amount>")
            return True

        name = args[0]
        damage = int(args[1])

        # Check if character
        for char in self.ui.game_state.characters:
            if char.name.lower() == name.lower():
                self.ui.game_state.damage_character(name, damage)
                return True

        # Check if monster
        for monster in self.ui.game_state.monsters:
            if monster.name.lower() == name.lower():
                self.ui.game_state.damage_monster(name, damage)
                return True

        self.ui.add_message("System", f"Character or monster '{name}' not found.")
        return True

    def _handle_heal(self, args: list) -> bool:
        """Handle /heal command"""
        # /heal Gandalf 10
        if len(args) < 2:
            self.ui.add_message("System", "Usage: /heal <name> <amount>")
            return True

        name = args[0]
        healing = int(args[1])

        self.ui.game_state.heal_character(name, healing)
        return True

    def _handle_roll(self, args: list) -> bool:
        """Handle /roll command"""
        # /roll 2d6+3
        if not args:
            self.ui.add_message("System", "Usage: /roll <notation> (e.g., 2d6+3, 1d20+5)")
            return True

        notation = args[0]
        result = roll_dice(notation)

        if "error" in result:
            self.ui.add_message("System", f"Error rolling dice: {result['error']}")
        else:
            # Log the roll
            self.ui.log_dice_roll(
                roll_type="manual",
                notation=notation,
                result=result['total'],
                description=notation,
                critical=result.get('is_critical', False),
                fumble=result.get('is_fumble', False)
            )

            self.ui.add_message("System", f"🎲 {result['description']}")

        return True

    def _handle_condition(self, args: list) -> bool:
        """Handle /condition command"""
        # /condition add Gandalf poisoned
        # /condition remove Gandalf poisoned
        if len(args) < 3:
            self.ui.add_message("System", "Usage: /condition add|remove <name> <condition>")
            return True

        action = args[0].lower()
        name = args[1]
        condition = args[2]

        # Find entity
        entity = None
        for char in self.ui.game_state.characters:
            if char.name.lower() == name.lower():
                entity = char
                break

        if not entity:
            for monster in self.ui.game_state.monsters:
                if monster.name.lower() == name.lower():
                    entity = monster
                    break

        if not entity:
            self.ui.add_message("System", f"Character or monster '{name}' not found.")
            return True

        if action == "add":
            if condition not in entity.conditions:
                entity.conditions.append(condition)
                self.ui.add_message("System", f"Added condition '{condition}' to {name}.")
        elif action == "remove":
            if condition in entity.conditions:
                entity.conditions.remove(condition)
                self.ui.add_message("System", f"Removed condition '{condition}' from {name}.")
        else:
            self.ui.add_message("System", f"Unknown action: {action}. Use 'add' or 'remove'.")

        return True

    def send_to_dm(self, user_input: str):
        """Send message to DM agent and get response"""
        self.ui.add_message("You", user_input)

        # Get DM response
        response = self.dm_agent.chat(user_input)

        # Parse response for automatic dice rolls
        self._extract_dice_rolls(response)

        self.ui.add_message("DM", response)

    def _extract_dice_rolls(self, text: str):
        """Extract and log dice rolls from DM response"""
        # Look for dice notation patterns in the response
        patterns = [
            r'(\d+d\d+(?:[+\-]\d+)?)\s*=\s*(\d+)',  # "2d6+3 = 11"
            r'rolled?\s+(\d+d\d+(?:[+\-]\d+)?)',     # "rolled 2d6+3"
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    notation, result = match
                    self.ui.log_dice_roll(
                        roll_type="dm",
                        notation=notation,
                        result=int(result),
                        description=f"DM rolled {notation}"
                    )

    def run(self):
        """Main interactive loop"""
        self.console.clear()

        # Welcome message
        self.ui.add_message("System", """Welcome to D&D AI Dungeon Master V2!

Type /help to see available commands.
Add characters and monsters, then start your adventure!

Example quick start:
  /add char Gandalf Wizard 5 38 15
  /add monster Goblin 7 15 0.25
  /combat start
  /init Gandalf 18
  /init Goblin 12

Then just chat with the DM naturally!""")

        # Render initial UI
        self.console.print(self.ui.render())
        self.console.print()

        while self.running:
            try:
                # Get user input
                user_input = Prompt.ask("[bold cyan]>[/bold cyan]").strip()

                if not user_input:
                    continue

                # Parse commands
                if self.parse_command(user_input):
                    # Clear and re-render
                    self.console.clear()
                    self.console.print(self.ui.render())
                    self.console.print()
                    continue

                # Send to DM
                self.send_to_dm(user_input)

                # Clear and re-render after DM response
                self.console.clear()
                self.console.print(self.ui.render())
                self.console.print()

            except KeyboardInterrupt:
                self.running = False
            except EOFError:
                self.running = False
            except Exception as e:
                self.ui.add_message("System", f"Error: {e}")
                import traceback
                traceback.print_exc()
                # Re-render on error
                self.console.clear()
                self.console.print(self.ui.render())
                self.console.print()

        self.console.print("\n[bold cyan]Thanks for playing! May your rolls be high! 🎲[/bold cyan]\n")


def main():
    """Entry point"""
    dm = InteractiveDM()
    dm.run()


if __name__ == "__main__":
    main()
