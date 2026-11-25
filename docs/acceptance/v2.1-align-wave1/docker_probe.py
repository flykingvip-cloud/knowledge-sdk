"""Owned, bounded CI image build/run only. Never publishes or alters existing containers."""
from __future__ import annotations
import argparse,json,subprocess,tempfile,secrets,shutil,uuid,time,threading,os
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.error import URLError,HTTPError
from http.client import HTTPException


def wait_ready(base_url,attempts=100,pause=.1):
    """Docker may accept/reset TCP before uvicorn is listening; readiness is real."""
    for _ in range(attempts):
        try:
            with urlopen(base_url+'/v1/ready',timeout=1) as response:
                if response.status==200 and json.load(response)=={'status':'ready'}:return True
        except (OSError,HTTPException,json.JSONDecodeError):pass
        threading.Event().wait(pause)
    return False


def run(output,required=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if shutil.which('docker') is None:
        result={'status':'BUILD_NOT_RUN','reason':'Docker CLI absent; no Podman/BuildKit/daemon socket available on the local box','scope':'Local box only; CI receipt is separate'}
        (output/'docker-status.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
        if required:raise RuntimeError('Docker build/run required in CI')
        return result
    identity=uuid.uuid4().hex;tag='knowledge-sdk-align-wave1-test:'+identity;name='sdk-align-wave1-'+identity;created=False;built=False
    root=Path(__file__).resolve().parents[3]
    def command(args,**kw):return subprocess.run(['docker']+args,check=True,capture_output=True,text=True,timeout=kw.pop('timeout',180),**kw)
    try:
        command(['version','--format','{{.Server.Version}}'])
        command(['pull','python:3.12.12-slim-bookworm'],timeout=240)
        base=command(['image','inspect','python:3.12.12-slim-bookworm','--format','{{index .RepoDigests 0}}']).stdout.strip()
        assert '@sha256:' in base
        build=command(['build','--build-arg','PYTHON_IMAGE='+base,'--tag',tag,'.'],cwd=root,timeout=480);built=True
        (output/'docker-build.log').write_text(build.stdout+build.stderr)
        assert command(['image','inspect',tag,'--format','{{.Config.User}}']).stdout.strip()=='65532:65532'
        probe_user=str(os.getuid())+':'+str(os.getgid());assert os.getuid()!=0
        with tempfile.TemporaryDirectory(prefix='sdk-align-container-test-') as directory:
            secret=secrets.token_hex(32);file=Path(directory)/'hmac';file.write_text(secret);file.chmod(0o600)
            # Retain the image's default-UID assertion above, but run the probe
            # as the nonzero host UID so a minimal-permission mounted key works.
            Path(directory).chmod(0o700)
            command(['run','--detach','--user',probe_user,'--name',name,'--label','knowledge-sdk-owned-fixture='+identity,'--read-only','--cap-drop=ALL','--security-opt','no-new-privileges','--memory','512m','--cpus','2','--pids-limit','128','--tmpfs','/data:uid='+str(os.getuid())+',gid='+str(os.getgid())+',mode=0700','--tmpfs','/tmp:uid='+str(os.getuid())+',gid='+str(os.getgid())+',mode=0700','--mount','type=bind,src='+str(file)+',dst=/run/secrets/knowledge_auth_secret,readonly','--publish','127.0.0.1::8088',tag]);created=True
            port=int(command(['port',name,'8088/tcp']).stdout.strip().rsplit(':',1)[1]);assert port not in (3000,3001,8000,8002,8090,8091)
            base_url='http://127.0.0.1:'+str(port)
            assert wait_ready(base_url),'Container did not reach real schema-v5 readiness'
            from knowledge_sdk import Actor,HttpKnowledgeClient
            from knowledge_sdk.server.auth import signed_headers
            a=Actor('container-test','container-test',org_roles=('admin','metrics_admin'));h=HttpKnowledgeClient(base_url,secret)
            h.create_kb(a,'test','enterprise',kb_id='test');h.ingest(a,'test','container fixture',doc_id='doc')
            assert h.get_kb(a,'test').kb_id=='test';assert h.rollback_document(a,'doc',1).version==2
            body=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}).encode();headers=signed_headers(a,secret,'POST','/v1/mcp',body);headers['Content-Type']='application/json'
            with urlopen(Request(base_url+'/v1/mcp',data=body,headers=headers),timeout=5) as response:assert len(json.load(response)['result']['tools'])==4
            headers=signed_headers(a,secret,'GET','/v1/metrics',b'')
            with urlopen(Request(base_url+'/v1/metrics',headers=headers),timeout=5) as response:assert len(json.load(response)['counters'])==5 and response.headers['Cache-Control']=='no-store'
            logs=command(['logs',name]);assert secret not in logs.stdout+logs.stderr
            config=command(['inspect',name,'--format','{{.Config.User}} {{.HostConfig.ReadonlyRootfs}}']).stdout.strip();assert config==probe_user+' true' and file.stat().st_mode&0o777==0o600
        result={'status':'ACTUAL_ISOLATED_BUILD_RUN_PASSED','base_image_digest':base,'nonroot_uid_gid':probe_user,'image_default_uid_gid':'65532:65532','key_permissions':'0600','read_only_rootfs':True,'capabilities_dropped':True,'memory_limit_mb':512,'cpus':2,'pids_limit':128,'health_ready':True,'signed_v1_compat':True,'mcp_four_tools':True,'authenticated_metrics_no_store':True,'published':False,'production_deployment':False}
        (output/'docker-status.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
    finally:
        try:
            if created:
                try:
                    # Diagnostic failure must never skip owned-resource cleanup.
                    logs=command(['logs',name]);safe=(logs.stdout+logs.stderr).replace(secret,'[REDACTED_FIXTURE_SECRET]')
                    (output/'docker-runtime.log').write_text(safe)
                finally:
                    try:command(['stop','--time','5',name])
                    finally:command(['rm',name])
        finally:
            if built:command(['rmi',tag])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--require',action='store_true');a=p.parse_args();run(a.output,a.require)
