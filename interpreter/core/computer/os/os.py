import platform


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
        # Notification title
        title = "Open Interpreter"

        if "darwin" in platform.system().lower():  # Check if the OS is macOS
            script = f'display notification "{text}" with title "{title}"'
            self.computer.terminal.run("applescript", script)
        else:  # For other OS, use a general notification API
            import plyer

            plyer.notification.notify(title=title, message=text)

    # Maybe run code should be here...?
