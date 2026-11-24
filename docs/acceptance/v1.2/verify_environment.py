"""Reproducible L2 AST/wheel and isolated core-import verification (stdlib only)."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile
from email.parser import Parser

ROOT = Path(__file__).resolve().parents[3]
files = sorted((ROOT / 'src').rglob('*.py'))
for path in files:
    ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)), feature_version=(3, 9))
print('Python 3.9 AST PASS:', len(files), 'source files (syntax check, not Python 3.9 runtime execution)')
# A blocking import hook fails if even a single third-party dependency is imported.
code = '''import importlib.abc, sys
class StdlibOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split('.')[0]
        if top not in sys.stdlib_module_names and top != 'knowledge_sdk':
            raise AssertionError('Non-stdlib import: ' + fullname)
sys.meta_path.insert(0, StdlibOnly())
import knowledge_sdk
from knowledge_sdk import Actor, LocalKnowledgeClient
from knowledge_sdk.storage.sqlite_store import SQLiteStore
client=LocalKnowledgeClient(SQLiteStore(':memory:'))
client.list_kbs(Actor('u','org'))
client.store.close()
print('Core import and basic runtime under python -S: PASS (blocking third-party import hook)')
'''
cmd = [sys.executable, '-S', '-c', code]
print('$', sys.executable, '-S -c <stdlib-only import hook>', flush=True)
subprocess.run(cmd, cwd=ROOT, check=True)
wheel = ROOT / 'dist/knowledge_sdk-1.2.0-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
    for name in ('index.html','workbench.css','workbench.js','i18n.js'):
        assert 'knowledge_sdk/ui/static/' + name in names, name
    init = archive.read('knowledge_sdk/__init__.py').decode()
    assert '__version__ = "1.2.0"' in init
    metadata = Parser().parsestr(archive.read('knowledge_sdk-1.2.0.dist-info/METADATA').decode())
    assert metadata['Version'] == '1.2.0'
    assert all('extra ==' in dep for dep in metadata.get_all('Requires-Dist', [])), 'core dependency found'
print('Wheel resources/version/zero core dependencies: PASS')
print('Wheel:', wheel.name)
print('SHA256:', hashlib.sha256(wheel.read_bytes()).hexdigest())
