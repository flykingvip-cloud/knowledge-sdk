"""Owned ephemeral database capability. Never runs DDL on a caller's target DB.
Control DSN is only accepted with loopback, dedicated name and ownership marker;
all prototype tables/auth tests use a NEW generated DB and non-superuser role.
"""
import re,uuid
MARKER='SDK25_OWNED_EPHEMERAL_CONTROL_V1'
_TOKEN=object()
class OwnedPostgres:
    def __init__(self,token):
        if token is not _TOKEN:raise ValueError('OWNED_CAPABILITY_REQUIRED')
    @classmethod
    def create(cls,control_dsn):
        import psycopg
        from psycopg.conninfo import conninfo_to_dict,make_conninfo
        from psycopg import sql
        info=conninfo_to_dict(control_dsn)
        if set(info)-{'host','port','dbname','user'}:raise ValueError('ONLY_EXPLICIT_CONTROL_COORDINATES_ALLOWED')
        if info.get('host')not in ('127.0.0.1','localhost') or not re.fullmatch(r'sdk25_control_[a-z0-9_]+',info.get('dbname','')) or int(info.get('port','5432'))in(3000,3001,8000,8002,8090,8091):raise ValueError('OWNED_CONTROL_REQUIRED')
        with psycopg.connect(control_dsn,autocommit=True,password='',passfile='/dev/null',sslmode='disable',gssencmode='disable')as c:
            marker=c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
            if marker!=MARKER:raise ValueError('OWNED_CONTROL_MARKER_REQUIRED')
            suffix=uuid.uuid4().hex;role='sdk25_role_'+suffix;db='sdk25_proto_'+suffix
            c.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE').format(sql.Identifier(role)))
            try:c.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(sql.Identifier(db),sql.Identifier(role)))
            except BaseException:c.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)));raise
        self=cls(_TOKEN);self.control=control_dsn;self.db=db;self.role=role;self.dsn=make_conninfo(control_dsn,dbname=db,user=role,password='',passfile='/dev/null',sslmode='disable',gssencmode='disable');self.closed=False
        return self
    def connect(self):
        if self.closed or not self.db.startswith('sdk25_proto_'):raise ValueError('OWNED_CAPABILITY_REQUIRED')
        import psycopg
        c=psycopg.connect(self.dsn,autocommit=True)
        if c.execute('SELECT current_database(),current_user').fetchone()!=(self.db,self.role):c.close();raise ValueError('OWNED_IDENTITY_MISMATCH')
        return c
    def close(self):
        if self.closed:return
        import psycopg
        from psycopg import sql
        with psycopg.connect(self.control,autocommit=True,password='',passfile='/dev/null',sslmode='disable',gssencmode='disable')as c:
            c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(self.db)))
            c.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(self.role)))
        self.closed=True
