"""Reproducible fixture validation. Results are not a real hiring quality estimate."""
import json,tempfile,time,statistics,hashlib,random,math
from pathlib import Path
from storage import Storage
from service import Service
from seed import seed
from assessment import generate,evaluate,SPECIALIZATIONS,GRADES
from matching import rank
ROOT=Path(__file__).resolve().parent

def assessment_validation(legacy=False):
 """Two fresh forms per synthetic profile; probabilities are assumptions, not labels."""
 categories=[]
 for spec_index,spec in enumerate(SPECIALIZATIONS):
  for grade in GRADES:
   profiles=[]
   for i in range(150):
    # A spread of assumed proficiency, including profiles near the pass cutoff.
    probability=0.25+0.74*i/149
    attempts=[]
    for attempt in range(2):
     form=generate(spec,grade,10000+i*2+attempt)
     if legacy:form={**form,'questions':form['questions'][:6]}
     rng=random.Random(20261011+spec_index*100000+GRADES.index(grade)*10000+i*2+attempt)
     answers={}
     correct=[]
     for q in form['questions']:
      success=rng.random()<probability
      answers[q['id']]=q['answer'] if success else (q['answer']+1)%4
      correct.append(int(success))
     attempts.append({**evaluate(form,answers),'items':correct})
    profiles.append(attempts)
   first=[p[0]['score'] for p in profiles];second=[p[1]['score'] for p in profiles]
   mx=statistics.mean(first);my=statistics.mean(second)
   denom=math.sqrt(sum((x-mx)**2 for x in first)*sum((y-my)**2 for y in second))
   ordered=sorted((p[0] for p in profiles),key=lambda a:a['score'])
   n=round(len(ordered)*0.27)
   borderline=[p for i,p in enumerate(profiles) if abs((0.25+0.74*i/149)*100-form['threshold'])<=10]
   pa=statistics.mean(p[0]['passed'] for p in profiles);pb=statistics.mean(p[1]['passed'] for p in profiles)
   agreement=statistics.mean(p[0]['passed']==p[1]['passed'] for p in profiles)
   chance=pa*pb+(1-pa)*(1-pb)
   discrimination=[]
   for j in range(len(ordered[0]['items'])):
    # Exclude the measured item from grouping to avoid part-whole inflation.
    groups=sorted(ordered,key=lambda a:sum(a['items'])-a['items'][j])
    discrimination.append({'position':j+1,'upper_minus_lower_correct_rate':round(statistics.mean(a['items'][j] for a in groups[-n:])-statistics.mean(a['items'][j] for a in groups[:n]),4)})
   categories.append({'specialization':spec,'claimed_grade':grade,'profiles':len(profiles),
    'questions_per_attempt':len(form['questions']),
    'confirmed_grade_agreement':round(agreement,4),
    'cohen_kappa':round((agreement-chance)/(1-chance),4) if chance<1 else None,
    'borderline_profiles':len(borderline),
    'borderline_agreement':round(statistics.mean(p[0]['passed']==p[1]['passed'] for p in borderline),4),
    'score_correlation':round(sum((x-mx)*(y-my) for x,y in zip(first,second))/denom,4) if denom else None,
    'mean_absolute_score_change':round(statistics.mean(abs(x-y) for x,y in zip(first,second)),2),
    'pass_rates':[round(statistics.mean(p[a]['passed'] for p in profiles),4) for a in range(2)],
    'item_discrimination':discrimination})
 return {'method':'150 synthetic profiles per category, two independently generated forms; same assumed proficiency for both attempts. Confirmed grade equals claimed grade on pass, otherwise unconfirmed.',
  'response_model':'P(correct)=0.25+0.74*i/149, identical across items; independent Bernoulli answers. Seed 20261011.',
  'comparison':'Shared profile and attempt seeds; old form uses first six answers from the same draw stream. No threshold changes.',
  'discrimination_method':'Upper 27% minus lower 27% correct rate, grouped by first-attempt score excluding the measured item.',
  'categories':categories,
  'limitations':['Simulated answers are independent of question content; this cannot validate actual item difficulty or expert grade labels.',
   'Candidates near thresholds can change pass status. Borderline subgroup is defined by assumed proficiency within 10 percentage points of the threshold, not by observed scores. Simulation is diagnostic, not proof of stable real-world grades.',
   'Independent item responses overstate the benefit if real questions are correlated. Core scenarios are not expert-calibrated alternate forms or Senior-level evidence on their own.',
   'Repeated assessments are simulated outside the service cooldown; the 90-day category change rule remains enforced.',
   'Real validation needs consented test-retest data, expert labels, corrected item-total correlations and a larger calibrated question bank.']}

def validate():
 with tempfile.TemporaryDirectory() as tmp:
  db=Storage(Path(tmp)/'validation.sqlite');dataset=seed(db);service=Service(db)
  with db.connect() as c:
   emp=dict(c.execute("SELECT id,email,role FROM users WHERE email='employer@example.test'").fetchone());profiles=[dict(r) for r in c.execute('SELECT * FROM profiles')]
  queries=[]
  # Fixture relevance was set from the explicit required technologies, without using score or FSP results.
  for spec,skills in [('backend','Python, PostgreSQL'),('frontend','TypeScript, React'),('data','Python, SQL')]:
   for grade in GRADES:
    need={'specialization':spec,'grade':grade,'skills':skills};out=service.candidates(emp,need)['candidates']
    wanted=set(s.strip().lower() for s in skills.split(','))
    relevant={r['id'] for r in dataset if r['specialization']==spec and r['grade']==grade and wanted <= set(x.strip().lower() for x in r['skills'].split(','))}
    top=[r['id'] for r in out[:3]]
    queries.append({**need,'relevant_ids':sorted(relevant),'top3':top,'precision_at_1':int(top[0] in relevant),'precision_at_3':sum(x in relevant for x in top)/3})
  forms=[]
  for spec in SPECIALIZATIONS:
   for grade in GRADES:
    for i in range(100):
     f=generate(spec,grade,i);forms.append(hashlib.sha256(json.dumps(f,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
  # 1008 synthetic profiles, one in-memory ranking process. This excludes HTTP and concurrent users.
  large=[]
  for repeat in range(28):
   for p in profiles:large.append({**p,'user_id':p['user_id']+repeat*100})
  durations=[]
  for _ in range(100):
   start=time.perf_counter();rank(large,{'specialization':'backend','grade':'Middle','skills':'Python, PostgreSQL'});durations.append((time.perf_counter()-start)*1000)
  result={'dataset':'Synthetic fixture only','candidate_count':len(dataset),'query_count':len(queries),'precision_at_1':statistics.mean(q['precision_at_1'] for q in queries),'precision_at_3':statistics.mean(q['precision_at_3'] for q in queries),'forms_generated':len(forms),'unique_forms':len(set(forms)),'ranking_benchmark':{'profiles':len(large),'runs':100,'p50_ms':round(statistics.median(durations),3),'p95_ms':round(sorted(durations)[94],3),'scope':'In-process only. Not an HTTP load test.'},'queries':queries,'limitations':['No real candidates or expert grade labels.','Seed scores are scenario fixtures, not measured test results.','Form uniqueness does not prove resistance to cheating.','No claim of psychometric reliability, real hiring relevance or legal compliance.']}
  result['assessment_validation']=assessment_validation()
  result['assessment_validation_baseline']=assessment_validation(legacy=True)
  (ROOT/'data/synthetic-candidates.json').write_text(json.dumps(dataset,ensure_ascii=False,indent=2))
  (ROOT/'data/validation-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  print(json.dumps({k:v for k,v in result.items() if k not in ('queries','limitations','assessment_validation','assessment_validation_baseline')},ensure_ascii=False,indent=2))
  print('Test-retest simulation: 9 categories, 1350 profiles, 2700 attempts; details in data/validation-results.json')
if __name__=='__main__':validate()
