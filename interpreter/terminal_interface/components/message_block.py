from rich.panel import Panel
from rich.markdown import Markdown
from rich.box import MINIMAL
import re
from .base_block import BaseBlock

class MessageBlock(BaseBlock):

  def __init__(self):
    super().__init__()

    self.type = "message"
    self.message = ""
    self.has_run = False

  def refresh(self, cursor=True):
    # De-stylize any code blocks in markdown,
    # to differentiate from our Code Blocks
    content = textify_markdown_code_blocks(self.message)
    
    if cursor:
      content += "█"
      
    markdown = Markdown(content.strip())
    panel = Panel(markdown, box=MINIMAL)
    self.live.update(panel)
    self.live.refresh()


def textify_markdown_code_blocks(text):
  """
  To distinguish CodeBlocks from markdown code, we simply turn all markdown code
  (like '```python...') into text code blocks ('```text') which makes the code black and white.
  """
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
