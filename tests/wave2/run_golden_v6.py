"""Run unchanged original golden commands/assertions with every primary fixture v6.

Only wraps fixture setup AFTER its predecessor v5 KB creation. No benchmark source,
case registry, expected assertion, vector stub, engine flag or hard gate is changed.
"""
from unittest.mock import patch
from knowledge_sdk.storage.migration_v6 import upgrade_v6,require_v6
from tests.benchmark import runner


class V6Fixture(runner.Fixture):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        try:upgrade_v6(self.c.store,owned_nonproduction=True);require_v6(self.c.store)
        except BaseException:self.close();raise


if __name__=='__main__':
    with patch.object(runner,'Fixture',V6Fixture):raise SystemExit(runner.main())
