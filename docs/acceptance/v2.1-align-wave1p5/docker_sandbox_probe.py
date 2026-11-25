"""Bounded fresh CI images/projects only; no publication or existing daemon changes."""
from __future__ import annotations
import argparse,importlib.util,json,os,shutil,socket,subprocess,tempfile,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];SCRIPTS=ROOT/'deploy/openbot-sandbox'
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def run(output,required=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if shutil.which('docker') is None:
        result={'status':'BUILD_NOT_RUN','reason':'Local Docker CLI/daemon unavailable; actual CI receipt separate','local_container_claim':False};(out/'sandbox-docker.json').write_text(json.dumps(result,indent=2)+'\n')
        if required:raise RuntimeError('Actual Docker tests required in CI')
        return result
    prepare=module('sandbox_prepare',SCRIPTS/'prepare_sandbox.py').prepare;wait=module('sandbox_wait',ROOT/'docs/acceptance/v2.1-align-wave1/docker_probe.py').wait_ready
    identity=uuid.uuid4().hex;image='sdk22-wave1p5-fixture:'+identity;built=False;results=[];started=time.monotonic()
    def cmd(args,check=True,timeout=180,env=None):return subprocess.run(['docker']+args,check=check,capture_output=True,text=True,timeout=timeout,cwd=ROOT,env=env)
    try:
        cmd(['version','--format','{{.Server.Version}}']);cmd(['compose','version']);cmd(['pull','python:3.12.12-slim-bookworm'],timeout=240)
        base=cmd(['image','inspect','python:3.12.12-slim-bookworm','--format','{{index .RepoDigests 0}}']).stdout.strip();assert '@sha256:' in base
        build=cmd(['build','--build-arg','PYTHON_IMAGE='+base,'--tag',image,'.'],timeout=480);built=True;(out/'sandbox-image-build.log').write_text(build.stdout+build.stderr)
        cmd(['pull','pgvector/pgvector:pg17'],timeout=240);pg=cmd(['image','inspect','pgvector/pgvector:pg17','--format','{{index .RepoDigests 0}}']).stdout.strip();assert '@sha256:' in pg
        for mode in ('sqlite','postgres'):
            phase=time.monotonic();project='sdk22-wave1p5-'+mode+'-'+identity
            with tempfile.TemporaryDirectory(prefix='sdk22-owned-sandbox-') as directory:
                state=Path(directory)/'new'
                with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
                prepare(state,port);env=dict(os.environ,SANDBOX_IMAGE=image,SANDBOX_PG_IMAGE=pg)
                compose=['compose','--env-file',str(state/'sandbox.env'),'-p',project,'-f',str(SCRIPTS/('compose.'+mode+'.yaml'))]
                try:
                    cmd(compose+['config','--quiet'],env=env)
                    cmd(compose+['up','--detach','--wait','--wait-timeout','120'],env=env,timeout=180)
                    assert wait('http://127.0.0.1:'+str(port),attempts=150),'Actual fixture readiness failed'
                    wire=cmd(compose+['exec','-T','sandbox','python','/opt/sandbox/probe_openbot_sandbox.py','--url','http://127.0.0.1:8088'],env=env);result=json.loads(wire.stdout)
                    assert result['status']=='REAL_SIGNED_SANDBOX_WIRE_PASSED'
                    container=cmd(compose+['ps','--quiet','sandbox'],env=env).stdout.strip()
                    actual=cmd(['inspect',container,'--format','{{.Config.User}} {{.HostConfig.ReadonlyRootfs}}']).stdout.strip();assert actual==str(os.getuid())+':'+str(os.getgid())+' true' and os.getuid()!=0
                    second=cmd(compose+['run','--rm','--no-deps','seed'],env=env);assert json.loads(second.stdout)['status']=='IDEMPOTENT_NO_WRITES'
                    assert (state/'secrets/hmac').stat().st_mode&0o777==0o600
                    if mode=='postgres':
                        code="import sys,os,json;sys.path.insert(0,'/opt/sandbox');from seed_openbot_sandbox import connect,TENANTS;c=connect('/data','postgres',os.environ['KNOWLEDGE_SDK_DSN']);assert c.store._execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')[0]==(False,False);assert c.store._execute('SELECT count(*) FROM documents')[0][0]==0;ctx=c.store.tenant_scope(TENANTS[0]);ctx.__enter__();assert c.store._execute('SELECT count(*) FROM documents WHERE org_id=%s',(TENANTS[1],))[0][0]==0;ctx.__exit__(None,None,None);c.store.close();print(json.dumps({'non_superuser_nobypassrls':True,'unscoped_rows':0,'cross_tenant_rows':0}))"
                        sql=cmd(compose+['exec','-T','sandbox','python','-c',code],env=env);result['real_rls']=json.loads(sql.stdout)
                    result.update(mode=mode,nonroot_uid=os.getuid(),read_only_rootfs=True,key_permissions='0600',seed_idempotent_no_writes=True,setup_and_probe_seconds=time.monotonic()-phase)
                    results.append(result)
                finally:
                    try:
                        logs=cmd(compose+['logs','--no-color'],check=False,env=env)
                        # Fixture key contents never enter logs, reports or stdout.
                        secret=(state/'secrets/hmac').read_text().strip();safe=(logs.stdout+logs.stderr).replace(secret,'[REDACTED]');(out/('sandbox-'+mode+'-runtime.log')).write_text(safe)
                    finally:cmd(compose+['down','--volumes','--remove-orphans','--timeout','5'],env=env)
        result={'status':'ACTUAL_ISOLATED_BOTH_SANDBOX_MODES_PASSED','source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),'base_image_digest':base,'pg_image_digest':pg,'modes':results,'build_and_both_modes_seconds':time.monotonic()-started,'published':False,'production_deployment':False};(out/'sandbox-docker.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
    finally:
        if built:cmd(['rmi',image])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--require',action='store_true');a=p.parse_args();run(a.output,a.require)
