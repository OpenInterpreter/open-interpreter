from textual.app import App
from textual_terminal import Terminal

class TerminalApp(App):
    
    async def on_mount(self) -> None:
        # Create a layout with two terminals
        await self.layout.dock(Terminal(command="htop", id="terminal_htop"), edge="top", size=10)
        await self.layout.dock(Terminal(command="bash", id="terminal_bash"), edge="bottom")
    
    async def on_ready(self) -> None:
        # Start the commands in each terminal
        terminal_htop: Terminal = await self.get_widget("terminal_htop")
        await terminal_htop.start()

        terminal_bash: Terminal = await self.get_widget("terminal_bash")
        await terminal_bash.start()

app = TerminalApp()
app.run()
