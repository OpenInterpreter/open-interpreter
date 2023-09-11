#import threading
#from pynput import keyboard

# Removed due to issues with pynput and automatic checks. Will revisit.

'''
class HotkeyHandler:
    # Uses pynput.keyboard to listen for key presses. Calls a callback function if the key combination defined
    # gets pressed. This works in the background as its own thread.
    # Needs to be instantiated with key combination and callback function as parameters

    def __init__(self, key_combination, callback_function):
        self.key_combination = key_combination
        self.current_keys = set()
        self.callback_function = callback_function

        self.listener_thread = threading.Thread(target=self.start_key_listener)
        self.listener_thread.daemon = True  # This makes the thread terminate when the main program exits

    # Detect keypress, check if it's the combination.
    def on_press(self, key):
        if key in self.key_combination:
            self.current_keys.add(key)
            if all(k in self.current_keys for k in self.key_combination):
                self.callback_function()

    # Remove key from current_keys once released, so that keys don't get stuck.
    def on_release(self, key):
        try:
            self.current_keys.remove(key)
        except KeyError:
            pass

    # Start listening to hotkey combo
    def start_key_listener(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()

    def start(self):
        # Start the listener thread in the background
        self.listener_thread.start()'''