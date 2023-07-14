import hashlib
import importlib.util
import json
from typing import Dict

import rope.base.project


def get_version_hash_data(project: rope.base.project.Project) -> Dict[str, str]:
    version_hash_data = dict(
        version_data=f"{rope.VERSION}",
        prefs_data=_get_prefs_data(project),
        schema_file_content=_get_file_content("rope.contrib.autoimport.models"),
    )
    return version_hash_data


def calculate_version_hash(project: rope.base.project.Project) -> str:
    def _merge(hasher, name: str, serialized_data: str):
        hashed_data = hashlib.sha256(serialized_data.encode("utf-8")).hexdigest()
        hasher.update(hashed_data.encode("ascii"))

    hasher = hashlib.sha256()
    for name, data in get_version_hash_data(project).items():
        _merge(hasher, name, data)
    return hasher.hexdigest()


def _get_prefs_data(project) -> str:
    prefs_data = dict(vars(project.prefs))
    del prefs_data["project_opened"]
    del prefs_data["callbacks"]
    del prefs_data["dependencies"]
    return json.dumps(prefs_data, sort_keys=True, indent=2)


def _get_file_content(module_name: str) -> str:
    models_module = importlib.util.find_spec(module_name)
    assert models_module and models_module.loader
    assert isinstance(models_module.loader, importlib.machinery.SourceFileLoader)
    src = models_module.loader.get_source(module_name)
    assert src
    return src
