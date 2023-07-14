from distutils.command.build import build as _build
import warnings

from setuptools import SetuptoolsDeprecationWarning


_ORIGINAL_SUBCOMMANDS = {"build_py", "build_clib", "build_ext", "build_scripts"}


class build(_build):
    # copy to avoid sharing the object with parent class
    sub_commands = _build.sub_commands[:]

    def run(self):
        subcommands = {cmd[0] for cmd in _build.sub_commands}
        if subcommands - _ORIGINAL_SUBCOMMANDS:
            msg = """
            It seems that you are using `distutils.command.build` to add
            new subcommands. Using `distutils` directly is considered deprecated,
            please use `setuptools.command.build`.
            """
            warnings.warn(msg, SetuptoolsDeprecationWarning)
            self.sub_commands = _build.sub_commands
        super().run()
