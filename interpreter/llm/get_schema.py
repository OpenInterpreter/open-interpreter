"""Function to enable / disable different lang based on operating system. """
import platform
import copy

BASE_FUNCTION_SCHEMA = {
  "name": "execute",
  "description":
  "Executes code on the user's machine, **in the users local environment**, and returns the output",
  "parameters": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        "description":
        "The programming language (required parameter to the `execute` function)",
        "enum": ["python", "R", "shell", "javascript", "html",]
      },
      "code": {
        "type": "string",
        "description": "The code to execute (required)"
      }
    },
    "required": ["language", "code"]
  },
}

def get_schema():
    # Detect the operating system
    os_type = platform.system().lower()

    # Define the base languages that are common to all supported operating systems
    base_languages = ["python", "R", "shell", "javascript", "html"]

    # Copy the schema to avoid modifying the original
    corrected_schema = copy.deepcopy(BASE_FUNCTION_SCHEMA)

    # Add 'powershell' if the OS is Windows, 'applescript' if macOS, or none if it's another OS
    if os_type == 'windows':
        base_languages.append('powershell')
    elif os_type == 'darwin':  # Darwin is the system name for macOS
        base_languages.append('applescript')

    corrected_schema['parameters']['properties']['language']['enum'] = base_languages

    return corrected_schema
