from typing import Any, Optional, TypedDict, Dict

class FunctionCall(TypedDict):
  arguments: str
  parsed_arguments: Dict[str, Any]
  language: str
  code: str

class Message(TypedDict, total=False):
  role: str
  content: str
  name: Optional[str]
  function_call: Optional[FunctionCall]