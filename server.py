#!/usr/bin/env python3
"""Small dependency-light HTTP adapter. Business logic and storage are separate modules."""
import argparse,json,os,re,time,threading
from collections import defaultdict,deque
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from storage import Storage
from service import Service,ApiError
from assessment import SPECIALIZATIONS,GRADES
from seed import seed
ROOT=Path(__file__).resolve().parent
STATIC_FILES={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/fsp-logo.svg':('fsp-logo.svg','image/svg+xml')}
STATIC_FILES['/fonts/JetBrainsMono-Regular.woff2']=('fonts/JetBrainsMono-Regular.woff2','font/woff2')
STATIC_FILES['/fonts/Lato-Regular.ttf']=('fonts/Lato-Regular.ttf','font/ttf')
STATIC_FILES['/fonts/Lato-Bold.ttf']=('fonts/Lato-Bold.ttf','font/ttf')
STATIC_FILES['/assets/overview.svg']=('assets/overview.svg','image/svg+xml')
STATIC_FILES['/assets/communication.svg']=('assets/communication.svg','image/svg+xml')
STATIC_FILES['/assets/people.svg']=('assets/people.svg','image/svg+xml')
STATIC_FILES['/assets/activity.svg']=('assets/activity.svg','image/svg+xml')
STATIC_FILES['/assets/fsp-mark.svg']=('assets/fsp-mark.svg','image/svg+xml')
STATIC_FILES['/assets/fsp-pattern.png']=('assets/fsp-pattern.png','image/png')
STATIC_FILES['/styles/base.css']=('styles/base.css','text/css; charset=utf-8')
STATIC_FILES['/styles/content.css']=('styles/content.css','text/css; charset=utf-8')
STATIC_FILES['/styles/controls.css']=('styles/controls.css','text/css; charset=utf-8')
STATIC_FILES['/styles/layout.css']=('styles/layout.css','text/css; charset=utf-8')
STATIC_FILES['/styles/motion.css']=('styles/motion.css','text/css; charset=utf-8')
STATIC_FILES['/styles/overlays.css']=('styles/overlays.css','text/css; charset=utf-8')
STATIC_FILES['/styles/search.css']=('styles/search.css','text/css; charset=utf-8')
STATIC_FILES['/ui/dialog.js']=('ui/dialog.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/disclosure.js']=('ui/disclosure.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/icons.js']=('ui/icons.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/index.js']=('ui/index.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/motion.js']=('ui/motion.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/navigation.js']=('ui/navigation.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/select-keyboard.js']=('ui/select-keyboard.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/select-menu.js']=('ui/select-menu.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/select.js']=('ui/select.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/profile-fields.js']=('ui/profile-fields.js','text/javascript; charset=utf-8')
STATIC_FILES['/ui/toast.js']=('ui/toast.js','text/javascript; charset=utf-8')


class Handler(BaseHTTPRequestHandler):
 server_version='FSPMVP/1.1'
 def log_message(self,fmt,*args):pass # Avoid leaking verification tokens or query data into logs.
 def respond(self,status,data,ctype='application/json; charset=utf-8',cookie=None):
  raw=json.dumps(data,ensure_ascii=False).encode() if ctype.startswith('application/json') else data
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)))
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(raw)
 def token(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except Exception:return ''
  return cookie['session'].value if 'session' in cookie else ''
 def body(self):
  try:length=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ApiError(400,'Некорректная длина запроса')
  if length>65536 or length<0:raise ApiError(413,'Слишком большой запрос')
  if not self.headers.get('Content-Type','').startswith('application/json'):raise ApiError(415,'Требуется application/json')
  try:d=json.loads(self.rfile.read(length))
  except (ValueError,UnicodeDecodeError):raise ApiError(400,'Некорректный JSON')
  if not isinstance(d,dict):raise ApiError(400,'Требуется JSON-объект')
  return d
 def limit(self,path):
  if path not in ('/api/auth/login','/api/auth/register','/api/auth/verify'):return
  key=(self.client_address[0],path);now=time.time()
  with self.server.rate_lock:
   events=self.server.rates[key]
   while events and events[0]<now-60:events.popleft()
   if len(events)>=20:raise ApiError(429,'Слишком много запросов. Повторите через минуту')
   events.append(now)
 def do_GET(self):self.handle_request('GET')
 def do_POST(self):self.handle_request('POST')
 def do_PUT(self):self.handle_request('PUT')
 def handle_request(self,method):
  try:
   parsed=urlsplit(self.path);path=parsed.path;q={k:v[0] for k,v in parse_qs(parsed.query).items()};s=self.server.service;cookie=None
   if method=='GET' and path in STATIC_FILES:
    file,ctype=STATIC_FILES[path]
    return self.respond(200,(ROOT/'web'/file).read_bytes(),ctype)
   if method=='GET' and path=='/api/health':
    with s.store.connect() as c:c.execute('SELECT 1 FROM users LIMIT 1').fetchone()
    return self.respond(200,{'status':'ok','demo':s.demo,'version':'1.1.0'})
   if method=='GET' and path=='/api/catalog':return self.respond(200,{'specializations':SPECIALIZATIONS,'grades':GRADES})
   if method=='GET' and path=='/openapi.json':return self.respond(200,json.loads((ROOT/'docs/openapi.json').read_text()))
   if method not in ('GET','POST','PUT'):raise ApiError(405,'Метод не поддерживается')
   self.limit(path)
   d=self.body() if method!='GET' else {}
   # SameSite cookies plus explicit CSRF token for every authenticated mutation.
   if method!='GET':
    origin=self.headers.get('Origin')
    expected=os.environ.get('PUBLIC_URL') or 'http://'+self.headers.get('Host','')
    if origin and origin.rstrip('/')!=expected.rstrip('/'):raise ApiError(403,'Недопустимый источник запроса')
   if method=='POST' and path=='/api/auth/register':result=s.register(d)
   elif method=='POST' and path=='/api/auth/verify':result=s.verify(d)
   elif method=='POST' and path=='/api/auth/login':
    result,token=s.login(d)
    cookie=f'session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=86400'+('; Secure' if self.server.secure else '')
   else:
    u=s.auth(self.token())
    if method!='GET' and self.headers.get('X-CSRF-Token')!=u['csrf']:raise ApiError(403,'CSRF-токен недействителен')
    def role(r):
     if u['role']!=r:raise ApiError(403,'Недостаточно прав')
    if method=='GET' and path=='/api/me':result=s.me(u)
    elif method=='POST' and path=='/api/auth/logout':
     result=s.logout(self.token());cookie='session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'
    elif method=='PUT' and path=='/api/profile':result=s.update_profile(u,d)
    elif path=='/api/needs/preview' and method=='POST':role('employer');result=s.need_preview(u,d)
    elif path=='/api/practice' and method=='POST':role('candidate');result=s.practice(u)
    elif path=='/api/practice/submit' and method=='POST':role('candidate');result=s.submit_practice(u,d)
    elif path=='/api/assessment/start' and method=='POST':role('candidate');result=s.start_assessment(u,d)
    elif path=='/api/assessment/active' and method=='GET':role('candidate');result=s.active_assessment(u)
    elif path=='/api/assessment/submit' and method=='POST':role('candidate');result=s.submit_assessment(u,d)
    elif path=='/api/fsp/link' and method=='POST':role('candidate');result=s.link_fsp(u,d)
    elif path=='/api/candidates' and method=='GET':role('employer');result=s.candidates(u,q)
    elif re.fullmatch(r'/api/candidates/\d+/contact',path) and method=='GET':role('employer');result=s.candidate_detail(u,int(path.split('/')[3]))
    elif path=='/api/invitations' and method=='POST':role('employer');result=s.invite(u,d)
    elif path=='/api/invitations' and method=='GET':result=s.invitations(u)
    elif re.fullmatch(r'/api/invitations/\d+/status',path) and method=='POST':role('candidate');result=s.invitation_status(u,int(path.split('/')[3]),d)
    elif path=='/api/vacancies' and method=='GET':result=s.vacancies(u)
    elif path=='/api/vacancies' and method=='POST':role('employer');result=s.vacancy(u,d)
    elif re.fullmatch(r'/api/vacancies/\d+',path) and method=='PUT':role('employer');result=s.update_vacancy(u,int(path.split('/')[3]),d)
    elif path=='/api/applications' and method=='GET':result=s.applications(u)
    elif path=='/api/applications' and method=='POST':role('candidate');result=s.apply(u,d)
    elif re.fullmatch(r'/api/applications/\d+/status',path) and method=='POST':role('employer');result=s.application_status(u,int(path.split('/')[3]),d)
    elif path=='/api/profile.pdf' and method=='GET':role('candidate');return self.profile_pdf(s.me(u))
    else:raise ApiError(404,'Маршрут не найден')
   self.respond(200,result,cookie=cookie)
  except ApiError as e:self.respond(e.status,{'error':e.message})
  except (ValueError,TypeError):self.respond(400,{'error':'Некорректные данные запроса'})
  except Exception:
   import traceback;traceback.print_exc()
   self.respond(500,{'error':'Внутренняя ошибка сервера'})
 def profile_pdf(self,me):
  try:
   from profile_pdf import build_profile_pdf
   pdf=build_profile_pdf(me)
  except (ImportError,OSError):raise ApiError(503,'Для PDF нужны зависимости и шрифт из комплекта приложения')
  self.respond(200,pdf,'application/pdf')

def create_server(host,port,db,demo=True):
 store=Storage(db)
 if demo:seed(store)
 srv=ThreadingHTTPServer((host,port),Handler);srv.daemon_threads=True;srv.service=Service(store,demo);srv.secure=not demo;srv.rates=defaultdict(deque);srv.rate_lock=threading.Lock()
 return srv
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8080);p.add_argument('--db',default=str(ROOT/'data/platform.sqlite'));p.add_argument('--production',action='store_true');args=p.parse_args()
 if args.production and not os.environ.get('PUBLIC_URL','').startswith('https://'):p.error('Production requires HTTPS PUBLIC_URL and SMTP configuration')
 srv=create_server(args.host,args.port,args.db,not args.production)
 print(f'ФСП / ИТ-подбор: http://{args.host}:{args.port} / {"production" if args.production else "synthetic demo"}',flush=True)
 try:srv.serve_forever()
 except KeyboardInterrupt:pass
 finally:srv.server_close()
