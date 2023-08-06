from .code_interpreter import CodeInterpreter
from .code_block import CodeBlock
from .message_block import MessageBlock
from .json_utils import JsonAccumulator, close_and_parse_json
import openai
import tokentrim as tt
import os
import readline
from .cli import cli
from rich import print
from rich.markdown import Markdown

# Function schema for function-calling GPTs
function_schema = {
  "name": "run_code",
  "description":
  "Executes code in various programming languages and returns the output.",
  "parameters": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        "description":
        "The programming language. Supported languages: python, shell",
        "enum": ["python", "shell"]
      },
      "code": {
        "type": "string",
        "description": "The code to execute."
      }
    },
    "required": ["language", "code"]
  },
}

# Message for when users don't have an OpenAI API key.
# `---` is at the bottom for aesthetic reasons.
missing_api_key_message = """
**OpenAI API key not found.** You can [get one here](https://platform.openai.com/account/api-keys).

To use Open Interpreter in your terminal, set the environment variable using `export OPENAI_API_KEY=your_api_key` on Unix-based systems, or `setx OPENAI_API_KEY your_api_key` on Windows.

---
"""


class Interpreter:

  def __init__(self):
    self.messages = []
    self.system_message = self.generate_system_message()
    self.temperature = 0.01
    self.api_key = None
    self.auto_run = False

    # Store Code Interpreter instances for each language
    self.code_interpreters = {}

    # No active block to start
    # (blocks are visual representation of messages on the terminal)
    self.active_block = None

  def cli(self):
    # The cli takes the current instance of Interpreter,
    # modifies it according to command line flags, then runs chat.
    cli(self)

  def generate_system_message(self):
    """
    Adds relevent information to system_message.txt.
    """

    # First get the baseline system message from system_message.txt
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, 'system_message.txt'), 'r') as f:
      system_message = f.read().strip()

    return system_message

  def reset(self):
    self.messages = []
    self.code_interpreters = {}

  def load(self, messages):
    self.messages = messages

  def chat(self, message=None, return_messages=False):
    self.verify_api_key()

    # Message won't be None if we're passing one in via interpreter.chat(message)
    # In that case, we respond non-interactivley and return:
    if message:
      self.messages.append({"role": "user", "content": message})
      self.respond()
      return

    # Start interactive chat
    while True:
      try:
        user_input = input("> ").strip()
      except EOFError:
        break
      except KeyboardInterrupt:
        print()  # Aesthetic choice
        break

      # Use `readline` to let users up-arrow to previous user messages,
      # which is a common behavior in terminals.
      readline.add_history(user_input)

      # Add the user message to self.messages
      self.messages.append({"role": "user", "content": user_input})

      # Respond, but gracefully handle CTRL-C / KeyboardInterrupt
      try:
        self.respond()
      except KeyboardInterrupt:
        pass
      finally:
        # Always end the active block. Multiple Live displays = issues
        self.end_active_block()

    if return_messages:
      return self.messages

  def verify_api_key(self):
    """
    Makes sure we have an OPENAI_API_KEY.
    """

    if self.api_key == None:

      if 'OPENAI_API_KEY' in os.environ:
        self.api_key = os.environ['OPENAI_API_KEY']
      else:
        # Print message with newlines on either side (aesthetic choice)
        print('', Markdown(missing_api_key_message), '')
        self.api_key = input("Enter an OpenAI API key for this session:\n")

  def end_active_block(self):
    if self.active_block:
      self.active_block.end()
      self.active_block = None

  def respond(self):

    # Make OpenAI call
    model = "gpt-4-0613"
    response = openai.ChatCompletion.create(
      model=model,
      messages=tt.trim(self.messages,
                       model,
                       system_message=self.system_message),
      functions=[function_schema],
      stream=True,
      temperature=self.temperature,
    )

    # Initialize
    self.messages.append({})
    json_accumulator = JsonAccumulator()
    in_function_call = False
    self.active_block = None

    for chunk in response:

      delta = chunk.choices[0].delta

      # Accumulate deltas into the last message in messages
      json_accumulator.receive_delta(delta)
      self.messages[-1] = json_accumulator.accumulated_json

      # Check if we're in a function call
      if "function_call" in self.messages[-1]:

        # Check if we just entered a function call
        if in_function_call == False:

          # If so, end the last block,
          self.end_active_block()

          # Print newline if it was just a code block or user message
          # (this just looks nice)
          last_role = self.messages[-2]["role"]
          if last_role == "user" or last_role == "function":
            print()

          # then create a new code block
          self.active_block = CodeBlock()

        # Remember we're in a function_call
        in_function_call = True

        # Parse arguments and save to parsed_args, under function_call
        if "arguments" in self.messages[-1]["function_call"]:
          args = self.messages[-1]["function_call"]["arguments"]

          # There are some common errors made in GPT function calls.
          new_parsed_args = close_and_parse_json(args)

          if new_parsed_args:
            # Only overwrite what we have if it's not None (which means it failed to parse)
            self.messages[-1]["function_call"]["parsed_args"] = new_parsed_args

      else:

        # If we're not in a function call and there's no active block,
        if self.active_block == None:

          # Create a message block
          self.active_block = MessageBlock()

      # Update active_block
      self.active_block.update_from_message(self.messages[-1])

      # Check if we're finished
      if chunk.choices[0].finish_reason:
        if chunk.choices[0].finish_reason == "function_call":
          # Time to call the function!
          # (Because this is Open Interpreter, we only have one function.)

          # Ask for user confirmation to run code
          if self.auto_run == False:

            # End the active block so you can run input() below it
            # Save language and code so we can create a new block in a moment
            self.active_block.end()
            language = self.active_block.language
            code = self.active_block.code

            # Prompt user
            response = input("  Would you like to run this code? (y/n) \n\n  ")
            print("") # <- Aesthetic choice

            if response.lower() == "y":
              # Create a new, identical block where the code will actually be run
              self.active_block = CodeBlock()
              self.active_block.language = language
              self.active_block.code = code
              
            else:
              # User declined to run code.
              self.active_block.end()
              self.messages.append({
                "role":
                "function",
                "name":
                "run_code",
                "content":
                "User decided not to run this code."
              })
              return

          # Create or retrieve a Code Interpreter for this language
          language = self.messages[-1]["function_call"]["parsed_args"][
            "language"]
          if language not in self.code_interpreters:
            self.code_interpreters[language] = CodeInterpreter(language)
          code_interpreter = self.code_interpreters[language]

          # Let Code Interpreter control the active_block
          code_interpreter.active_block = self.active_block
          code_interpreter.run()

          # End the active_block
          self.active_block.end()

          # Append the output to messages
          self.messages.append({
            "role": "function",
            "name": "run_code",
            "content": self.active_block.output
          })

          # Go around again
          self.respond()

        if chunk.choices[0].finish_reason != "function_call":
          # Done!
          self.active_block.end()
          return
