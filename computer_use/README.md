- server
- tools [interpreter,editor,gui]
- allowed_commands
- allowed_paths
- system_message
- custom_instructions
- model
- api_base
- api_key
- api_version
- provider
- max_budget
- max_turns
- profile ~/.openinterpreter
- auto_run
- tool_calling

i --model ollama/llama3.2 --no-tool-calling --custom-instructions "
You can execute code by enclosing it in markdown code blocks."