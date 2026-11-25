"""Run unchanged M2 wheel integrity gates, then additive Wave1 extracted -S smoke."""
from __future__ import annotations
import ast,os,runpy,subprocess,sys,tempfile,zipfile
from pathlib import Path


def main():
    wheel=Path(sys.argv[1]).resolve()
    runpy.run_path('docs/acceptance/v2.1-q3-phase2/verify_package.py',run_name='__main__')
    scripts=list(Path('docs/acceptance/v2.1-align-wave1').glob('*.py'))+list(Path('docs/architecture/knowledge-sdk-alignment/contracts').glob('*.py'))
    for script in scripts:ast.parse(script.read_text(),filename=str(script),feature_version=(3,9))
    with tempfile.TemporaryDirectory(prefix='wave1-extracted-wheel-') as directory:
        with zipfile.ZipFile(wheel) as archive:archive.extractall(directory)
        code="""from knowledge_sdk import Actor,LocalKnowledgeClient
from knowledge_sdk.connectors import ConnectorSyncRunner
from knowledge_sdk.contracts.connectors import ConnectorSyncBatch
c=LocalKnowledgeClient();a=Actor('owner','org',org_roles=('admin',))
try:
 c.create_kb(a,'original',kb_id='kb');c.ingest(a,'kb','original text',doc_id='doc')
 assert c.get_kb(a,'kb').name=='original'
 assert c.update_kb(a,'kb',name='updated').name=='updated'
 assert c.list_kb_members(a,'kb')==[{'user_id':'owner','role':'admin'}]
 assert len(c.list_document_versions(a,'doc'))==1
 assert c.rollback_document(a,'doc',1).version==2
 assert len(c.list_document_versions(a,'doc'))==2
 class Source:connector_id='source';org_id='org'
 changes=c.store.db.total_changes
 assert ConnectorSyncRunner(c).plan_sync(a,Source(),org_id='org',kb_id='kb',batch=ConnectorSyncBatch())['to_upsert']==[]
 assert c.store.db.total_changes==changes
 assert c.store.db.execute('PRAGMA user_version').fetchone()[0]==5
finally:c.store.close()
print('Wave1 extracted wheel stdlib strict compatibility smoke passed')"""
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd=directory,env=dict(os.environ,PYTHONPATH=directory),check=True)
    print('Wave1 acceptance/draft Python3.9 AST passed:',len(scripts))

if __name__=='__main__':main()
