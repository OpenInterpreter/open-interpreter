"""
Some code extracted (or based on code) from:
https://github.com/davidhalter/jedi/blob/b489019f5bd5750051122b94cc767df47751ecb7/jedi/evaluate/docstrings.py
Thanks to @davidhalter for this utils under MIT License.
"""
import re

from rope.base.ast import literal_eval
from rope.base.oi.type_hinting.providers import docstrings

try:
    from numpydoc.docscrape import NumpyDocString
except ImportError:
    NumpyDocString = None


class NumPyDocstringParamParser(docstrings.IParamParser):
    def __call__(self, docstring, param_name):
        """Search `docstring` (in numpydoc format) for type(-s) of `param_name`."""
        if not docstring:
            return []
        params = NumpyDocString(docstring)._parsed_data["Parameters"]
        for p_name, p_type, p_descr in params:
            if p_name == param_name:
                m = re.match("([^,]+(,[^,]+)*?)(,[ ]*optional)?$", p_type)
                if m:
                    p_type = m.group(1)

                if p_type.startswith("{"):
                    types = {type(x).__name__ for x in literal_eval(p_type)}
                    return list(types)
                else:
                    return [p_type]
        return []


class _DummyParamParser(docstrings.IParamParser):
    def __call__(self, docstring, param_name):
        return []


if not NumpyDocString:
    NumPyDocstringParamParser = _DummyParamParser
