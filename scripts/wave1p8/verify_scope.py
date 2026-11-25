"""Read-only Wave1.8 frozen-boundary gate, zero third-party imports."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASELINE='07f5d39f05ef4c7952be48b83025b9c86ea2458e'
ROOT=Path(__file__).resolve().parents[2]
FROZEN=['src/knowledge_sdk/storage/migrations.py','tests/benchmark',
        'docs/architecture/knowledge-sdk-alignment/contracts',
        'docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json',
        'docs/architecture/knowledge-sdk-alignment/M1_DECISION_PACKAGE.md','pyproject.toml']
FROZEN += [str(p.relative_to(ROOT)) for p in (ROOT/'docs/architecture/knowledge-sdk-alignment').glob('[0-1][0-9]_*.md') if int(p.name[:2])<=10]
result=subprocess.check_output(['git','diff',BASELINE,'--']+FROZEN,cwd=ROOT)
if result:raise SystemExit('FROZEN_BOUNDARY_CHANGED')
manifest=json.loads((ROOT/'docs/architecture/knowledge-sdk-alignment/m1-freeze-manifest.json').read_text())
assert manifest['status']=='pending_joint_signoff' and manifest['freeze_authorized'] is False
assert len(manifest['contract_asset_hashes'])==28
assert re.search(r'^dependencies\s*=\s*\[\]',(ROOT/'pyproject.toml').read_text(),re.M)
source=ROOT/'docs/architecture/knowledge-sdk-alignment/12_WAVE1P8_PRE_M2_FOUNDATION_DIRECTIVE.md'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='daa48b8853d0849b1df812ee0b87228ff57364e10ae41f90afb9fa330a096949'
print(json.dumps(dict(baseline=BASELINE,frozen_diff_bytes=len(result),contract_assets=28,
                     core_dependencies=[],m1='pending_joint_signoff',freeze_authorized=False,
                     directive_byte_original=True)))
