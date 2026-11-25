"""Reproduce ONLY the synthetic prototype suite in a new local owned PG cluster.
No DSN input, no existing database/cluster, no SDK imports or runtime startup.
"""
import argparse,datetime,json,os,socket,subprocess,sys,tempfile,uuid
from pathlib import Path

def run(output,pg_bin='/usr/lib/postgresql/17/bin'):
    if os.getuid()==0:raise ValueError('NONROOT_RUNNER_REQUIRED')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    binaries=Path(pg_bin);repo=Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sdk25-owned-prototype-')as directory:
        root=Path(directory);data=root/'data';started=False
        with socket.socket()as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        if port in(3000,3001,8000,8002,8090,8091):raise ValueError('UNSAFE_EPHEMERAL_PORT')
        def cmd(args):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=60)
        try:
            init=cmd([str(binaries/'initdb'),'-D',str(data),'-A','trust','-U','sdk25_bootstrap','--no-locale','--encoding=UTF8']);(output/'init.log').write_text(init.stdout+init.stderr)
            cmd([str(binaries/'pg_ctl'),'-D',str(data),'-l',str(root/'server.log'),'-o',f'-h 127.0.0.1 -p {port} -k {root}','-w','start']);started=True
            import psycopg
            from psycopg import sql
            name='sdk25_control_'+uuid.uuid4().hex;admin=f'host=127.0.0.1 port={port} dbname=postgres user=sdk25_bootstrap'
            with psycopg.connect(admin,autocommit=True)as c:
                c.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(name)))
                c.execute(sql.SQL("COMMENT ON DATABASE {} IS 'SDK25_OWNED_EPHEMERAL_CONTROL_V1'").format(sql.Identifier(name)))
            env=dict(os.environ,SDK25_PROVISION_DSN=admin.replace('dbname=postgres','dbname='+name),SDK25_REQUIRE_PG='1')
            with (output/'prototype-tests.log').open('w')as log:
                result=subprocess.run([sys.executable,'-W','error::ResourceWarning','-m','unittest','discover','-s','sandbox/space_alignment_v1','-v'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            with psycopg.connect(admin,autocommit=True)as c:
                remaining_db=c.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'sdk25_proto_%'").fetchone()[0]
                remaining_roles=c.execute("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'sdk25_role_%'").fetchone()[0]
            assert remaining_db==remaining_roles==0
            receipt=dict(status='P_SPACE_PROTOTYPE_ONLY',formal_acceptance=False,exit_code=result.returncode,owned_generated_cluster=True,loopback_port=port,remaining_generated_databases=remaining_db,remaining_generated_roles=remaining_roles,finished_at_cst=datetime.datetime.now().astimezone().isoformat())
        finally:
            if started or(data/'postmaster.pid').exists():cmd([str(binaries/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'])
            if(root/'server.log').exists():(output/'owned-server.log').write_bytes((root/'server.log').read_bytes())
        receipt['owned_cluster_stopped']=True;(output/'owned-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return result.returncode
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--pg-bin',default='/usr/lib/postgresql/17/bin');a=p.parse_args();raise SystemExit(run(a.output,a.pg_bin))
