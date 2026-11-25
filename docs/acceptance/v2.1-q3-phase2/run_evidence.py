"""Reproduce actual paired metrics / signed HTTP. Requires only optional extras for PG/HTTP."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from tests.retrieval.q3_m2_fixture import EvalFixture
from knowledge_sdk.retrieval.eval import PairwiseRetrievalEvaluator


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--engine',choices=('sqlite','postgres'),required=True);p.add_argument('--http',action='store_true');args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    f=EvalFixture(args.engine)
    try:
        index=f.index_hash()
        report=PairwiseRetrievalEvaluator(f.c,{'reader':f.reader,'foreign':f.foreign},config=f.config).evaluate(f.cases,index_sha256=index).to_dict()
        assert f.index_hash()==index,'Measured index mutated'
        assert report['gate_passed']
        (args.output/('pairwise-eval-'+args.engine+'.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(args.engine,report['pairwise_deltas'],report['gate_passed'])
    finally:f.close()
    if args.http:
        from tests.server.test_q3_m2_http import run_http
        result=run_http(args.engine);assert result['passed']
        (args.output/('http-'+args.engine+'.json')).write_text(json.dumps(result,indent=2)+'\n');print('Real HTTP',args.engine,result['assertion_groups'])

if __name__=='__main__':main()
