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
