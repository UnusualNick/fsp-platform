import json,tempfile,unittest,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage import Storage
from service import Service,ApiError
from assessment import generate,evaluate,GRADES,SPECIALIZATIONS
from seed import seed
class PlatformTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=Storage(Path(self.tmp.name)/'test.sqlite');seed(self.db);self.s=Service(self.db)
  self.emp=self.user('employer@example.test');self.candidate=self.user('candidate@example.test');self.other=self.user('candidate1@example.test')
 def tearDown(self):self.tmp.cleanup()
 def user(self,email):
  with self.db.connect() as c:r=c.execute('SELECT id,email,role FROM users WHERE email=?',(email,)).fetchone()
  return dict(r)
 def error(self,status,fn,*args):
  with self.assertRaises(ApiError) as ctx:fn(*args)
  self.assertEqual(status,ctx.exception.status)
 def start(self,grade='Middle'):
  return self.s.start_assessment(self.candidate,{'industry':'ИТ','specialization':'backend','grade':grade})
 def answers(self,a,correct=True):
  with self.db.connect() as c:f=json.loads(c.execute('SELECT form FROM attempts WHERE id=?',(a['attempt_id'],)).fetchone()[0])
  return {'attempt_id':a['attempt_id'],'answers':{q['id']:q['answer'] if correct else (q['answer']+1)%4 for q in f['questions']}}
 def test_registration_requires_confirmation(self):
  d={'email':'new@example.test','password':'LongPassword42!','role':'candidate','consent':True};reg=self.s.register(d);self.error(403,self.s.login,d)
  self.s.verify({'token':reg['verification_token']});_,token=self.s.login(d);self.assertEqual(d['email'],self.s.auth(token)['email']);self.error(400,self.s.verify,{'token':reg['verification_token']})
 def test_consent_and_password_rules(self):
  d={'email':'new@example.test','password':'short','role':'candidate','consent':True};self.error(400,self.s.register,d)
  d.update(password='LongPassword42!',consent=False);self.error(400,self.s.register,d)
 def test_role_boundary(self):
  _,token=self.s.login({'email':'candidate@example.test','password':'DemoPassword42!'});self.error(403,self.s.auth,token,'employer')
 def test_category_and_no_contact_in_search(self):
  r=self.s.candidates(self.emp,{'specialization':'backend','grade':'Middle','skills':'Python, PostgreSQL'});self.assertEqual(4,r['total']);self.assertEqual(self.candidate['id'],r['candidates'][0]['id'])
  for row in r['candidates']:self.assertNotIn('contact',row);self.assertNotIn('email',row);self.assertEqual('Middle',row['grade'])
 def test_search_pagination_and_filters(self):
  q={'specialization':'backend','grade':'Middle','skills':'Python, PostgreSQL','page_size':'2'}
  first=self.s.candidates(self.emp,q);second=self.s.candidates(self.emp,{**q,'page':'2'})
  self.assertEqual(4,first['total']);self.assertEqual(2,first['pages']);self.assertEqual(first['summary'],second['summary'])
  self.assertFalse({c['id'] for c in first['candidates']} & {c['id'] for c in second['candidates']})
  filtered=self.s.candidates(self.emp,{**q,'skills_mode':'all','min_score':'84','min_match':'80'})
  self.assertTrue(all(c['score']>=84 and c['match']>=80 and c['breakdown']['skills']==60 for c in filtered['candidates']))
  name=first['candidates'][0]['name'];found=self.s.candidates(self.emp,{**q,'query':name})
  self.assertEqual(1,found['total']);self.assertEqual(name,found['candidates'][0]['name'])
  self.error(400,self.s.candidates,self.emp,{**q,'page':'0'})
  self.error(400,self.s.candidates,self.emp,{**q,'min_match':'nan'})
 def test_private_and_unassessed_excluded(self):
  with self.db.connect() as c:c.execute('UPDATE profiles SET published=0 WHERE user_id=?',(self.candidate['id'],))
  ids=[r['id'] for r in self.s.candidates(self.emp,{'specialization':'backend','grade':'Middle'})['candidates']];self.assertNotIn(self.candidate['id'],ids)
  with self.db.connect() as c:c.execute('UPDATE profiles SET grade=NULL WHERE user_id=?',(ids[0],))
  self.assertEqual(2,self.s.candidates(self.emp,{'specialization':'backend','grade':'Middle'})['total'])
 def test_fsp_absent_profile_works(self):
  rows=self.s.candidates(self.emp,{'specialization':'backend','grade':'Middle'})['candidates'];self.assertTrue(any(not r['achievements'] for r in rows))
  rows=self.s.candidates(self.emp,{'specialization':'backend','grade':'Middle','fsp_only':'true'})['candidates'];self.assertTrue(all(r['achievements'] for r in rows))
 def test_fsp_link_owner_validation(self):
  d={'fsp_id':'FSP-DEMO-001','code':'demo-owner-001'};self.error(400,self.s.link_fsp,self.other,d);self.assertEqual(2,len(self.s.link_fsp(self.candidate,d)['profile']['achievements']))
 def test_unverified_achievement_does_not_rank_or_pass_fsp_filter(self):
  q={'specialization':'backend','grade':'Middle','skills':'Python, PostgreSQL'}
  before=next(r for r in self.s.candidates(self.emp,q)['candidates'] if r['id']==self.candidate['id'])
  with self.db.connect() as c:
   c.execute('UPDATE profiles SET achievements=? WHERE user_id=?',(json.dumps([{'event':'Unverified claim','verified':False}]),self.candidate['id']))
  after=next(r for r in self.s.candidates(self.emp,q)['candidates'] if r['id']==self.candidate['id'])
  self.assertEqual([],after['achievements']);self.assertEqual(0,after['breakdown']['fsp'])
  self.assertEqual(before['match']-before['breakdown']['fsp'],after['match'])
  self.assertNotIn(self.candidate['id'],[r['id'] for r in self.s.candidates(self.emp,{**q,'fsp_only':'true'})['candidates']])
 def test_membership_fields_cannot_change_profile_or_ranking(self):
  q={'specialization':'backend','grade':'Middle'}
  before=self.s.candidates(self.emp,q)['candidates']
  p=self.s.me(self.candidate)['profile']
  self.s.update_profile(self.candidate,{**p,'published':True,'fsp_member':True,'membership_paid':True,'sports_rank':'Master'})
  after=self.s.candidates(self.emp,q)['candidates']
  self.assertEqual(before,after)
  self.assertNotIn('fsp_member',self.s.me(self.candidate)['profile'])
 def test_contact_unlock_after_accept_only(self):
  self.error(403,self.s.candidate_detail,self.emp,self.candidate['id']);iid=self.s.invitations(self.candidate)['invitations'][0]['id']
  self.s.invitation_status(self.candidate,iid,{'status':'viewed'});self.error(403,self.s.candidate_detail,self.emp,self.candidate['id']);self.s.invitation_status(self.candidate,iid,{'status':'accepted'})
  self.assertEqual(self.candidate['email'],self.s.candidate_detail(self.emp,self.candidate['id'])['email']);self.error(409,self.s.invitation_status,self.candidate,iid,{'status':'declined'})
 def test_other_candidate_cannot_change_invitation(self):
  iid=self.s.invitations(self.candidate)['invitations'][0]['id'];self.error(404,self.s.invitation_status,self.other,iid,{'status':'accepted'});self.assertEqual([],self.s.invitations(self.other)['invitations'])
 def test_salary_required(self):
  d={'candidate_id':self.candidate['id'],'title':'Работа','description':'Команда','salary_min':250000,'salary_max':100000};self.error(400,self.s.invite,self.emp,d)
  d['salary_max']=300000;self.assertEqual('sent',self.s.invite(self.emp,d)['status'])
 def test_answer_secrecy_single_submit_and_cooldown(self):
  a=self.start();self.assertTrue(all('answer' not in q for q in a['questions']));d=self.answers(a);self.assertTrue(self.s.submit_assessment(self.candidate,d)['passed'])
  self.error(409,self.s.submit_assessment,self.candidate,d);self.error(409,self.start,'Senior')
 def test_failed_test_does_not_downgrade(self):
  grade=self.s.me(self.candidate)['profile']['grade'];a=self.start('Senior');r=self.s.submit_assessment(self.candidate,self.answers(a,False));self.assertFalse(r['passed']);self.assertEqual(grade,self.s.me(self.candidate)['profile']['grade'])
 def test_attempt_ownership_and_expiry(self):
  a=self.start();self.error(404,self.s.submit_assessment,self.other,{'attempt_id':a['attempt_id'],'answers':{}})
  with self.db.connect() as c:c.execute('UPDATE attempts SET expires=0 WHERE id=?',(a['attempt_id'],))
  self.error(409,self.s.submit_assessment,self.candidate,self.answers(a))
 def test_grade_cannot_be_edited_in_profile(self):
  self.s.update_profile(self.candidate,{'name':'Test','skills':'Python','grade':'Senior','score':100,'published':True});self.assertEqual('Middle',self.s.me(self.candidate)['profile']['grade'])
 def test_application_requires_contact_consent(self):
  self.error(400,self.s.apply,self.other,{'vacancy_id':1});self.s.apply(self.other,{'vacancy_id':1,'share_contact':True});self.assertEqual(self.other['email'],self.s.candidate_detail(self.emp,self.other['id'])['email']);self.error(409,self.s.apply,self.other,{'vacancy_id':1,'share_contact':True})
 def test_vacancy_edit_owner_and_salary_validation(self):
  v=self.s.vacancies(self.emp)['vacancies'][0]
  changed={**v,'title':'Updated vacancy','salary_min':100000,'salary_max':200000}
  self.error(404,self.s.update_vacancy,{'id':99999},v['id'],changed)
  self.error(400,self.s.update_vacancy,self.emp,v['id'],{**changed,'salary_max':1})
  self.s.update_vacancy(self.emp,v['id'],changed)
  updated=next(x for x in self.s.vacancies(self.candidate)['vacancies'] if x['id']==v['id'])
  self.assertEqual('Updated vacancy',updated['title']);self.assertEqual(200000,updated['salary_max'])
 def test_application_status_owned_by_employer_and_final(self):
  a=self.s.apply(self.other,{'vacancy_id':1,'share_contact':True})
  self.error(404,self.s.application_status,{'id':99999},a['id'],{'status':'accepted'})
  self.error(400,self.s.application_status,self.emp,a['id'],{'status':'invalid'})
  self.s.application_status(self.emp,a['id'],{'status':'viewed'})
  self.s.application_status(self.emp,a['id'],{'status':'accepted'})
  self.assertEqual('accepted',self.s.applications(self.other)['applications'][0]['status'])
  self.error(409,self.s.application_status,self.emp,a['id'],{'status':'declined'})
 def test_forms_distinct_options_correct_scoring(self):
  for spec in SPECIALIZATIONS:
   for grade in GRADES:
    for seedval in range(50):
     f=generate(spec,grade,seedval);self.assertTrue(all(len(set(q['options']))==4 for q in f['questions']));self.assertEqual(100,evaluate(f,{q['id']:q['answer'] for q in f['questions']})['score'])
 def test_extended_form_coverage_and_pass_boundary(self):
  from question_bank import CORE
  import math
  for spec in SPECIALIZATIONS:
   for grade in GRADES:
    f=generate(spec,grade,42)
    self.assertEqual(12,len(f['questions']))
    self.assertTrue(set(CORE[spec])<=set(q['skill'] for q in f['questions']))
    required=math.ceil(f['threshold']*len(f['questions'])/100)
    for count in [required-1,required]:
     answers={q['id']:q['answer'] if i<count else (q['answer']+1)%4 for i,q in enumerate(f['questions'])}
     self.assertEqual(count>=required,evaluate(f,answers)['passed'])
  # A stored legacy attempt must still score against its own six questions.
  old={**f,'questions':f['questions'][:6],'version':'2026.10.1'}
  self.assertTrue(evaluate(old,{q['id']:q['answer'] for q in old['questions']})['passed'])
 def test_session_logout(self):
  _,token=self.s.login({'email':self.candidate['email'],'password':'DemoPassword42!'});self.s.logout(token);self.error(401,self.s.auth,token)
