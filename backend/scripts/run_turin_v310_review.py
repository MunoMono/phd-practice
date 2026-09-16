import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.core.database import LocalSessionLocal
from app.services.turin_question_register import TURIN_QUESTION_REGISTER
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service,CORPUS_VERSION
from app.services.turin_retrieval_v310_query_anchors import TurinRetrievalV310QueryAnchors
IDS=(("Q01","KR1"),("Q02","KR2"),("Q03","KR3"),("Q04","KR4"),("Q05","CI1"),("Q06","CI2"),("Q07","CI3"),("Q08","CI4"),("Q09","SM1"),("Q10","SM2"),("Q11","SM3"),("Q12","SM4"))
db=LocalSessionLocal(); service=TurinRetrievalV3Service(use_authority_graph=True,passage_version="v3.2"); out=[]
try:
 for display,qid in IDS:
  _,q=TURIN_QUESTION_REGISTER[qid]; r=service.retrieve(db,q,5,CORPUS_VERSION); s=TurinRetrievalV310QueryAnchors.build(service.last_passage_candidates,q,r['question_analysis']['required_facets']); data={'version':'v3.10-read-only','question_id':display,'question':q,'qwen_calls':0,'formal_runs':0,'query_anchors':s['query_anchors'],'source_profiles':[{k:v for k,v in p.items() if k!='top_passages'} for p in s['source_profiles']],'evidence_bundles':s['evidence_bundles'],'retrieval_adequacy':s['retrieval_adequacy']}; (ROOT/'artifacts'/f'turin_v310_review_{display.lower()}.json').write_text(json.dumps(data,indent=2)+'\n'); out.append(data)
finally: db.close()
(ROOT/'artifacts'/'turin_v310_review_all_12.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'reviews':len(out),'qwen_calls':0,'formal_runs':0}))
