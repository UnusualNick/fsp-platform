"""Small authenticated HTTP read benchmark against an explicitly supplied local demo."""
import argparse,concurrent.futures,http.cookiejar,json,math,time,urllib.request,urllib.parse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:8080');parser.add_argument('--output',default='data/http-load.json');args=parser.parse_args()
if urllib.parse.urlsplit(args.base).hostname not in ('localhost','127.0.0.1'):parser.error('Only a local demonstration is supported')
jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
req=urllib.request.Request(args.base+'/api/auth/login',data=json.dumps({'email':'employer@example.test','password':'DemoPassword42!'}).encode(),headers={'Content-Type':'application/json'})
with client.open(req,timeout=10) as response:json.loads(response.read())
cookie='; '.join(c.name+'='+c.value for c in jar)
paths=['/api/candidates?specialization=backend&grade=Middle&skills=Python%2CPostgres','/api/candidates?specialization=frontend&grade=Middle&skills=JS%2CReact','/api/vacancies','/api/invitations']
def read(i):
 start=time.perf_counter()
 try:
  with urllib.request.urlopen(urllib.request.Request(args.base+paths[i%len(paths)],headers={'Cookie':cookie}),timeout=10) as r:
   data=json.loads(r.read());ok=r.status==200 and 'error' not in data
 except Exception:ok=False
 return (time.perf_counter()-start)*1000,ok
start=time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(read,range(100)))
values=sorted(r[0] for r in results)
report={'requests':100,'concurrency':8,'errors':sum(not r[1] for r in results),'elapsed_seconds':round(time.perf_counter()-start,3),'p50_ms':round(values[49],2),'p95_ms':round(values[94],2),'p99_ms':round(values[98],2),'scope':'Local read-only HTTP smoke benchmark; 36 synthetic profiles, shared employer session. Does not validate writes, large datasets, real users or production throughput.'}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
if report['errors']:raise SystemExit(1)
