"""
Open Interpreter
===============

A natural language interface for your computer.

Basic Usage
----------
>>> from interpreter import Interpreter
>>> interpreter = Interpreter()
>>> interpreter.chat("Hello, what can you help me with?")

Configuration
------------
>>> from interpreter import Interpreter, Profile

Use defaults:

>>> interpreter = Interpreter()

Load from custom profile:

>>> profile = Profile.from_file("~/custom_profile.py")
>>> interpreter = Interpreter(profile)

Save current settings:

>>> interpreter.save_profile("~/my_settings.py")
"""

# Use lazy imports to avoid loading heavy modules immediately
from importlib import import_module

__version__ = "1.0.0"  # Single source of truth for version

def __getattr__(name):
    """Lazy load attributes only when they're actually requested"""
    if name in ["Interpreter", "Profile"]:
        if name == "Interpreter":
            return getattr(import_module(".interpreter", __package__), name)
        else:
            return getattr(import_module(".profiles", __package__), name)
    raise AttributeError(f"module '{__package__}' has no attribute '{name}'")


__all__ = ["Interpreter", "Profile"]
