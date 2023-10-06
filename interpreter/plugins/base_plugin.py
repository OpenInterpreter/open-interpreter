# add this to a separate package that folks can install and import
# into their own plugin definitions
class InterpreterPlugin:
    """
    A base class for building Open Interpreter plugins.
    """

    def __init__(self, name):
        self.name = name
        self.functions = []
        self.callMap = {}

    def get_functions(self):
        """
        Return the list of functions defined by this plugin
        """
        return self.functions

    def register_function(self, function_def, function_to_call):
        """
        Define a new function that this plugin enables
        """

        self.functions.append(function_def)
        self.callMap[function_def["name"]] = function_to_call

    def execute_function(self, function_name="", parameters={}):
        """
        Receive the parameters defined for a function and execute
        it with them as keyword arguments
        """

        if function_name not in self.callMap:
            return {"error": "Function not found"}
        else:
            return self.callMap[function_name](**parameters)
