# _build_config.py.in is converted into _build_config.py during the meson build process.

from __future__ import annotations


def build_config() -> dict[str, str]:
    """
    Return a dictionary containing build configuration settings.

    All dictionary keys and values are strings, for example ``False`` is
    returned as ``"False"``.
    """
    return dict(
        # Python settings
        python_version="3.10",
        python_install_dir=r"/usr/local/lib/python3.10/site-packages/",
        python_path=r"/tmp/build-env-bm13lnj5/bin/python",

        # Package versions
        contourpy_version="1.1.0",
        meson_version="1.1.1",
        mesonpy_version="0.13.1",
        pybind11_version="2.10.4",

        # Misc meson settings
        meson_backend="ninja",
        build_dir=r"/project/.mesonpy-ni3w2uwu/build/lib/contourpy/util",
        source_dir=r"/project/lib/contourpy/util",
        cross_build="False",

        # Build options
        build_options=r"-Dbuildtype=release -Db_ndebug=if-release -Db_vscrt=md -Dvsenv=True --native-file=/project/.mesonpy-ni3w2uwu/build/meson-python-native-file.ini",
        buildtype="release",
        cpp_std="c++17",
        debug="False",
        optimization="3",
        vsenv="True",
        b_ndebug="if-release",
        b_vscrt="from_buildtype",

        # C++ compiler
        compiler_name="gcc",
        compiler_version="10.2.1",
        linker_id="ld.bfd",
        compile_command="c++",

        # Host machine
        host_cpu="x86_64",
        host_cpu_family="x86_64",
        host_cpu_endian="little",
        host_cpu_system="linux",

        # Build machine, same as host machine if not a cross_build
        build_cpu="x86_64",
        build_cpu_family="x86_64",
        build_cpu_endian="little",
        build_cpu_system="linux",
    )
