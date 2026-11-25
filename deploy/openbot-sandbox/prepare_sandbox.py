"""Create NEW local fixture directories/ephemeral key, never overwrite or print a key."""
from __future__ import annotations
import argparse,json,os,secrets,socket,uuid
from pathlib import Path
FIXTURE='SDK22_ALIGN_WAVE1P5_SANDBOX_V1'
def prepare(root,port=8878):
    root=Path(root).absolute()
    if root.exists():raise ValueError('Choose a new unused fixture directory')
    if not 1024<=port<=65535 or port in (3000,3001,8000,8002,8090,8091):raise ValueError('Unsafe fixture port')
    if any(c in str(root) for c in ('\n','\r',':',' ','"',"'",'$','`')):raise ValueError('Use a simple local fixture path')
    uid=os.getuid();gid=os.getgid()
    if uid==0:raise ValueError('Prepare/run application as a non-root host user')
    with socket.socket() as s:s.bind(('127.0.0.1',port))
    root.mkdir(mode=0o700);(root/'data').mkdir(mode=0o700);(root/'secrets').mkdir(mode=0o700)
    marker=root/'data/fixture-marker.json';marker.write_text(json.dumps({'fixture':FIXTURE,'seed_revision':1})+'\n');marker.chmod(0o600)
    key=root/'secrets/hmac';key.write_text(secrets.token_hex(32)+'\n');key.chmod(0o600)
    config=root/'sandbox.env';config.write_text('SANDBOX_STATE='+str(root)+'\nSANDBOX_UID='+str(uid)+'\nSANDBOX_GID='+str(gid)+'\nSANDBOX_PORT='+str(port)+'\nSANDBOX_PROJECT=sdk22-openbot-'+uuid.uuid4().hex[:16]+'\nSANDBOX_IMAGE=knowledge-sdk:align-wave1p5\n');config.chmod(0o600)
    return {'status':'NEW_ISOLATED_FIXTURE_PREPARED','config_file':str(config),'secret_printed':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--port',type=int,default=8878);a=p.parse_args();print(json.dumps(prepare(a.directory,a.port)))
