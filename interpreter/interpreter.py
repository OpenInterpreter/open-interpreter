import json
from .code_interpreter import run_code
from .view import View
from .json_utils import JsonDeltaCalculator
import openai
import tokentrim as tt
import os
import readline

functions = [{
  "name": "run_code",
  "description": "Executes code in various programming languages and returns the output.",
  "parameters": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        # Temporarily disabled javascript
        # "description": "The programming language. Supported languages: python, bash, javascript",
        # "enum": ["python", "bash", "javascript"]
        "description": "The programming language. Supported languages: python, bash",
        "enum": ["python", "bash"]
      },
      "code": {
        "type": "string",
        "description": "The code to execute."
      }
    },
    "required": ["language", "code"]
  },
  "function": run_code
}]

# Locate system_message.txt using the absolute path
# for the directory where this file is located ("here"):
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'system_message.txt'), 'r') as f:
  system_message = f.read().strip()


class Interpreter:

  def __init__(self):
    self.messages = []
    self.system_message = system_message
    self.temperature = 0.2
    self.api_key = None
    self.max_output_chars = 2000
    self.no_confirm = False
    self.code_interpreters = {}

    # Commands Open Interpreter cannot run
    with open('forbidden_commands.json', 'r') as f:
        self.forbidden_commands = json.load(f)

  def reset(self):
    self.messages = []

  def load(self, messages):
    self.messages = messages

  def chat(self, message=None, return_messages=False):
    self.verify_api_key()

    if message:
      self.messages.append({"role": "user", "content": message})
      self.respond()

    else:
      print("Type 'exit' to leave the chat.\n")

      while True:
        try:
          user_input = input("> ").strip()
        except EOFError:
          break

        if user_input == 'exit' or user_input == 'exit()':
          break

        readline.add_history(user_input)  # add input to the readline history
        self.messages.append({"role": "user", "content": user_input})
        self.respond()

    if return_messages:
      return self.messages

  def display(self, delta):

    if delta == None:
      return

    if "content" in delta and delta["content"] != None:
      delta = {"type": "message", "content": delta["content"]}
    elif "function_call" in delta:
      delta = {"type": "function", "content": delta["function_call"]}

    self.view.process_delta(delta)

  def verify_api_key(self):
    if self.api_key == None:
      if 'OPENAI_API_KEY' in os.environ:
        self.api_key = os.environ['OPENAI_API_KEY']
      else:
        print("""OpenAI API key not found.
                
To use Open Interpreter in your terminal, set the environment variable using 'export OPENAI_API_KEY=your_api_key' in Unix-based systems, or 'setx OPENAI_API_KEY your_api_key' in Windows.

To get an API key, visit https://platform.openai.com/account/api-keys.
""")
        self.api_key = input(
          """Please enter an OpenAI API key for this session:\n""").strip()

  def respond(self):

    # You always need a new view.
    self.view = View()

    try:

      # make openai call
      gpt_functions = [{k: v
                        for k, v in d.items() if k != 'function'}
                       for d in functions]

      model = "gpt-4-0613"
      response = openai.ChatCompletion.create(
          model=model,
          messages=tt.trim(self.messages, model, system_message=self.system_message),
          functions=gpt_functions,
          stream=True,
          temperature=self.temperature,
      )

      base_event = {"role": "assistant", "content": ""}
      event = base_event

      func_call = {
        "name": None,
        "arguments": "",
      }

      for chunk in response:

        delta = chunk.choices[0].delta

        if "function_call" in delta:
          if "name" in delta.function_call:

            # New event!
            if event != base_event:
              self.messages.append(event)
            event = {"role": "assistant", "content": None}

            func_call["name"] = delta.function_call["name"]
            self.display(delta)

            delta_calculator = JsonDeltaCalculator()

          if "arguments" in delta.function_call:
            func_call["arguments"] += delta.function_call["arguments"]

            argument_delta = delta_calculator.receive_chunk(
              delta.function_call["arguments"])

            # Reassemble it as though OpenAI did this properly

            if argument_delta != None:
              self.display({"content": None, "function_call": argument_delta})

        if chunk.choices[0].finish_reason == "function_call":

          event["function_call"] = func_call
          self.messages.append(event)

          # For interpreter
          if func_call["name"] != "run_code":
            func_call["name"] = "run_code"

          function = [f for f in functions
                      if f["name"] == func_call["name"]][0]["function"]

          # For interpreter. Sometimes it just sends the code??
          try:
            function_args = json.loads(func_call["arguments"])
          except:
            function_args = {"code": func_call["arguments"]}

          # For interpreter. This should always be true:
          if func_call["name"] == "run_code" and False:
            # Pass in max_output_chars to truncate the output
            function_args["max_output_chars"] = self.max_output_chars
            # Pass in forbidden_commands
            function_args["forbidden_commands"] = self.forbidden_commands

          function_args["code_interpreters"] = self.code_interpreters

          user_declined = False
          
          if self.no_confirm == False:
            # Ask the user for confirmation
            print("\n")
            response = input("  Would you like to run this code? (y/n) ")
            print("\n")
            if response.lower().strip() != "y":
              user_declined = True
            else:
              user_declined = False

          if user_declined:
            output = "The user you're chatting with declined to run this code on their machine. It may be best to ask them why, or to try another method."
          else:
            
            # Clear live
            self.view.live.update("")
  
            # The output might use a rich Live display so we need to finalize ours.
            self.view.finalize()
            
            output = function(**function_args)

          event = {
            "role": "function",
            "name": func_call["name"],
            "content": output
          }
          self.messages.append(event)

          # Go around again
          if not user_declined:
            self.respond()

        if "content" in delta and delta.content != None:
          event["content"] += delta.content
          self.display(delta)

        if chunk.choices[0].finish_reason and chunk.choices[
            0].finish_reason != "function_call":
          self.messages.append(event)

    finally:
      self.view.finalize()
