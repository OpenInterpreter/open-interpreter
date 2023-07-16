from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.box import MINIMAL
import re

def textify_markdown_code_blocks(text):
    replacement = "```text"
    lines = text.split('\n')
    inside_code_block = False
    
    for i in range(len(lines)):
        # If the line matches ``` followed by optional language specifier
        if re.match(r'^```(\w*)$', lines[i].strip()):
            inside_code_block = not inside_code_block

            # If we just entered a code block, replace the marker
            if inside_code_block:
                lines[i] = replacement

    return '\n'.join(lines)

class View:
    def __init__(self):
        self.console = Console()
        self.live = None
        self.current_type = None
        self.current_content = ""

    def process_delta(self, event):

        try:
            event_type = event["type"]
            data = event["content"]

            if event_type == 'message':
                content = data
                display_type = 'message'
            elif event_type == 'function':
                if 'code' in data:
                    content = data['code']
                    display_type = 'code'
                else:
                  return
                # elif 'name' in data:
                #     content = data['name']
                #     display_type = 'name'
                # elif 'output' in data:
                #     content = data['output']
                #     display_type = 'output'

            if (event_type, display_type) != self.current_type:

                if display_type == 'code' and self.current_type == None:
                  # If it just became code after we just got here, print some whitespace
                  # (This is after user messages and other code blocks)
                  self.console.print("\n")

                if self.live is not None:
                    self.live.stop()
                self.live = Live(console=self.console, auto_refresh=False)
                self.live.start()
                self.current_type = (event_type, display_type)
                self.current_content = content
            else:
                self.current_content += content

            if display_type == 'message':
                markdown = Markdown(textify_markdown_code_blocks(self.current_content))
                current_display = Panel(markdown, box=MINIMAL)
            elif display_type == 'code':
                syntax = Syntax(self.current_content, "python", theme="monokai")
                current_display = Panel(syntax, box=MINIMAL, style="on #272722")
            # elif display_type == 'name':
            #     markdown = Markdown("# " + self.current_content)
            #     current_display = Panel(markdown, box=MINIMAL)
            # elif display_type == 'output':
            #     current_display = Panel(self.current_content, box=MINIMAL, style=f"#FFFFFF on #3b3b37")

            self.live.update(current_display, refresh=True)

        except Exception as e:
            # If an error occurs, stop the live display and raise the exception
            self.finalize()
            raise e

    def finalize(self):
        if self.live is not None:
            self.live.stop()