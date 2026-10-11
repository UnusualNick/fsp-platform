"""Exercise a running demo through HTTP. Writes synthetic vacancy/application fixtures."""
import argparse,http.cookiejar,json,time,urllib.request,urllib.error

class Client:
 def __init__(self,base,role):
  self.base=base.rstrip('/');self.csrf=''
  self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  self.csrf=self.call('/api/auth/login','POST',{'email':role+'@example.test','password':'DemoPassword42!'})['csrf']
 def call(self,path,method='GET',data=None):
  req=urllib.request.Request(self.base+path,method=method,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','X-CSRF-Token':self.csrf})
  with self.http.open(req) as r:
   body=r.read()
   return json.loads(body) if r.headers.get_content_type()=='application/json' else body

def run(base):
 with urllib.request.urlopen(base.rstrip('/')+'/api/health') as r:health=json.load(r)
 if not health.get('demo'):raise RuntimeError('Smoke scenario requires a demo instance; production was not modified.')
 employer=Client(base,'employer');candidate=Client(base,'candidate')
 cid=candidate.call('/api/me')['user']['id']
 rows=employer.call('/api/candidates?specialization=backend&grade=Middle&page_size=2')
 assert rows['total']>=2 and len(rows['candidates'])==2
 assert all('contact' not in row for row in rows['candidates'])
 iid=employer.call('/api/invitations','POST',{'candidate_id':cid,'title':'Smoke invitation','description':'Synthetic acceptance scenario','salary_min':180000,'salary_max':220000})['id']
 candidate.call('/api/invitations/'+str(iid)+'/status','POST',{'status':'accepted'})
 assert employer.call('/api/candidates/'+str(cid)+'/contact')['email']=='candidate@example.test'
 vacancy={'title':'Compose smoke '+str(time.time_ns()),'description':'Synthetic test vacancy','specialization':'backend','grade':'Middle','skills':'Python, SQL','salary_min':100000,'salary_max':150000}
 vid=employer.call('/api/vacancies','POST',vacancy)['id']
 vacancy['title']+=' edited';employer.call('/api/vacancies/'+str(vid),'PUT',vacancy)
 assert any(v['id']==vid and v['title']==vacancy['title'] for v in candidate.call('/api/vacancies')['vacancies'])
 aid=candidate.call('/api/applications','POST',{'vacancy_id':vid,'share_contact':True})['id']
 employer.call('/api/applications/'+str(aid)+'/status','POST',{'status':'accepted'})
 assert any(a['id']==aid and a['status']=='accepted' for a in candidate.call('/api/applications')['applications'])
 candidate.call('/api/fsp/link','POST',{'fsp_id':'FSP-DEMO-001','code':'demo-owner-001'})
 assert candidate.call('/api/profile.pdf').startswith(b'%PDF-')
 assert employer.call('/assets/fsp-pattern.png').startswith(b'\x89PNG')
 print(json.dumps({'health':health['status'],'vacancy_id':vid,'vacancy_title':vacancy['title'],'application_id':aid,'result':'passed'},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8080');run(p.parse_args().url)
