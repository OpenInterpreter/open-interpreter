import pyautogui
import pyperclip


class Clipboard:
    def get_selected_text(self):
        # Store the current clipboard content
        current_clipboard = pyperclip.paste()
        # Copy the selected text to clipboard
        pyautogui.hotkey("ctrl", "c", interval=0.15)
        # Get the selected text from clipboard
        selected_text = pyperclip.paste()
        # Reset the clipboard to its original content
        pyperclip.copy(current_clipboard)
        return selected_text
