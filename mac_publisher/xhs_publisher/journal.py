import fcntl
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

UNSAFE_RETRY={'preparing','ready','submitting','submitted_unverified','pending_review','published','unknown','rejected'}
class JobConflict(RuntimeError): pass

class Journal:
 def __init__(self,root):
    self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.root.chmod(0o700)
    self.path=self.root/'publisher.sqlite'
    with self.db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,account TEXT NOT NULL,fingerprint TEXT NOT NULL,state TEXT NOT NULL,result TEXT NOT NULL,updated REAL NOT NULL,UNIQUE(account,fingerprint))')
        db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,state TEXT NOT NULL,at REAL NOT NULL)')
    self.path.chmod(0o600)
 @contextmanager
 def db(self):
    db=sqlite3.connect(self.path)
    try:
        with db: yield db
    finally: db.close()
 def reserve(self,account,fingerprint,retry_prepare=False):
    with self.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT id,state FROM jobs WHERE account=? AND fingerprint=?',(account,fingerprint)).fetchone()
        if row:
            if not retry_prepare or row[1] not in {'blocked','failed_pre_submit'}: return row[0],False
            db.execute('UPDATE jobs SET state=?,result=?,updated=? WHERE id=?',('preparing','{}',time.time(),row[0]))
            return row[0],True
        job=uuid.uuid4().hex
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',(job,account,fingerprint,'preparing','{}',time.time()))
        return job,True
 def update(self,job,state,**result):
    with self.db() as db:
        row=db.execute('SELECT result FROM jobs WHERE id=?',(job,)).fetchone()
        if not row: raise JobConflict('任务不存在')
        merged=json.loads(row[0]);merged.update(result)
        db.execute('UPDATE jobs SET state=?,result=?,updated=? WHERE id=?',(state,json.dumps(merged,ensure_ascii=False),time.time(),job))
        db.execute('INSERT INTO events(job_id,state,at) VALUES(?,?,?)',(job,state,time.time()))
 def get(self,job):
    with self.db() as db:
        row=db.execute('SELECT id,account,fingerprint,state,result,updated FROM jobs WHERE id=?',(job,)).fetchone()
    return dict(zip(['id','account','fingerprint','state','result','updated'],row))|{'result':json.loads(row[4])} if row else None
 def history(self):
    with self.db() as db: ids=[r[0] for r in db.execute('SELECT id FROM jobs ORDER BY updated DESC LIMIT 50')]
    return [self.get(i) for i in ids]

@contextmanager
def profile_lock(root):
    path=Path(root)/'profile.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:
        os.chmod(path,0o600)
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc: raise JobConflict('浏览器正被另一个登录或发布任务使用') from exc
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.chmod(0o600);temp.replace(path)
