import threading
import time
from functools import wraps

def access_aware(cls):
    class AccessAwareWrapper:
        def __init__(self, wrapped, auto_remove_timeout, close_callback=None):
            self._wrapped = wrapped 
            self._last_accessed = time.time()
            self._auto_remove = auto_remove_timeout is not None
            self._timeout = auto_remove_timeout
            self.close_callback = close_callback  # Store the callback
            if self._auto_remove:
                self._monitor_thread = threading.Thread(target=self._monitor_object, daemon=True)
                self._monitor_thread.start()

        def _monitor_object(self):
            while True:
                time.sleep(1)  # Check every second
                if self._auto_remove and self.check_timeout():
                    # If a close_callback is defined, call it
                    if self.close_callback:
                        try:
                            self.close_callback()  # Call the callback
                        except Exception as e:
                            # Log or handle the exception as required
                            return f"An error occurred during callback: {e}"
                    
                    try:
                        self._wrapped.stop()
                    except Exception:
                        continue # why care? we are removing it anyway

                    # If the wrapped object has a __del__ method, call it
                    if self._wrapped and hasattr(self._wrapped, '__del__'):
                        try:
                            self._wrapped.__del__()
                        except Exception as e:
                            # Log or handle the exception as required
                            return f"An error occurred during deletion: {e}"

                    # Remove the strong reference to the wrapped object. this makes it go bye bye.
                    self._wrapped = None
                    break

        def touch(self):
            self._last_accessed = time.time()

        def check_timeout(self):
            return time.time() - self._last_accessed > self._timeout

        def __getattr__(self, attr):
            if self._wrapped is None:
                raise ValueError("Object has been removed due to inactivity.")
            self.touch()  # Update last accessed time
            return getattr(self._wrapped, attr)  # Use the actual object here

        def __del__(self):
            if self._auto_remove:
                self._monitor_thread.join()  # Ensure the monitoring thread is cleaned up

    @wraps(cls)
    def wrapper(*args, **kwargs):
        auto_remove_timeout = kwargs.pop('auto_remove_timeout', None)  # Extract the auto_remove_timeout argument
        close_callback = kwargs.pop('close_callback', None)  # Extract the close_callback argument
        obj = cls(*args, **kwargs)  # Create an instance of the original class
        return AccessAwareWrapper(obj, auto_remove_timeout, close_callback)  # Wrap it
    return wrapper
