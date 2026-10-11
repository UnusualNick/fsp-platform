import http.cookiejar,json,tempfile,threading,unittest,urllib.request,urllib.error,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import create_server
class HttpSecurityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.server=create_server('127.0.0.1',0,Path(cls.tmp.name)/'db.sqlite');cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup()
 def setUp(self):self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def request(self,path,method='GET',data=None,headers=None):
  req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Content-Type':'application/json',**(headers or {})})
  try:
   with self.client.open(req) as r:return r.status,json.loads(r.read()),r.headers
  except urllib.error.HTTPError as r:return r.code,json.loads(r.read()),r.headers
 def login(self,role='employer'):
  status,d,h=self.request('/api/auth/login','POST',{'email':role+'@example.test','password':'DemoPassword42!'});self.assertEqual(200,status);return d['csrf'],h
 def test_csrf_and_origin_blocked(self):
  csrf,h=self.login();self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Lax',h['Set-Cookie'])
  self.assertEqual(403,self.request('/api/profile','PUT',{'name':'Demo','contact':'demo'})[0])
  self.assertEqual(403,self.request('/api/profile','PUT',{'name':'Demo','contact':'demo'},{'X-CSRF-Token':csrf,'Origin':'https://attacker.example'})[0])
  self.assertEqual(200,self.request('/api/profile','PUT',{'name':'Demo','contact':'demo'},{'X-CSRF-Token':csrf})[0])
 def test_unauthorized_and_role_routes(self):
  self.assertEqual(401,self.request('/api/invitations')[0]);self.login('candidate');self.assertEqual(403,self.request('/api/candidates')[0])
 def test_search_excludes_contact_and_password(self):
  self.login();status,d,_=self.request('/api/candidates?specialization=backend&grade=Middle&skills=Python');self.assertEqual(200,status)
  for row in d['candidates']:
   for field in ('email','contact','password','csrf'):self.assertNotIn(field,row)
 def test_candidate_cannot_manage_vacancy_or_application(self):
  csrf,_=self.login('candidate')
  self.assertEqual(403,self.request('/api/vacancies/1','PUT',{}, {'X-CSRF-Token':csrf})[0])
  self.assertEqual(403,self.request('/api/applications/1/status','POST',{'status':'accepted'}, {'X-CSRF-Token':csrf})[0])
