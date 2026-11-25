import importlib.util
from pathlib import Path


def live(app):
    path=Path(__file__).parents[2]/'docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py'
    spec=importlib.util.spec_from_file_location('wave18_live',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.live(app)
