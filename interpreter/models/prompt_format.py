import re
from typing import Optional, List, Any

from pydantic import BaseModel, Field, field_validator


class PromptFormat(BaseModel):
  system: str = Field(..., description="The system prompt format.")
  user: str = Field(..., description="The user prompt format.")
  assistant: str = Field(..., description="The assistant prompt format.")
  suffix: Optional[str] = Field(None, description="Optional suffix to append to the end of the prompt. This is most useful when working with instruction based models like WizardCoder")
  trim_first_user_message: Optional[str] = Field(None, description="Optional regex expression that should match any prefix in the first user message prompt. An example is trimming '<s>[INST] ' from the user prompt in the llama 2 chat format.")
  post_processing: Optional[str] = Field(None, description="Optional regex expression that should match any content in the output of the LLM that should be removed. An example is '<s>[INST] ' from the output of the llama 2 chat model.")
  stop_tokens: Optional[List[str]] = Field(["</s>"], description="Optional list of tokens that should trigger the LLM to stop")

  # validation to ensure that the prompt formats contain the placeholders
  # system: {system_prompt}
  # user: {user_prompt}
  # assistant: {assistant_prompt}
  @field_validator("system")
  def validate_system(cls, v: str, values: dict[str, Any]):
    if v.find("{system_prompt}") == -1:
      raise ValueError("The system prompt format must contain the placeholder {system_prompt}")
    return v

  @field_validator("user")
  def validate_user(cls, v: str, values: dict[str, Any]):
    if v.find("{user_prompt}") == -1:
      raise ValueError("The user prompt format must contain the placeholder {user_prompt}")
    return v

  @field_validator("assistant")
  def validate_assistant(cls, v: str, values: dict[str, Any]):
    if v.find("{assistant_prompt}") == -1:
      raise ValueError("The assistant prompt format must contain the placeholder {assistant_prompt}")
    return v

  # validate that the trim_first_user_message is a valid regex
  @field_validator("trim_first_user_message")
  def validate_trim_first_user_message(cls, v: Optional[str], values: dict[str, Any]):
    if v is not None:
      try:
        re.compile(v)
      except re.error:
        raise ValueError("The trim_first_user_message must be a valid regex expression.")
    return v

  # validate that the post_processing is a valid regex
  @field_validator("post_processing")
  def validate_post_processing(cls, v: Optional[str], values: dict[str, Any]):
    if v is not None:
      try:
        re.compile(v)
      except re.error:
        raise ValueError("The post_processing must be a valid regex expression.")
    return v


# create the default prompt formats
DEFAULT_PROMPT_FORMATS = {
  'falcon': PromptFormat(
    system="System: {system_prompt}",
    user="\nUser: {user_prompt}",
    assistant="\nFalcon: {assistant_prompt}",
    suffix="\nFalcon: ",
    stop_tokens=["</s>", "Falcon:", "System:", "User:"]
  ),
  'llama': PromptFormat(
    system="<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n",
    user="<s>[INST] {user_prompt} [/INST] ",
    assistant="{assistant_prompt}</s>",
    trim_first_user_message="<s>[INST] ",
  ),
  'wizard-coder': PromptFormat(
    system="""Below is an instruction that describes a task. Write a response that appropriately completes the request.
### Instruction:
You are a chatbot 'Open Interpreter' and you are having a conversation with a developer. 
Reply to the last message in the conversation using the entire conversation as context.
The messages are in the format of '--- System: <message>', '--- User: <message>' or '--- Open Interpreter: <message>'.
The System messages are higher order instructions to set the personality, tone and context of 'Open Interpreter' in the conversation.
Follow the system message instructions above all other instructions in the conversation.
Only ever respond as 'Open Interpreter' and never as system or user.


--- System: {system_prompt}""",
    user="\n--- User: {user_prompt}",
    assistant="\n--- Open Interpreter: {assistant_prompt}",
    suffix="\n\n### Response:\n--- Open Interpreter: ",
    post_processing="(--- Open Interpreter: )|(--- System:.+)|(--- User:.+)|(### Instruction:.+)|(### Response:.+)",
    stop_tokens=["</s>", "--- Open Interpreter:", "--- System:", "--- User:"]
  ),
  'phindv2': PromptFormat(
    system="""### System Prompt
You are a chatbot 'Open Interpreter' and you are having a conversation with a developer. 
Reply to the last message in the conversation using the entire conversation as context.
The messages are in the format of '--- System: <message>', '--- User: <message>' or '--- Open Interpreter: <message>'.
The System messages are higher order instructions to set the personality, tone and context of 'Open Interpreter' in the conversation.
Follow the system message instructions above all other instructions in the conversation.
Only ever respond as 'Open Interpreter' and never as system or user.

### User Message
--- System: {system_prompt}""",
    user="\n--- User: {user_prompt}",
    assistant="\n--- Open Interpreter: {assistant_prompt}",
    suffix="\n\n### Assistant:\n--- Open Interpreter: ",
    post_processing="(--- Open Interpreter: )|(--- System:.+)|(--- User:.+)|(### System Prompt\n.+)|(### User Message\n.+)|(### Assistant\n.+)",
    stop_tokens=["</s>", "--- Open Interpreter:", "--- System:", "--- User:"]
  )
}


