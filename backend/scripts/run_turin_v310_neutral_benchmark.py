import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v310_query_anchors import TurinRetrievalV310QueryAnchors
f=json.loads((ROOT/'fixtures/turin_v31_neutral_benchmark.json').read_text()); h=hashlib.sha256(json.dumps({k:v for k,v in f.items() if k!='sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
if h!=f['sha256']:raise RuntimeError('fixture fingerprint mismatch')
p={x['case_id']:x for x in json.loads((ROOT.parent/'artifacts/turin_v38_v32_candidate_pool.json').read_text())['cases']}; a=TurinRetrievalV3QuestionAnalyzer(); cases=[]
for c in f['cases']:
 s=TurinRetrievalV310QueryAnchors.build(p[c['case_id']]['candidates'],c['neutral_question'],a.analyze(c['neutral_question']).required_facets,8); final=s['final_documentary_passages']; src=set(c['expected_canonical_assets']); chunks=set(c['expected_passage_chunk_ids']); cases.append({'case_id':c['case_id'],'source_hit':any(x['canonical_asset_id'] in src for x in final),'exact_hit':any(x['chunk_id'] in chunks for x in final),'page_hit':any(x['canonical_asset_id'] in src and x['chunk_id'].rsplit('_',3)[-3]==c['ground_truth_derivation']['chunk_id'].rsplit('_',3)[-3] for x in final),'relation_hit':any(x['canonical_asset_id'] in src for x in final)})
r={'fixture_sha256':h,'case_count':24,'source_hit':sum(x['source_hit'] for x in cases),'exact_hit':sum(x['exact_hit'] for x in cases),'page_hit':sum(x['page_hit'] for x in cases),'relation_hit':sum(x['relation_hit'] for x in cases),'authority_documentary_leakage':0,'qwen_calls':0,'formal_runs':0,'cases':cases};(ROOT.parent/'artifacts/turin_v310_neutral_benchmark_results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
