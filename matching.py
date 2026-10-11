"""Explainable ranking within an assessed category, without personal attributes."""
import json
from needs import normalized_skills
from assessment import SPECIALIZATIONS, GRADES

def rank(candidates, need):
 wanted = normalized_skills(need.get('skills', ''))
 ranked=[]
 for row in candidates:
  c=dict(row)
  if not c['published'] or not c['grade'] or c['specialization']!=need['specialization'] or c['grade']!=need['grade']:
   continue
  achievements=json.loads(c['achievements']) if isinstance(c['achievements'],str) else c['achievements']
  # Only verified registry records are evidence; membership is not a ranking signal.
  achievements=[a for a in achievements if a.get('verified') is True]
  if need.get('fsp_only') and not achievements: continue
  skills=normalized_skills(c['skills'])
  coverage = len(wanted & skills)/len(wanted) if wanted else 1
  test_points=round(c['score']*0.3,1)
  skill_points=round(60*coverage,1)
  fsp_points=min(10,len(achievements)*5)
  ranked.append({'id':c['user_id'],'name':c['name'],'specialization':c['specialization'],'grade':c['grade'],'skills':c['skills'],'about':c['about'],'score':c['score'],'achievements':achievements,'fsp_id':c['fsp_id'],'match':round(skill_points+test_points+fsp_points,1),'breakdown':{'skills':skill_points,'assessment':test_points,'fsp':fsp_points},'explanation':f'Категория подтверждена тестом. Совпало {len(wanted & skills)} из {len(wanted)} навыков запроса. Тест: {c["score"]}%. Подтверждённые достижения ФСП: {len(achievements)}. Членство в Федерации не учитывается.','contact_unlocked':False})
 return sorted(ranked,key=lambda c:(-c['match'],-c['score'],c['id']))
