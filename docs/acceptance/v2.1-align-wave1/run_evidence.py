"""Reproducible live-wire evidence without UI, remote providers or existing services."""
from __future__ import annotations
import argparse,json,importlib.util
from pathlib import Path
from unittest.mock import patch


def run(engine):
    from tests.alignment.test_wave1_wire import run_wave1_wire
    from tests.server.test_q3_m2_http import run_http
    root=Path(__file__).resolve().parents[3];path=root/'docs/acceptance/v2.1-q3-phase1/live_runtime_probe.py'
    spec=importlib.util.spec_from_file_location('wave_m1_probe',path);probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    attempts=[]
    def blocked(*args,**kwargs):attempts.append('provider_boundary');raise AssertionError('Provider calls forbidden in isolated wire acceptance')
    with patch('knowledge_sdk.retrieval.adapters.openai_embedder.OpenAICompatibleEmbedder.embed',blocked),patch('knowledge_sdk.retrieval.adapters.qdrant.QdrantIndex._request',blocked):
        wave=run_wave1_wire(engine);m2=run_http(engine);m1=probe.run(engine)
    assert not attempts
    return dict(wave1=wave,q3_m2_nine_runtime_variants=m2,q3_m1_hmac_oidc_six_families=m1,provider_instrumentation={'boundaries':['OpenAICompatibleEmbedder.embed','QdrantIndex._request'],'observed_attempts':len(attempts),'note':'Loopback HMAC/OIDC HTTP is actual wire traffic, not blocked or counted as model/provider use; deterministic fixture embeddings are explicit offline stand-ins.'},ui='NO_UI_CHANGES; no browser run claimed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=('sqlite','postgres'),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=run(a.engine);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'engine':a.engine,'wave1_wire_groups':result['wave1']['wire_assertion_groups'],'provider_attempts':result['provider_instrumentation']['observed_attempts']}))
