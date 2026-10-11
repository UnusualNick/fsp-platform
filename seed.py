"""Every identity and result in this seed is synthetic, never an FSP registry export."""
import json,time
from pathlib import Path
from assessment import SPECIALIZATIONS,GRADES
DEMO_PASSWORD='DemoPassword42!'
REGISTRY={'FSP-DEMO-001':{'email':'candidate@example.test','code':'demo-owner-001','achievements':[{'event':'Кубок алгоритмов','discipline':'Алгоритмическое программирование','place':3,'participants':120,'date':'2026-09-12','source':'Синтетический реестр MVP','verified':True},{'event':'Хакатон по продуктовой разработке','discipline':'Продуктовая разработка','place':2,'participants':48,'date':'2026-08-20','source':'Синтетический реестр MVP','verified':True}]}}
NAMES=['Алексей Волков','Мария Соколова','Илья Орлов','Анна Кузнецова','Дмитрий Новиков','София Морозова','Максим Лебедев','Алиса Попова','Никита Серов','Дарья Белова','Кирилл Фомин','Елена Павлова']
STACKS={'backend':['Python, PostgreSQL, Docker','Go, PostgreSQL, Redis','Python, Django, SQL','Java, Spring, Kafka'],'frontend':['TypeScript, React, CSS','JavaScript, Vue, HTML','TypeScript, React, Accessibility','JavaScript, CSS, Web APIs'],'data':['Python, SQL, pandas','SQL, ClickHouse, BI','Python, pandas, Statistics','Python, SQL, ML']}
def seed(store):
 from service import hash_password
 with store.connect() as c:
  if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]:return
  now=time.time()
  def user(email,role):
   uid=c.execute('INSERT INTO users(email,password,role,verified,created,consent_at) VALUES(?,?,?,?,?,?)',(email,hash_password(DEMO_PASSWORD),role,1,now,now)).lastrowid
   return uid
  employer=user('employer@example.test','employer')
  c.execute('INSERT INTO companies VALUES(?,?,?,?)',(employer,'Орбита Технологии','Создаём инструменты для разработчиков','talent@orbita.example.test'))
  dataset=[]
  for si,(spec,label) in enumerate(SPECIALIZATIONS.items()):
   for gi,grade in enumerate(GRADES):
    for j in range(4):
     ix=si*12+gi*4+j
     email='candidate@example.test' if ix==4 else f'candidate{ix+1}@example.test'
     uid=user(email,'candidate');name=NAMES[ix%12]
     ach=REGISTRY['FSP-DEMO-001']['achievements'] if ix==4 else ([{'event':'Турнир по программированию № '+str(ix+1),'discipline':'Спортивное программирование','place':j+1,'participants':80,'date':'2026-09-01','source':'Синтетический реестр MVP','verified':True}] if j%2==0 else [])
     fsp_id='FSP-DEMO-001' if ix==4 else (f'FSP-SEED-{ix:03}' if ach else None)
     # Seed results are scenario fixtures, not actual completed assessments.
     score=[100,83.3,100,100][j] if grade!='Senior' else 100
     skills=STACKS[spec][j]
     c.execute('INSERT INTO profiles(user_id,name,skills,about,contact,specialization,grade,claimed_grade,score,published,fsp_id,achievements,grade_changed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(uid,name,skills,f'{label}. Работаю в команде над сервисами и внутренними инструментами',f'@demo_candidate_{ix+1}',spec,grade,grade,score,1,fsp_id,json.dumps(ach,ensure_ascii=False),now-91*86400))
     dataset.append({'synthetic':True,'id':uid,'name':name,'specialization':spec,'grade':grade,'skills':skills,'score':score,'fsp_achievement_count':len(ach)})
  for spec,grade,title,skills,lo,hi in [('backend','Middle','Backend-разработчик платформы','Python, PostgreSQL',180000,260000),('frontend','Middle','Frontend-разработчик продукта','TypeScript, React',170000,240000),('data','Junior','Аналитик продуктовой команды','Python, SQL',90000,140000)]:
   c.execute('INSERT INTO vacancies(employer_id,title,description,specialization,grade,skills,salary_min,salary_max,created) VALUES(?,?,?,?,?,?,?,?,?)',(employer,title,'Разрабатываем веб-сервис удалённо. Задачи и условия обсудим на собеседовании',spec,grade,skills,lo,hi,now))
  profile=c.execute("SELECT user_id FROM profiles JOIN users ON users.id=profiles.user_id WHERE email='candidate@example.test'").fetchone()
  c.execute('INSERT INTO invitations(employer_id,candidate_id,title,description,salary_min,salary_max,created,updated,company_name,company_contact) VALUES(?,?,?,?,?,?,?,?,?,?)',(employer,profile['user_id'],'Разработчик Backend','Ваш подтверждённый профиль подходит команде. Предлагаем обсудить продукт и условия',180000,260000,now,now,'Орбита Технологии','talent@orbita.example.test'))
 return dataset
