"""All inherited wheel/RECORD/AST gates, plus readiness asset AST and -S audit smoke."""
from __future__ import annotations
import ast,os,runpy,subprocess,sys,tempfile,zipfile
from pathlib import Path

def main():
    wheel=Path(sys.argv[1]).resolve()
    runpy.run_path('docs/acceptance/v2.1-align-wave1/verify_package.py',run_name='__main__')
    scripts=list(Path('deploy/openbot-sandbox').glob('*.py'))+list(Path('docs/acceptance/v2.1-align-wave1p5').glob('*.py'))+list(Path('tests/alignment_p5').glob('*.py'))+[Path('docs/architecture/knowledge-sdk-alignment/validate_m1_manifest.py')]
    for script in scripts:ast.parse(script.read_text(),filename=str(script),feature_version=(3,9))
    with tempfile.TemporaryDirectory(prefix='sdk22-p5-wheel-') as directory:
        with zipfile.ZipFile(wheel) as archive:archive.extractall(directory)
        code="""from knowledge_sdk import Actor,LocalKnowledgeClient,DocumentACL,PermissionDeniedError
c=LocalKnowledgeClient();a=Actor('owner','org',org_roles=('admin',));b=Actor('reader','org')
try:
 c.create_kb(a,'space',kb_id='kb');c.grant_kb_member(a,'kb','reader','editor')
 c.ingest(a,'kb','old',filename='old.txt',doc_id='d');c.ingest(a,'kb','new',doc_id='d')
 c.set_document_acl(a,'d',DocumentACL(deny_users=['reader']))
 restored=c.rollback_document(a,'d',1);assert restored.text=='old' and restored.filename=='old.txt'
 event=c.store.list_audit_events('org',action='rollback_document',limit=10)[-1]
 assert event.details['rollback_scope']=='content_and_filename_only'
 assert event.details['security_metadata_preserved'] is True
 try:c.get_document(b,'d')
 except PermissionDeniedError:pass
 else:raise AssertionError('ACL resurrected')
 assert c.search(a,'old').hits and c._retrieval_identity is None
 assert c.store.db.execute('PRAGMA user_version').fetchone()[0]==5
finally:c.store.close()
print('Wave1p5 extracted wheel strict zero-dependency audit and request-lifetime smoke passed')"""
        subprocess.run([sys.executable,'-S','-W','error::ResourceWarning','-c',code],cwd=directory,env=dict(os.environ,PYTHONPATH=directory),check=True)
    print('Wave1p5 assets/tests Python3.9 AST passed:',len(scripts))
if __name__=='__main__':main()
