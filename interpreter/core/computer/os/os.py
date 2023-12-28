import platform
import subprocess


class Os:
    def __init__(self, computer):
        self.computer = computer

    def get_selected_text(self):
        # Store the current clipboard content
        current_clipboard = self.computer.clipboard.view()
        # Copy the selected text to clipboard
        self.computer.clipboard.copy()
        # Get the selected text from clipboard
        selected_text = self.computer.clipboard.view()
        # Reset the clipboard to its original content
        self.computer.clipboard.copy(current_clipboard)
        return selected_text

    def notify(self, text):
        title = "Open Interpreter"

        if len(text) > 200:
            text = text[:200] + "..."

        if "darwin" in platform.system().lower():  # Check if the OS is macOS
            script = f'display notification "{text}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
        else:  # For other OS, use a general notification API
            try:
                import plyer

                plyer.notification.notify(title=title, message=text)
            except:
                # Optional package
                pass

    # Maybe run code should be here...?
