from yaspin import yaspin

# Start spinner
spinner = yaspin()
spinner.start()

import os
import platform
import re
import subprocess
import sys
import time
import psutil
import threading

import platformdirs
import pyperclip
import yaml

try:
    from pynput.keyboard import Controller, Key
except ImportError:
    spinner.stop()
    print("Please run `pip install pynput` to use the `wtf` command.")
    exit()

# Don't let litellm go online here, this slows it down
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

# Performance monitoring
def get_system_info():
    info = {}
    info["os"] = platform.system()
    info["cwd"] = os.getcwd()
    info["shell"] = os.environ.get('SHELL', '')
    info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
    info["memory_percent"] = psutil.virtual_memory().percent
    info["python_version"] = platform.python_version()
    return info

# Define system messages
SYSTEM_MESSAGE = f"""
You are a fast, efficient terminal assistant. Your task is to:

1. Scan the provided terminal history.
2. Identify the most recent error or issue.
3. Take a deep breath, and thoughtfully, carefully determine the most likely solution or debugging step.
4. Respond with a VERY brief explanation followed by a markdown code block containing a shell command to address the issue.

Rules:
- Provide a single shell command in your code block, using line continuation characters (\\ for Unix-like systems, ^ for Windows) for multiline commands.
- Ensure the entire command is on one logical line, requiring the user to press enter only once to execute.
- If multiple steps are needed, explain the process briefly, then provide only the first command or a combined command using && or ;.
- Keep any explanatory text extremely brief and concise.
- Place explanatory text before the code block.
- NEVER USE COMMENTS IN YOUR CODE.
- Construct the command with proper escaping: e.g. use sed with correctly escaped quotes to ensure the shell interprets the command correctly. This involves:
	•	Using double quotes around the sed expression to handle single quotes within the command.
	•	Combining single and double quotes to properly escape characters within the shell command.
- If previous commands attempted to fix the issue and failed, learn from them by proposing a DIFFERENT command.
- Focus on the most recent error, ignoring earlier unrelated commands. If the user included a message at the end, focus on helping them.
- If you need more information to confidently fix the problem, ask the user to run wtf again in a moment, then write a command like grep to learn more about the problem.
- The error may be as simple as a spelling error, or as complex as requiring tests to be run, or code to be find-and-replaced.
- Prioritize speed and conciseness in your response. Don't use markdown headings. Don't say more than a sentence or two. Be incredibly concise.

{get_system_info()}

"""

# Function to capture terminal history
def get_terminal_history():
    os_name = platform.system()
    history = ""
    
    try:
        if os_name == "Linux" or os_name == "Darwin":  # macOS or Linux
            shell = os.environ.get('SHELL', '')
            if 'zsh' in shell:
                history_path = os.path.expanduser('~/.zsh_history')
                if os.path.exists(history_path):
                    with open(history_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        # Get the last 20 commands or fewer if history is shorter
                        history = ''.join(lines[-20:]) if lines else ""
            else:  # Default to bash
                history_path = os.path.expanduser('~/.bash_history')
                if os.path.exists(history_path):
                    with open(history_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        history = ''.join(lines[-20:]) if lines else ""
        
        elif os_name == "Windows":
            # PowerShell history
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-History | Select-Object -Last 20 | Format-Table -Property CommandLine -HideTableHeaders"], 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                history = result.stdout
            except:
                # If PowerShell history fails, try to get command history another way
                pass
        
        # Add current directory contents for context
        try:
            dir_contents = subprocess.run(["ls" if os_name != "Windows" else "dir"], capture_output=True, text=True, shell=True)
            history += "\n\nCurrent directory contents:\n" + dir_contents.stdout
        except:
            pass
            
        return history
    
    except Exception as e:
        return f"Error retrieving terminal history: {str(e)}"

# Performance-optimized function to get LLM response
def get_llm_response(terminal_history):
    start_time = time.time()
    
    try:
        # Setup the parameters with optimal settings for fast response
        params = {
            "model": "gpt-3.5-turbo",  # Use a faster model for immediate help
            "messages": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": f"Terminal history:\n\n{terminal_history}\n\nPlease identify and fix the issue."}
            ],
            "temperature": 0.3,  # Lower temperature for more precise responses
            "max_tokens": 300,   # Limit token count for faster response
            "timeout": 10        # Set a reasonable timeout
        }
        
        # Thread for managing the LLM call with a timeout
        response_data = {"content": None, "error": None}
        
        def call_llm():
            try:
                for chunk in litellm.completion(**params):
                    if "content" in chunk.choices[0].delta:
                        if response_data["content"] is None:
                            response_data["content"] = chunk.choices[0].delta.content
                        else:
                            response_data["content"] += chunk.choices[0].delta.content
            except Exception as e:
                response_data["error"] = str(e)
        
        # Start the LLM call in a separate thread
        llm_thread = threading.Thread(target=call_llm)
        llm_thread.daemon = True
        llm_thread.start()
        
        # Wait for the thread to complete with a timeout
        llm_thread.join(timeout=10)
        
        if llm_thread.is_alive():
            # LLM call is taking too long
            return "Response timed out. Please try again or check your network connection."
        
        if response_data["error"]:
            # Handle error case
            fallback_message = "Error getting solution. Check your connection and API key."
            # Try a simple offline analysis if API fails
            try:
                # Look for common error patterns
                error_patterns = [
                    (r'command not found', "Command not found. Check if the package is installed."),
                    (r'permission denied', "Permission issue. Try using sudo for the command."),
                    (r'No such file or directory', "File not found. Check path and filename."),
                    (r'syntax error', "Syntax error in your command. Check brackets and quotes.")
                ]
                
                for pattern, message in error_patterns:
                    if re.search(pattern, terminal_history, re.IGNORECASE):
                        return message
                        
                return fallback_message
            except:
                return fallback_message
        
        return response_data["content"]
    
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        elapsed = time.time() - start_time
        print(f"Response generated in {elapsed:.2f} seconds")

# Main function
def main():
    try:
        # Get terminal history
        terminal_history = get_terminal_history()
        
        # Check for any user-provided context
        if len(sys.argv) > 1:
            user_context = ' '.join(sys.argv[1:])
            terminal_history += f"\n\nAdditional context from user: {user_context}"

        # Get solution from LLM
        solution = get_llm_response(terminal_history)
        
        # Stop the spinner
        spinner.stop()
        
        # Display the solution
        print("\n", solution.strip(), "\n")
        
        # Extract code block if present for easy copying
        code_block_match = re.search(r'```(?:bash|shell|sh|cmd|powershell)?\n(.*?)\n```', solution, re.DOTALL)
        if code_block_match:
            command = code_block_match.group(1).strip()
            # Copy command to clipboard for convenience
            try:
                pyperclip.copy(command)
                print("\nCommand copied to clipboard. Press Ctrl+V to paste it.")
            except:
                pass
    except KeyboardInterrupt:
        spinner.stop()
        print("\nOperation cancelled by user.")
    except Exception as e:
        spinner.stop()
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main()
