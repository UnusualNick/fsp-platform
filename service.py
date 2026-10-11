"""Business operations. Every visibility rule is enforced here, before JSON serialization."""
import hashlib,hmac,json,re,secrets,time,sqlite3,os,smtplib
from email.message import EmailMessage
from assessment import SPECIALIZATIONS,GRADES,generate,public_form,evaluate
from matching import rank
from needs import parse_need
from practice_bank import generate_practice

DAY=86400
class ApiError(Exception):
 def __init__(self,status,message):self.status=status;self.message=message

def digest(token):return hashlib.sha256(token.encode()).hexdigest()
def hash_password(password):
 salt=secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def check_password(password,stored):
 salt,value=stored.split(':')
 return hmac.compare_digest(value,hashlib.scrypt(password.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex())
def text(data,key,maxlen=2000,required=False):
 value=data.get(key,'')
 if not isinstance(value,str) or len(value)>maxlen:raise ApiError(400,f'Некорректное поле {key}')
 value=value.strip()
 if required and not value:raise ApiError(400,f'Заполните поле {key}')
 return value

def salary(data):
 lo,hi=data.get('salary_min'),data.get('salary_max')
 if type(lo) is not int or type(hi) is not int or not 1<=lo<=hi<=10000000:raise ApiError(400,'Укажите диапазон зарплаты в рублях: от <= до')
 return lo,hi

class Service:
 def __init__(self,store,demo=True):self.store=store;self.demo=demo
 def audit(self,c,uid,event,details=''):
  c.execute('INSERT INTO audit(user_id,event,created,details) VALUES(?,?,?,?)',(uid,event,time.time(),details))
 def auth(self,token,role=None):
  with self.store.connect() as c:
   row=c.execute('SELECT u.id,u.email,u.role,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.verified=1',(digest(token or ''),time.time())).fetchone()
  if not row:raise ApiError(401,'Войдите в аккаунт')
  if role and row['role']!=role:raise ApiError(403,'Действие недоступно для этой роли')
  return dict(row)
 def session(self,c,uid):
  token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
  c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),uid,csrf,time.time()+DAY))
  return token,csrf
 def register(self,d):
  email=text(d,'email',254,True).lower();password=text(d,'password',128,True);role=d.get('role')
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ApiError(400,'Введите корректную почту')
  if len(password)<12:raise ApiError(400,'Пароль должен содержать минимум 12 символов')
  if role not in ('candidate','employer'):raise ApiError(400,'Выберите роль')
  if d.get('consent') is not True:raise ApiError(400,'Нужно согласие на обработку данных')
  token=secrets.token_urlsafe(32);now=time.time()
  try:
   with self.store.connect() as c:
    uid=c.execute('INSERT INTO users(email,password,role,created,consent_at) VALUES(?,?,?,?,?)',(email,hash_password(password),role,now,now)).lastrowid
    c.execute('INSERT INTO '+('profiles' if role=='candidate' else 'companies')+'(user_id) VALUES(?)',(uid,))
    c.execute('INSERT INTO verifications VALUES(?,?,?)',(digest(token),uid,now+3600))
    self.audit(c,uid,'consent.processing','v1')
    if not self.demo:self.send_verification(email,token)
  except sqlite3.IntegrityError:raise ApiError(409,'Аккаунт с этой почтой уже существует')
  result={'message':'Подтвердите адрес по ссылке в письме','demo':self.demo}
  if self.demo:result['verification_token']=token;result['message']='Подтвердите email кнопкой ниже.'
  return result
 def send_verification(self,email,token):
  host=os.environ.get('SMTP_HOST');base=os.environ.get('PUBLIC_URL');sender=os.environ.get('SMTP_FROM')
  if not host or not base or not sender:raise ApiError(503,'SMTP и PUBLIC_URL должны быть настроены')
  msg=EmailMessage();msg['Subject']='Подтверждение email — ФСП / ИТ-подбор';msg['From']=sender;msg['To']=email
  msg.set_content(f'Подтвердите адрес в течение часа: {base}/?verify={token}')
  try:
   with smtplib.SMTP(host,int(os.environ.get('SMTP_PORT','587')),timeout=10) as smtp:
    smtp.starttls()
    if os.environ.get('SMTP_USER'):smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
    smtp.send_message(msg)
  except (OSError,smtplib.SMTPException):raise ApiError(503,'Не удалось отправить письмо. Повторите регистрацию позже.')
 def verify(self,d):
  token=text(d,'token',100,True)
  with self.store.connect() as c:
   row=c.execute('SELECT * FROM verifications WHERE token_hash=? AND expires>?',(digest(token),time.time())).fetchone()
   if not row:raise ApiError(400,'Ссылка недействительна или истекла')
   c.execute('UPDATE users SET verified=1 WHERE id=?',(row['user_id'],));c.execute('DELETE FROM verifications WHERE user_id=?',(row['user_id'],))
   self.audit(c,row['user_id'],'email.verified')
  return {'message':'Email подтверждён. Войдите в аккаунт.'}
 def login(self,d):
  email=text(d,'email',254,True).lower();password=text(d,'password',128,True)
  with self.store.connect() as c:
   row=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
   if not row or not check_password(password,row['password']):raise ApiError(401,'Неверная почта или пароль')
   if not row['verified']:raise ApiError(403,'Сначала подтвердите почту')
   token,csrf=self.session(c,row['id'])
   self.audit(c,row['id'],'login')
  return {'csrf':csrf},token
 def logout(self,token):
  with self.store.connect() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),))
  return {'message':'Вы вышли из аккаунта'}
 def me(self,u):
  with self.store.connect() as c:
   p=dict(c.execute('SELECT * FROM '+('profiles' if u['role']=='candidate' else 'companies')+' WHERE user_id=?',(u['id'],)).fetchone())
   history=[dict(x) for x in c.execute('SELECT id,created,completed,result FROM attempts WHERE user_id=? AND completed IS NOT NULL ORDER BY created DESC',(u['id'],))]
  if u['role']=='candidate':p['achievements']=json.loads(p['achievements'])
  for a in history:a['result']=json.loads(a['result'])
  return {'user':u,'profile':p,'history':history,'demo':self.demo}
 def update_profile(self,u,d):
  if u['role']=='employer':
   fields={k:text(d,k,2000,k in ('name','contact')) for k in ('name','description','contact')}
  else:
   fields={k:text(d,k,2000,k=='name') for k in ('name','skills','about','contact')}
   published=d.get('published',False)
   if type(published) is not bool:raise ApiError(400,'Некорректное согласие на публикацию')
   fields['published']=int(published)
  with self.store.connect() as c:
   c.execute('UPDATE '+('profiles' if u['role']=='candidate' else 'companies')+' SET '+','.join(k+'=?' for k in fields)+' WHERE user_id=?',(*fields.values(),u['id']))
   self.audit(c,u['id'],'profile.updated', 'publish='+str(fields.get('published','n/a')))
  return self.me(u)
 def start_assessment(self,u,d):
  spec=d.get('specialization');grade=d.get('grade');industry=text(d,'industry',100,True)
  if spec not in SPECIALIZATIONS or grade not in GRADES:raise ApiError(400,'Выберите специализацию и грейд')
  now=time.time()
  with self.store.connect() as c:
   # Serialize read + write so concurrent starts cannot bypass cooldown or attempt limits.
   c.execute('BEGIN IMMEDIATE')
   p=c.execute('SELECT * FROM profiles WHERE user_id=?',(u['id'],)).fetchone()
   if not p['name']:raise ApiError(400,'Сначала заполните имя в профиле')
   if p['grade_changed'] and now-p['grade_changed']<90*DAY:
    raise ApiError(409,'Подтверждённую категорию можно менять раз в 90 дней')
   active=c.execute('SELECT * FROM attempts WHERE user_id=? AND completed IS NULL AND expires>?',(u['id'],now)).fetchone()
   if active:raise ApiError(409,'Уже есть активный тест. Завершите его или дождитесь окончания 20 минут.')
   count=c.execute('SELECT COUNT(*) FROM attempts WHERE user_id=? AND created>?',(u['id'],now-DAY)).fetchone()[0]
   if count>=3:raise ApiError(429,'Не более трёх тестов в сутки')
   form=generate(spec,grade);aid=secrets.token_urlsafe(18)
   c.execute('INSERT INTO attempts(id,user_id,form,created,expires) VALUES(?,?,?,?,?)',(aid,u['id'],json.dumps(form,ensure_ascii=False),now,now+1200))
   c.execute('UPDATE profiles SET claimed_grade=?,industry=? WHERE user_id=?',(grade,industry,u['id']))
  return {**public_form(form),'attempt_id':aid,'expires':now+1200}
 def active_assessment(self,u):
  with self.store.connect() as c:row=c.execute('SELECT * FROM attempts WHERE user_id=? AND completed IS NULL AND expires>? ORDER BY created DESC LIMIT 1',(u['id'],time.time())).fetchone()
  if not row:return {'active':None}
  return {'active':{**public_form(json.loads(row['form'])),'attempt_id':row['id'],'expires':row['expires']}}
 def submit_assessment(self,u,d):
  aid=text(d,'attempt_id',100,True);now=time.time()
  with self.store.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   a=c.execute('SELECT * FROM attempts WHERE id=? AND user_id=?',(aid,u['id'])).fetchone()
   if not a:raise ApiError(404,'Тест не найден')
   if a['completed']:raise ApiError(409,'Тест уже завершён')
   if now>a['expires']:raise ApiError(409,'Время теста истекло')
   form=json.loads(a['form'])
   try:result=evaluate(form,d.get('answers'))
   except ValueError as e:raise ApiError(400,str(e))
   result.update({'grade':form['grade'],'specialization':form['specialization'],'version':form['version']})
   if result['passed']:
    c.execute('UPDATE profiles SET grade=?,specialization=?,score=?,grade_changed=? WHERE user_id=?',(form['grade'],form['specialization'],result['score'],now,u['id']))
   c.execute('UPDATE attempts SET completed=?,result=? WHERE id=?',(now,json.dumps(result),aid))
   self.audit(c,u['id'],'assessment.completed',json.dumps(result))
  return result
 def link_fsp(self,u,d):
  if not self.demo:raise ApiError(503,'Реальный реестр ФСП ещё не подключён')
  fid=text(d,'fsp_id',100,True);code=text(d,'code',100,True)
  from seed import REGISTRY
  row=REGISTRY.get(fid)
  if not row or row['email']!=u['email'] or not hmac.compare_digest(row['code'],code):raise ApiError(400,'Проверьте ID, код и email владельца записи')
  with self.store.connect() as c:
   c.execute('UPDATE profiles SET fsp_id=?,achievements=? WHERE user_id=?',(fid,json.dumps(row['achievements'],ensure_ascii=False),u['id']))
   self.audit(c,u['id'],'fsp.linked',fid)
  return self.me(u)
 def candidates(self,u,q):
  spec=q.get('specialization','backend');grade=q.get('grade','Middle')
  if spec not in SPECIALIZATIONS or grade not in GRADES:raise ApiError(400,'Неизвестная категория')
  with self.store.connect() as c:rows=c.execute('SELECT * FROM profiles JOIN users ON users.id=profiles.user_id WHERE verified=1').fetchall()
  result=rank(rows,{'specialization':spec,'grade':grade,'skills':q.get('skills',''),'fsp_only':q.get('fsp_only')=='true'})
  try:
   page=int(q.get('page',1));size=int(q.get('page_size',10));min_score=float(q.get('min_score',0));min_match=float(q.get('min_match',0))
  except (ValueError,TypeError):raise ApiError(400,'Некорректные параметры фильтра')
  if page<1 or size not in (2,10,20,50) or not 0<=min_score<=100 or not 0<=min_match<=100:raise ApiError(400,'Некорректные параметры фильтра')
  if q.get('skills_mode','any') not in ('any','all'):raise ApiError(400,'Неизвестное условие технологий')
  sort=q.get('sort','match')
  if sort not in ('match','score','name'):raise ApiError(400,'Неизвестная сортировка')
  query=q.get('query','').strip().casefold()
  result=[c for c in result if c['score']>=min_score and c['match']>=min_match and (not query or query in (c['name']+' '+c['about']).casefold()) and (q.get('skills_mode')!='all' or c['breakdown']['skills']==60)]
  if sort=='score':result.sort(key=lambda c:(-c['score'],c['id']))
  if sort=='name':result.sort(key=lambda c:(c['name'].casefold(),c['id']))
  total=len(result);pages=max(1,(total+size-1)//size);page=min(page,pages)
  summary={'full_stack':sum(c['breakdown']['skills']==60 for c in result),'fsp':sum(bool(c['achievements']) for c in result)}
  return {'candidates':result[(page-1)*size:page*size],'category':f'{SPECIALIZATIONS[spec]} / {grade}','total':total,'page':page,'page_size':size,'pages':pages,'summary':summary}

 def candidate_detail(self,u,cid):
  with self.store.connect() as c:
   p=c.execute('SELECT p.*,u.email FROM profiles p JOIN users u ON u.id=p.user_id WHERE user_id=? AND u.verified=1',(cid,)).fetchone()
   if not p:raise ApiError(404,'Кандидат не найден')
   unlocked=c.execute("SELECT 1 FROM invitations WHERE employer_id=? AND candidate_id=? AND status='accepted'",(u['id'],cid)).fetchone()
   applied=c.execute('SELECT 1 FROM applications a JOIN vacancies v ON a.vacancy_id=v.id WHERE a.candidate_id=? AND v.employer_id=?',(cid,u['id'])).fetchone()
   if not p['published'] and not unlocked and not applied:raise ApiError(404,'Профиль скрыт')
   if not unlocked and not applied:raise ApiError(403,'Контакты доступны после согласия кандидата')
  return {'id':cid,'name':p['name'],'email':p['email'],'contact':p['contact']}
 def invite(self,u,d):
  cid=d.get('candidate_id');lo,hi=salary(d);title=text(d,'title',200,True);description=text(d,'description',4000,True)
  if type(cid) is not int:raise ApiError(400,'Выберите кандидата')
  with self.store.connect() as c:
   p=c.execute('SELECT p.* FROM profiles p JOIN users u ON u.id=p.user_id WHERE user_id=? AND published=1 AND grade IS NOT NULL AND u.verified=1',(cid,)).fetchone()
   if not p:raise ApiError(404,'Кандидат недоступен для приглашения')
   company=c.execute('SELECT * FROM companies WHERE user_id=?',(u['id'],)).fetchone()
   if not company['name'] or not company['contact']:raise ApiError(400,'Заполните название и контакты компании')
   now=time.time()
   iid=c.execute('INSERT INTO invitations(employer_id,candidate_id,title,description,salary_min,salary_max,created,updated,company_name,company_contact) VALUES(?,?,?,?,?,?,?,?,?,?)',(u['id'],cid,title,description,lo,hi,now,now,company['name'],company['contact'])).lastrowid
   self.audit(c,u['id'],'invitation.sent',str(iid))
  return {'id':iid,'status':'sent'}
 def invitations(self,u):
  field='candidate_id' if u['role']=='candidate' else 'employer_id'
  with self.store.connect() as c:rows=c.execute(f'SELECT i.*,p.name AS candidate_name FROM invitations i JOIN profiles p ON p.user_id=i.candidate_id WHERE {field}=? ORDER BY i.id DESC',(u['id'],)).fetchall()
  return {'invitations':[dict(r) for r in rows]}
 def invitation_status(self,u,iid,d):
  status=d.get('status')
  if status not in ('viewed','accepted','declined'):raise ApiError(400,'Недопустимый статус')
  with self.store.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   i=c.execute('SELECT * FROM invitations WHERE id=? AND candidate_id=?',(iid,u['id'])).fetchone()
   if not i:raise ApiError(404,'Приглашение не найдено')
   if i['status'] in ('accepted','declined'):raise ApiError(409,'Решение уже принято')
   if status=='viewed' and i['status']=='viewed':return {'status':'viewed'}
   c.execute('UPDATE invitations SET status=?,updated=? WHERE id=?',(status,time.time(),iid));self.audit(c,u['id'],'invitation.'+status,str(iid))
  return {'status':status}
 def vacancy(self,u,d):
  lo,hi=salary(d);spec=d.get('specialization');grade=d.get('grade')
  if spec not in SPECIALIZATIONS or grade not in GRADES:raise ApiError(400,'Некорректная категория')
  fields=[text(d,'title',200,True),text(d,'description',4000,True),spec,grade,text(d,'skills',1000,True),lo,hi]
  with self.store.connect() as c:
   company=c.execute('SELECT * FROM companies WHERE user_id=?',(u['id'],)).fetchone()
   if not company['name'] or not company['contact']:raise ApiError(400,'Заполните профиль компании')
   vid=c.execute('INSERT INTO vacancies(employer_id,title,description,specialization,grade,skills,salary_min,salary_max,created) VALUES(?,?,?,?,?,?,?,?,?)',(u['id'],*fields,time.time())).lastrowid
  return {'id':vid}
 def vacancies(self,u):
  with self.store.connect() as c:rows=c.execute('SELECT v.*,c.name AS company_name,c.contact AS company_contact FROM vacancies v JOIN companies c ON c.user_id=v.employer_id ORDER BY id DESC').fetchall()
  return {'vacancies':[dict(x) for x in rows]}
 def update_vacancy(self,u,vid,d):
  lo,hi=salary(d);spec=d.get('specialization');grade=d.get('grade')
  if spec not in SPECIALIZATIONS or grade not in GRADES:raise ApiError(400,'Некорректная категория')
  values=[text(d,'title',200,True),text(d,'description',4000,True),spec,grade,text(d,'skills',1000,True),lo,hi]
  with self.store.connect() as c:
   if not c.execute('SELECT 1 FROM vacancies WHERE id=? AND employer_id=?',(vid,u['id'])).fetchone():raise ApiError(404,'Вакансия не найдена')
   c.execute('UPDATE vacancies SET title=?,description=?,specialization=?,grade=?,skills=?,salary_min=?,salary_max=? WHERE id=? AND employer_id=?',(*values,vid,u['id']))
   self.audit(c,u['id'],'vacancy.updated',str(vid))
  return {'id':vid}
 def application_status(self,u,aid,d):
  status=d.get('status')
  if status not in ('viewed','accepted','declined'):raise ApiError(400,'Недопустимый статус')
  with self.store.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   row=c.execute('SELECT a.status FROM applications a JOIN vacancies v ON v.id=a.vacancy_id WHERE a.id=? AND v.employer_id=?',(aid,u['id'])).fetchone()
   if not row:raise ApiError(404,'Отклик не найден')
   if row['status'] in ('accepted','declined'):raise ApiError(409,'Решение уже принято')
   c.execute('UPDATE applications SET status=? WHERE id=?',(status,aid));self.audit(c,u['id'],'application.'+status,str(aid))
  return {'id':aid,'status':status}
 def apply(self,u,d):
  vid=d.get('vacancy_id')
  if type(vid) is not int or d.get('share_contact') is not True:raise ApiError(400,'Для отклика подтвердите передачу контактов')
  try:
   with self.store.connect() as c:
    if not c.execute('SELECT 1 FROM vacancies WHERE id=?',(vid,)).fetchone():raise ApiError(404,'Вакансия не найдена')
    aid=c.execute('INSERT INTO applications(vacancy_id,candidate_id,created) VALUES(?,?,?)',(vid,u['id'],time.time())).lastrowid
    self.audit(c,u['id'],'application.contact_consent',str(vid))
  except sqlite3.IntegrityError:raise ApiError(409,'Вы уже откликнулись')
  return {'id':aid,'status':'sent'}
 def applications(self,u):
  with self.store.connect() as c:
   where='a.candidate_id=?' if u['role']=='candidate' else 'v.employer_id=?'
   rows=c.execute('SELECT a.*,v.title,c.name AS company_name,p.name AS candidate_name FROM applications a JOIN vacancies v ON v.id=a.vacancy_id JOIN companies c ON c.user_id=v.employer_id JOIN profiles p ON p.user_id=a.candidate_id WHERE '+where+' ORDER BY a.id DESC',(u['id'],)).fetchall()
  return {'applications':[dict(r) for r in rows]}

 def need_preview(self,u,d):
  if u['role']!='employer':raise ApiError(403,'Действие недоступно для этой роли')
  return parse_need(text(d,'description',4000,True))
 def practice(self,u):
  if u['role']!='candidate':raise ApiError(403,'Действие недоступно для этой роли')
  now=time.time()
  with self.store.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   profile=c.execute('SELECT specialization,grade FROM profiles WHERE user_id=?',(u['id'],)).fetchone()
   if not profile['grade']:raise ApiError(400,'Сначала подтвердите категорию тестом')
   latest=c.execute('SELECT * FROM practice WHERE user_id=? ORDER BY created DESC LIMIT 1',(u['id'],)).fetchone()
   if not latest or now>=latest['created']+7*DAY:
    form=generate_practice(profile['specialization'])
    pid=secrets.token_urlsafe(24)
    c.execute('INSERT INTO practice(id,user_id,specialization,form,created,expires) VALUES(?,?,?,?,?,?)',(pid,u['id'],profile['specialization'],json.dumps(form,ensure_ascii=False),now,now+7*DAY))
    latest=c.execute('SELECT * FROM practice WHERE id=?',(pid,)).fetchone()
    self.audit(c,u['id'],'practice.assigned',pid)
   history=[{'id':r['id'],'created':r['created'],'completed':r['completed'],'specialization':r['specialization'],'result':json.loads(r['result'])} for r in c.execute('SELECT * FROM practice WHERE user_id=? AND completed IS NOT NULL ORDER BY created DESC LIMIT 20',(u['id'],))]
  form=json.loads(latest['form'])
  return {'id':latest['id'],'specialization':latest['specialization'],'questions':[] if latest['completed'] else public_form(form)['questions'],'completed':latest['completed'],'expires':latest['expires'],'next_at':latest['created']+7*DAY,'history':history}
 def submit_practice(self,u,d):
  if u['role']!='candidate':raise ApiError(403,'Действие недоступно для этой роли')
  pid=text(d,'id',100,True);answers=d.get('answers');now=time.time()
  with self.store.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   row=c.execute('SELECT * FROM practice WHERE id=? AND user_id=?',(pid,u['id'])).fetchone()
   if not row:raise ApiError(404,'Задание не найдено')
   if row['completed']:raise ApiError(409,'Ответ уже сохранён')
   if now>=row['expires']:raise ApiError(409,'Срок задания истёк')
   questions=json.loads(row['form'])['questions']
   if not isinstance(answers,dict) or set(answers)!={q['id'] for q in questions} or any(type(answers[q['id']]) is not int or not 0<=answers[q['id']]<len(q['options']) for q in questions):raise ApiError(400,'Ответьте на каждое задание')
   result={'correct':sum(answers[q['id']]==q['answer'] for q in questions),'total':len(questions),'feedback':[{'prompt':q['prompt'],'correct':answers[q['id']]==q['answer'],'answer':q['options'][q['answer']]} for q in questions]}
   c.execute('UPDATE practice SET completed=?,result=? WHERE id=?',(now,json.dumps(result,ensure_ascii=False),pid));self.audit(c,u['id'],'practice.completed',pid)
  return result
