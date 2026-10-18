"""Docker entrypoint: persist generated secrets once, migrate, then start one worker."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import argparse


def migrate_database_path(environ):
    target=Path(environ.get('DATABASE_URL','sqlite:////data/gatearr.db').removeprefix('sqlite:///'))
    if target.name!='gatearr.db' or target.exists() or not target.parent.exists():return
    candidates=[]
    for path in target.parent.glob('*.db'):
        with sqlite3.connect(path) as db:
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if {'users','config','alembic_version'}<=tables:candidates.append(path)
    if len(candidates)>1:raise RuntimeError('Multiple portal databases found. Set DATABASE_URL explicitly before upgrading.')
    if candidates:
        with sqlite3.connect(candidates[0]) as source,sqlite3.connect(target) as destination:source.backup(destination)


def prepare(environ=None):
    environ=os.environ if environ is None else environ
    migrate_database_path(environ)
    path=Path(environ.get('GATEARR_SECRETS_FILE','/data/bootstrap.json'))
    missing=[name for name in ('SECRET_KEY',) if not environ.get(name)]
    if missing:
        if not path.exists():
            # An existing initialized installation must retain its original encryption key.
            database=environ.get('DATABASE_URL','sqlite:////data/gatearr.db')
            if database.startswith('sqlite:///'):
                db_path=Path(database[len('sqlite:///'):])
                if db_path.exists() and not environ.get('SECRET_KEY'):
                    with sqlite3.connect(db_path) as db:
                        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='config'").fetchone()
                        if exists and db.execute("SELECT 1 FROM config LIMIT 1").fetchone():
                            raise RuntimeError('SECRET_KEY existante requise : restaurez votre .env ou votre fichier bootstrap.json')
            path.parent.mkdir(parents=True,exist_ok=True)
            values={name:environ.get(name) or secrets.token_urlsafe(48) for name in ('SECRET_KEY',)}
            try:
                descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,'w') as output:json.dump(values,output)
            except FileExistsError:pass
        values=json.loads(path.read_text())
        for name in missing:
            value=values.get(name,'')
            if len(value)<32:raise RuntimeError('Fichier de secrets invalide')
            environ[name]=value
    if path.exists():
        persisted=json.loads(path.read_text())
        if set(persisted)!={'SECRET_KEY'}:
            path.write_text(json.dumps({'SECRET_KEY':persisted['SECRET_KEY']}))
    return environ


def main():
    argparse.ArgumentParser(description='Start Gatearr and migrate its database').parse_args()
    prepare()
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)
    os.execvp('uvicorn',['uvicorn','app.main:app','--host','0.0.0.0','--port','8000','--workers','1','--no-access-log','--proxy-headers','--forwarded-allow-ips',os.getenv('TRUSTED_PROXY_IPS','127.0.0.1')])

if __name__=='__main__':main()
