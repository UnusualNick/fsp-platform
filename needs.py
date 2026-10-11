"""Local, editable extraction of common IT requirements; no external model."""
import re
ALIASES = {
 'JavaScript': ('javascript','js','джаваскрипт'), 'TypeScript': ('typescript','ts'),
 'PostgreSQL': ('postgresql','postgres','psql','постгрес'), 'Python': ('python','питон'),
 'React': ('react','react.js','reactjs'), 'Node.js': ('node.js','nodejs','node'),
 'SQL': ('sql',), 'Docker': ('docker','докер'), 'Git': ('git',),
 'HTML': ('html',), 'CSS': ('css',), 'Pandas': ('pandas',), 'Linux': ('linux',),
 'FastAPI': ('fastapi',), 'Django': ('django',), 'Redis': ('redis',),
}
def normalized_skills(value):
 lookup={alias.casefold(): name.casefold() for name,aliases in ALIASES.items() for alias in aliases}
 return {lookup.get(part.strip().casefold(),part.strip().casefold()) for part in value.split(',') if part.strip()}
def mentioned(text,term):
 return bool(re.search(r'(?<![\w])'+re.escape(term)+r'(?![\w])',text,re.I))
def parse_need(value):
 skills=[name for name,aliases in ALIASES.items() if any(mentioned(value,a) for a in aliases)]
 scores={
 'backend': sum(mentioned(value,a) for a in ('backend','бэкенд','бекенд','сервер','api','django','fastapi','node.js')),
 'frontend': sum(mentioned(value,a) for a in ('frontend','фронтенд','фронт','интерфейс','react','javascript','typescript','html','css')),
 'data': sum(mentioned(value,a) for a in ('data','аналитик','аналитика','данных','pandas','ml','машинное обучение')),
 }
 grades=[g for g,terms in {'Junior':('junior','джуниор','джун'), 'Middle':('middle','мидл','миддл'), 'Senior':('senior','сеньор','синьор')}.items() if any(mentioned(value,t) for t in terms)]
 categories=[{'specialization':s,'grade':grades[0] if len(grades)==1 else None} for s,n in sorted(scores.items(),key=lambda x:-x[1]) if n]
 return {'skills':', '.join(skills),'categories':categories,'grade':grades[0] if len(grades)==1 else None,
 'message':'Проверьте требования перед поиском. Нераспознанные технологии добавьте вручную'}
