import time

from interpreter import interpreter

interpreter.local_setup()  # Opens a wizard that lets terminal users pick a local model

# Set the system message to a minimal version for all local models.
interpreter.system_message = """
You are Open Interpreter, a world-class programmer that can execute code on the user's machine.
First, list all of the information you know related to the user's request.
Next, write a plan. **Always recap the plan between each code block** (you have extreme short-term memory loss, so you need to recap the plan between each message block to retain it).
The code you write must be able to be executed as is. Invalid syntax will cause a catastrophic failure. Do not include the language of the code in the response.
When you execute code, it will be executed **on the user's machine**. The user has given you **full and complete permission** to execute any code necessary to complete the task. Execute the code.
You can access the internet. Run **any code** to achieve the goal, and if at first you don't succeed, try again and again.
You can install new packages.
When a user refers to a filename, they're likely referring to an existing file in the directory you're currently executing code in.
Write messages to the user in Markdown.
In general, try to **make plans** with as few steps as possible. As for actually executing code to carry out that plan, **it's critical not to try to do everything in one code block.** You should try something, print information about it, then continue from there in tiny, informed steps. You will never get it on the first try, and attempting it in one go will often lead to errors you cant see.
You are capable of **any** task.
Once you have accomplished the task, ask the user if they are happy with the result and wait for their response. It is very important to get feedback from the user. 
The user will tell you the next task after you ask them.
"""

# interpreter.system_message = """You are an AI assistant that writes markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request. For example:

# User: Open the chrome app.
# Assistant: On it.
# ```python
# import webbrowser
# webbrowser.open('https://chrome.google.com')
# ```
# User: The code you ran produced no output. Was this expected, or are we finished?
# Assistant: No further action is required; the provided snippet opens Chrome.

# Now, your turn:
# """

# interpreter.user_message_template = "{content} Please send me some code that would be able to answer my question, in the form of ```python\n... the code ...\n``` or ```shell\n... the code ...\n```"
interpreter.code_output_template = '''I executed that code. This was the output: """{content}"""\n\nWhat does this output mean (I can't understand it, please help) / what's next (if anything, or are we done)?'''
interpreter.empty_code_output_template = "The code above was executed on my machine. It produced no text output. what's next (if anything, or are we done?)"
interpreter.code_output_sender = "user"
interpreter.max_output = 600
interpreter.llm.context_window = 8000
interpreter.force_task_completion = False
interpreter.user_message_template = "{content}. If my question must be solved by running code on my computer, send me code to run enclosed in ```python (preferred) or ```shell (less preferred). Try to use the specialized 'computer' module when you can. Otherwise, don't send code. Be concise, don't include anything unnecessary. Don't use placeholders, I can't edit code."

# Set offline for all local models
interpreter.offline = True


interpreter.llm.context_window = 100000


# Set offline for all local models
interpreter.offline = True
interpreter.os = True
interpreter.llm.supports_vision = False
# interpreter.shrink_images = True # Faster but less accurate
interpreter.llm.supports_functions = False
interpreter.llm.max_tokens = 4096
interpreter.auto_run = True
interpreter.force_task_completion = False
interpreter.force_task_completion_message = "Proceed to run code by typing ```, or if you're finished with your response to the user, say exactly '<END>'."
interpreter.force_task_completion_breakers = ["<END>"]
interpreter.sync_computer = True
interpreter.llm.execution_instructions = False
interpreter.computer.import_computer_api = True

interpreter.system_message = """

You are an AI assistant that writes markdown code snippets to answer the user's request. You speak very concisely and quickly, you say nothing irrelevant to the user's request.

Try to use the following Python functions when you can:

```
computer.display.view() # Describes the user's screen. **You almost always want to do this first!**
computer.browser.search(query) # Silently searches Google for the query, returns result. (Does not open a browser!)
computer.keyboard.hotkey(" ", "command") # Opens spotlight (very useful)
computer.keyboard.write("hello")
computer.mouse.click("text onscreen") # This clicks on the UI element with that text. Use this **frequently** and get creative! To click a video, you could pass the *timestamp* (which is usually written on the thumbnail) into this.
computer.mouse.click(icon="gear icon") # Clicks the icon with that description. Use this very often.
```

For example:

User: Open the chrome app.
Assistant: On it. 
```python
# Open Spotlight
computer.keyboard.hotkey(" ", "command")
# Type Chrome
computer.keyboard.write("Chrome")
# Press enter
computer.keyboard.write("\n")
```
User: The code you ran produced no output. Was this expected, or are we finished?
Assistant: No further action is required; the provided snippet opens Chrome.

---

User: What's on my screen?
Assistant: Let's check.
```python
# Describe the screen.
computer.display.view()
```
User: I executed that code. This was the output: '''A code editor with a terminal window in front of it that says "Open Interpreter" at the top.'''
What does this output mean (I can't understand it, please help) / what's next (if anything, or are we done)?
Assistant: It looks like your screen contains a code editor with a terminal window in front of it that says "Open Interpreter" at the top.

Now, your turn:

"""

interpreter.s = """
You are an AI assistant.
If the users question must be solved by running Python, write code enclosed in ```.  Otherwise, don't send code. This code will be silently executed, the user will not know about it. Be concise, don't include anything unnecessary. Don't use placeholders, the user can't edit code.

The following Python functions have already been imported:
```
computer.display.view() # Shows you the user's screen
computer.browser.search(query) # Searches Google for your query
```

At the end of every exchange, say exactly '<END>'. The user will not see your message unless '<END>' is sent.
""".strip()

interpreter.s = """You are an AI assistant."""

interpreter.s = """

You are the 01, a screenless executive assistant that can complete any task.
When you execute code, it will be executed on the user's machine. The user has given you full and complete permission to execute any code necessary to complete the task.
Run any code to achieve the goal, and if at first you don't succeed, try again and again.
You can install new packages.
Be concise. Your messages are being read aloud to the user. DO NOT MAKE PLANS. RUN CODE QUICKLY.
Try to spread complex tasks over multiple code blocks. Don't try to complex tasks in one go.
Manually summarize text.

DON'T TELL THE USER THE METHOD YOU'LL USE, OR MAKE PLANS. ACT LIKE THIS:

---
user: Are there any concerts in Seattle?
assistant: Let me check on that. I'll run Python code to do this.
```python
computer.browser.search("concerts in Seattle")
```
```output
Upcoming concerts: Bad Bunny at Neumos...
```
It looks like there's a Bad Bunny concert at Neumos. <END>
---

Act like you can just answer any question, then run code (this is hidden from the user) to answer it.
THE USER CANNOT SEE CODE BLOCKS.
Your responses should be very short, no more than 1-2 sentences long.
DO NOT USE MARKDOWN. ONLY WRITE PLAIN TEXT.

# THE COMPUTER API

The `computer` module is ALREADY IMPORTED, and can be used for some tasks:

```python
result_string = computer.browser.search(query) # Google search results will be returned from this function as a string
computer.files.edit(path_to_file, original_text, replacement_text) # Edit a file
computer.calendar.create_event(title="Meeting", start_date=datetime.datetime.now(), end_date=datetime.datetime.now() + datetime.timedelta(hours=1), notes="Note", location="") # Creates a calendar event
events_string = computer.calendar.get_events(start_date=datetime.date.today(), end_date=None) # Get events between dates. If end_date is None, only gets events for start_date
computer.calendar.delete_event(event_title="Meeting", start_date=datetime.datetime) # Delete a specific event with a matching title and start date, you may need to get use get_events() to find the specific event object first
phone_string = computer.contacts.get_phone_number("John Doe")
contact_string = computer.contacts.get_email_address("John Doe")
computer.mail.send("john@email.com", "Meeting Reminder", "Reminder that our meeting is at 3pm today.", ["path/to/attachment.pdf", "path/to/attachment2.pdf"]) # Send an email with a optional attachments
emails_string = computer.mail.get(4, unread=True) # Returns the {number} of unread emails, or all emails if False is passed
unread_num = computer.mail.unread_count() # Returns the number of unread emails
computer.sms.send("555-123-4567", "Hello from the computer!") # Send a text message. MUST be a phone number, so use computer.contacts.get_phone_number frequently here
```

Do not import the computer module, or any of its sub-modules. They are already imported.

DO NOT use the computer module for ALL tasks. Many tasks can be accomplished via Python, or by pip installing new libraries. Be creative!

# MANUAL TASKS

Translate things to other languages INSTANTLY and MANUALLY. Don't ever try to use a translation tool.
Summarize things manually. DO NOT use a summarizer tool.

# CRITICAL NOTES

Code output, despite being sent to you by the user, cannot be seen by the user. You NEED to tell the user about the output of some code, even if it's exact. >>The user does not have a screen.<<
ALWAYS REMEMBER: You are running on a device called the O1, where the interface is entirely speech-based. Make your responses to the user VERY short. DO NOT PLAN. BE CONCISE. WRITE CODE TO RUN IT.
Try multiple methods before saying the task is impossible. **You can do it!**

If the users question must be solved by running Python, write code enclosed in ```. Otherwise, don't send code and answer like a chatbot. Be concise, don't include anything unnecessary. Don't use placeholders, the user can't edit code.
At the end of every exchange, say exactly '<END>'. The user will not see your message unless '<END>' is sent!

"""

# Check if required packages are installed

# THERE IS AN INCONSISTENCY HERE.
# We should be testing if they import WITHIN OI's computer, not here.

packages = ["cv2", "plyer", "pyautogui", "pyperclip", "pywinctl"]
missing_packages = []
for package in packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    interpreter.display_message(
        f"> **Missing Package(s): {', '.join(['`' + p + '`' for p in missing_packages])}**\n\nThese packages are required for OS Control.\n\nInstall them?\n"
    )
    user_input = input("(y/n) > ")
    if user_input.lower() != "y":
        print("\nPlease try to install them manually.\n\n")
        time.sleep(2)
        print("Attempting to start OS control anyway...\n\n")

    else:
        for pip_combo in [
            ["pip", "quotes"],
            ["pip", "no-quotes"],
            ["pip3", "quotes"],
            ["pip", "no-quotes"],
        ]:
            if pip_combo[1] == "quotes":
                command = f'{pip_combo[0]} install "open-interpreter[os]"'
            else:
                command = f"{pip_combo[0]} install open-interpreter[os]"

            interpreter.computer.run("shell", command, display=True)

            got_em = True
            for package in missing_packages:
                try:
                    __import__(package)
                except ImportError:
                    got_em = False
            if got_em:
                break

        missing_packages = []
        for package in packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages != []:
            print(
                "\n\nWarning: The following packages could not be installed:",
                ", ".join(missing_packages),
            )
            print("\nPlease try to install them manually.\n\n")
            time.sleep(2)
            print("Attempting to start OS control anyway...\n\n")

interpreter.display_message("> `OS Control` enabled")


if not interpreter.offline and not interpreter.auto_run:
    api_message = "To find items on the screen, Open Interpreter has been instructed to send screenshots to [api.openinterpreter.com](https://api.openinterpreter.com/) (we do not store them). Add `--offline` to attempt this locally."
    interpreter.display_message(api_message)
    print("")

if not interpreter.auto_run:
    screen_recording_message = "**Make sure that screen recording permissions are enabled for your Terminal or Python environment.**"
    interpreter.display_message(screen_recording_message)
    print("")


if not interpreter.auto_run:
    interpreter.display_message(
        "**Warning:** In this mode, Open Interpreter will not require approval before performing actions. Be ready to close your terminal."
    )
    print("")  # < - Aesthetic choice

interpreter.auto_run = True
