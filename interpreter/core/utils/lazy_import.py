import importlib.util
import sys

def lazy_import(name, optional=True):
    """Lazily import a module, specified by the name. Useful for optional packages, to speed up startup times."""
    # Check if module is already imported
    if name in sys.modules:
        return sys.modules[name]

    # Find the module specification from the module name
    spec = importlib.util.find_spec(name)
    if spec is None:
        if optional:
            return None  # Do not raise an error if the module is optional
        else:
            raise ImportError(f"Module '{name}' cannot be found")

    # Use LazyLoader to defer the loading of the module
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader

    # Create a module from the spec and set it up for lazy loading
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)

    return module









# import threading

# class LazyImport:
#     def __init__(self, module_name):
#         self.module_name = module_name
#         self.module = None
#         self.lock = threading.RLock()

#     def __getattr__(self, name):
#         # Thread-safe import
#         with self.lock:
#             if self.module is None:
#                 try:
#                     self.module = __import__(self.module_name)
#                 except ImportError as e:
#                     raise ImportError(f"Failed to import module '{self.module_name}'. ""This may be due to a missing dependency.") from e
        
#         # Try to return the requested attribute
#         try:
#             return getattr(self.module, name)
#         except AttributeError as e:
#             raise AttributeError(f"Module '{self.module_name}' has no attribute '{name}'.") from e






# import threading
# import importlib

# class LazyImport:
#     """
#     A class for lazy loading Python modules. Modules are loaded only when an attribute is first accessed, improving startup time for OI when it uses heavy optional dependencies.
#     """
#     def __init__(self, module_name, optional=False, attributes=None):
#         """
#         Initialize the lazy loader with the name of the module to be lazily loaded.
        
#         :param module_name: The name of the module to load.
#         :param optional: Indicates if the module is optional.
#         :param attributes: A list of attribute names to load from the module.
#         """
#         self.module_name = module_name
#         self.module = None
#         self.optional = optional
#         self.attributes = attributes or []
#         # Lock to prevent multiple threads from loading the same module at the same time. Prevents race conditions!
#         # self.lock = threading.RLock() 


#     def __getattr__(self, item):
#         """
#         Called when an attribute of the LazyImport is accessed. If the module has not been loaded yet, it loads the module and returns a callable that safely calls the requested attribute. If loading fails, returns a stub method that does nothing but prints an error message.

#         :param item: The attribute name being accessed.
#         :return: A lambda function that calls the attribute, or a stub method if loading fails.
#         """
#         if item.startswith('__') and item.endswith('__'):
#             # This allows Python's internal calls to access special methods without causing recursion.
#             raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

        
#         if self.module is None:
#             try:
#                 # Dynamically import the module
#                 self.module = importlib.import_module(self.module_name)
#                 # Dynamically import specified attributes, if any
#                 for attr in self.attributes:
#                     setattr(self, attr, getattr(self.module, attr))
#             except ImportError:
#                 if self.optional:
#                     # If the module is optional, handle the import error gracefully.
#                     self.module = None  # Provide a no-op fallback
#                     print(f"Optional module {self.module_name} is not installed.")
#                     pass
#                 else:
#                     # If the module is not optional, re-raise error.
#                     raise
#         # Handle requests for module attributes
#         if hasattr(self, item) or hasattr(self.module, item):
#             return getattr(self.module, item) if hasattr(self.module, item) else getattr(self, item)
#         else:
#             raise AttributeError(f"Module '{self.module_name}' does not have attribute '{item}'")

#     def _safe_call(self, attr, *args, **kwargs):
#         """
#         Safely calls an attribute of the loaded module. If the attribute doesn't exist or an error occurs during the call, prints an error message.

#         :param attr: The attribute name to call.
#         :return: The result of the attribute call, or None if an error occurs.
#         """
#         try:
#             attribute = getattr(self.module, attr)
#             # If the attribute is callable, call it with provided arguments.
#             if callable(attribute):
#                 return attribute(*args, **kwargs)
#             # If the attribute is not callable, simply return its value.
#             return attribute
#         except AttributeError as e:
#             # Attribute not found in the module.
#             print(f"Attribute {attr} not found in module {self.module_name}: {e}")
#         except Exception as e:
#             # Handle any other exceptions that occur during the attribute call.
#             print(f"Error calling {attr} from {self.module_name}: {e}")

#     def _handle_load_failure(self, *args, **kwargs):
#         """A placeholder method called if the module fails to load."""
#         print(f"Module {self.module_name} could not be loaded. Functionality is unavailable.")
#         return None

#     def reload(self):
#         """
#         Reloads the module. Useful in development environments where the module's source code may change. Ensures that the latest version of the module is used.
#         """
#         # with self.lock:
#         if self.module is not None:
#             import importlib
#             self.module = importlib.reload(self.module)