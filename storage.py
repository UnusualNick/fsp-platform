import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA='''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('candidate','employer')),verified INTEGER DEFAULT 0,created REAL NOT NULL,consent_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id),name TEXT DEFAULT '',skills TEXT DEFAULT '',about TEXT DEFAULT '',contact TEXT DEFAULT '',industry TEXT DEFAULT 'ИТ',specialization TEXT DEFAULT 'backend',grade TEXT,claimed_grade TEXT DEFAULT 'Junior',score REAL DEFAULT 0,published INTEGER DEFAULT 0,fsp_id TEXT,achievements TEXT DEFAULT '[]',grade_changed REAL);
CREATE TABLE IF NOT EXISTS companies(user_id INTEGER PRIMARY KEY REFERENCES users(id),name TEXT DEFAULT '',description TEXT DEFAULT '',contact TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS verifications(token_hash TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),form TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,completed REAL,result TEXT);
CREATE TABLE IF NOT EXISTS invitations(id INTEGER PRIMARY KEY,employer_id INTEGER REFERENCES users(id),candidate_id INTEGER REFERENCES users(id),title TEXT NOT NULL,description TEXT NOT NULL,salary_min INTEGER NOT NULL,salary_max INTEGER NOT NULL,status TEXT DEFAULT 'sent' CHECK(status IN ('sent','viewed','accepted','declined')),created REAL NOT NULL,updated REAL NOT NULL,company_name TEXT NOT NULL,company_contact TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS invitations_candidate ON invitations(candidate_id);
CREATE INDEX IF NOT EXISTS invitations_employer ON invitations(employer_id);
CREATE TABLE IF NOT EXISTS vacancies(id INTEGER PRIMARY KEY,employer_id INTEGER REFERENCES users(id),title TEXT NOT NULL,description TEXT NOT NULL,specialization TEXT NOT NULL,grade TEXT NOT NULL,skills TEXT NOT NULL,salary_min INTEGER NOT NULL,salary_max INTEGER NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY,vacancy_id INTEGER REFERENCES vacancies(id),candidate_id INTEGER REFERENCES users(id),status TEXT DEFAULT 'sent',created REAL NOT NULL,UNIQUE(vacancy_id,candidate_id));
CREATE TABLE IF NOT EXISTS practice(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),specialization TEXT NOT NULL,form TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,completed REAL,result TEXT);
CREATE INDEX IF NOT EXISTS practice_owner ON practice(user_id,created);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,event TEXT,created REAL,details TEXT);
'''
class Storage:
 def __init__(self,path):
  self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as c:c.executescript(SCHEMA)
 @contextmanager
 def connect(self):
  c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
  try:
   yield c;c.commit()
  except Exception:
   c.rollback();raise
  finally:c.close()
