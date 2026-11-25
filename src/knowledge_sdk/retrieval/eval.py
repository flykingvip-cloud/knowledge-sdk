"""Explicit offline paired evaluation, never a production quality certification."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from contextlib import ExitStack
from unittest.mock import patch
import hashlib
import json
import math
import time
from .calibration import validate_threshold
from .rerank import identifier, finite
from ..contracts.policy import Purpose
from ..contracts.models import encode
from ..exceptions import ValidationError, PermissionDeniedError, NotFoundError


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class RetrievalEvalCase:
    case_id: str
    doc_family: str
    query: str
    mode: str
    actor_id: str
    purpose: str
    relevant_doc_ids: tuple
    forbidden_doc_ids: tuple = ()
    expect_refusal: bool = False
    top_k: int = 5
    split: str = 'evaluation'

    def __post_init__(self):
        for v in (self.case_id,self.doc_family,self.actor_id):identifier(v)
        if not isinstance(self.query,str) or not 0<len(self.query)<=10000:raise ValidationError('Invalid eval query')
        if self.mode not in ('keyword','vector','hybrid') or self.split not in ('train','calibration','evaluation'):raise ValidationError('Invalid eval mode/split')
        try:object.__setattr__(self,'purpose',Purpose(self.purpose).value)
        except (ValueError,TypeError):raise ValidationError('Invalid eval purpose') from None
        if type(self.expect_refusal) is not bool or type(self.top_k) is not int or not 1<=self.top_k<=100:raise ValidationError('Invalid eval flags')
        rel=self.relevant_doc_ids
        if isinstance(rel,dict):rel=tuple(sorted(rel.items()))
        elif isinstance(rel,(list,tuple)):
            rel=tuple((x,1) if isinstance(x,str) else tuple(x) if isinstance(x,(tuple,list)) else () for x in rel)
        else:raise ValidationError('Invalid relevance judgments')
        for pair in rel:
            if len(pair)!=2:raise ValidationError('Invalid relevance judgments')
            identifier(pair[0])
            if type(pair[1]) is not int or not 1<=pair[1]<=3:raise ValidationError('Invalid relevance grade')
        if len({x[0] for x in rel})!=len(rel):raise ValidationError('Duplicate relevance judgments')
        if not isinstance(self.forbidden_doc_ids,(list,tuple)):raise ValidationError('Invalid forbidden identifiers')
        forbidden=tuple(self.forbidden_doc_ids)
        for v in forbidden:identifier(v)
        if set(forbidden)&{p[0] for p in rel} or self.expect_refusal and rel:raise ValidationError('Conflicting judgments')
        if not rel and not self.expect_refusal:raise ValidationError('Missing positive relevance judgments')
        object.__setattr__(self,'relevant_doc_ids',tuple(rel));object.__setattr__(self,'forbidden_doc_ids',forbidden)

    def to_dict(self):
        result=asdict(self);result['relevant_doc_ids']=dict(self.relevant_doc_ids);return result
    @classmethod
    def from_dict(cls,data):
        try:return cls(**data)
        except (TypeError,ValueError):raise ValidationError('Invalid eval case') from None


@dataclass(frozen=True)
class PairwiseEvalConfig:
    reranker_id: str = 'lexical-v1'
    calibrator_id: str = 'default-v1'
    min_calibrated_score: float = .60
    rerank_top_k: int = 40
    split: str = 'evaluation'
    def __post_init__(self):
        identifier(self.reranker_id);identifier(self.calibrator_id)
        validate_threshold(self.min_calibrated_score)
        if self.min_calibrated_score is None or type(self.rerank_top_k) is not int or not 1<=self.rerank_top_k<=500 or self.split not in ('train','calibration','evaluation'):
            raise ValidationError('Invalid eval configuration')
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):
        try:return cls(**data)
        except (TypeError,ValueError):raise ValidationError('Invalid eval config') from None


@dataclass(frozen=True)
class PairwiseEvalReport:
    """Canonical JSON seals a deep immutable checked report; to_dict returns a copy."""
    report_json: str
    def __post_init__(self):
        try:self._validate()
        except (TypeError,KeyError,AttributeError,ValueError,OverflowError):raise ValidationError('Invalid eval report') from None
    def _validate(self):
        try:r=json.loads(self.report_json,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError,TypeError):raise ValidationError('Invalid eval report') from None
        required={'baseline','candidate','pairwise_deltas','family_breakdown','case_results','gate_passed','configuration','dataset_sha256','corpus_sha256','index_sha256','snapshot_consistent','instrumentation','split_counts','scope'}
        if not isinstance(r,dict) or set(r)!=required or type(r['gate_passed']) is not bool or type(r['snapshot_consistent']) is not bool:raise ValidationError('Invalid eval report fields')
        for key in ('dataset_sha256','corpus_sha256','index_sha256'):
            if not isinstance(r[key],str) or len(r[key])!=64 or any(c not in '0123456789abcdef' for c in r[key]):raise ValidationError('Invalid eval fingerprints')
        for arm in ('baseline','candidate'):
            m=r[arm]
            for k in ('recall_at_k','ndcg_at_k','mrr','citation_precision','refusal_accuracy','false_refusal_rate','acl_violation_rate'):
                if not 0<=finite(m.get(k),'metric')<=1:raise ValidationError('Invalid bounded metric')
            for k in ('acl_violations','forbidden_hits','implicit_model_calls','returned_hits','positive_cases','case_count','valid_authorized_citations'):
                if type(m.get(k)) is not int or m[k]<0:raise ValidationError('Invalid metric count')
            for k in ('p50_latency_ms','p95_latency_ms'):
                if finite(m.get(k),'latency')<0:raise ValidationError('Invalid metric latency')
            if m['positive_cases']>m['case_count'] or m['valid_authorized_citations']>m['returned_hits'] or m['forbidden_hits']>m['acl_violations']:raise ValidationError('Inconsistent metric denominators')
        if not isinstance(r['case_results'],list) or not isinstance(r['family_breakdown'],dict):raise ValidationError('Invalid report breakdown')
        if r['baseline']['case_count']!=len(r['case_results']) or r['candidate']['case_count']!=len(r['case_results']):raise ValidationError('Inconsistent report case count')
        for key in ('ndcg_delta','mrr_delta'):finite(r['pairwise_deltas'].get(key),'delta')
        for key in ('wins','ties','losses'):
            if type(r['pairwise_deltas'].get(key)) is not int or r['pairwise_deltas'][key]<0:raise ValidationError('Invalid pair count')
        if sum(r['pairwise_deltas'][k] for k in ('wins','ties','losses'))!=len(r['case_results']):raise ValidationError('Inconsistent pair count')
        if r['gate_passed']!=_gate(r['baseline'],r['candidate'],r['pairwise_deltas'],r['snapshot_consistent']):raise ValidationError('Inconsistent eval gate')
        object.__setattr__(self,'report_json',canonical(r))
    def to_dict(self):return json.loads(self.report_json)
    @classmethod
    def from_dict(cls,data):
        try:return cls(canonical(data))
        except (TypeError,ValueError):raise ValidationError('Invalid eval report') from None


class OfflineBoundaryMonitor:
    """Explicit process-local offline guard. Counts SDK provider/network attempts.

    Do not use concurrently with unrelated network work in the same process.
    PostgreSQL's native local connection is not a model/provider call.
    """
    def __init__(self):self.implicit_model_calls=0;self.boundaries=[];self.stack=ExitStack()
    def _blocked(self,*args,**kwargs):
        self.implicit_model_calls+=1
        raise ValidationError('Offline evaluation forbids model/network calls')
    def __enter__(self):
        for target in ('urllib.request.urlopen','socket.create_connection',
                       'knowledge_sdk.retrieval.adapters.qdrant.QdrantIndex._request',
                       'knowledge_sdk.retrieval.adapters.openai_embedder.OpenAICompatibleEmbedder.embed'):
            try:self.stack.enter_context(patch(target,self._blocked));self.boundaries.append(target)
            except BaseException:self.stack.close();raise
        return self
    def __exit__(self,*args):return self.stack.__exit__(*args)


def _gate(base,candidate,deltas,consistent):
    return bool(consistent and base['acl_violations']==candidate['acl_violations']==0 and
                base['implicit_model_calls']==candidate['implicit_model_calls']==0 and
                candidate['refusal_accuracy']>=base['refusal_accuracy'] and
                candidate['false_refusal_rate']<=base['false_refusal_rate'] and deltas['ndcg_delta']>0)


def _percentile(values,p):
    if not values:return 0.0
    values=sorted(values);x=(len(values)-1)*p;i=int(x);j=min(i+1,len(values)-1)
    return values[i]+(values[j]-values[i])*(x-i)


def _aggregate(rows):
    positive=[r for r in rows if r['positive']]
    count=len(rows);returned=sum(r['returned_hits'] for r in rows)
    def avg(key,source):return sum(r[key] for r in source)/len(source) if source else 0.0
    invalid=sum(r['acl_violations'] for r in rows)
    return dict(case_count=count,positive_cases=len(positive),recall_at_k=avg('recall',positive),ndcg_at_k=avg('ndcg',positive),mrr=avg('mrr',positive),
                citation_precision=sum(r['precise_citations'] for r in rows)/returned if returned else 0.0,
                valid_authorized_citations=sum(r['valid_citations'] for r in rows),returned_hits=returned,
                refusal_accuracy=avg('refusal_correct',rows),false_refusal_rate=avg('false_refusal',positive),
                p50_latency_ms=_percentile([r['latency_ms'] for r in rows],.5),p95_latency_ms=_percentile([r['latency_ms'] for r in rows],.95),
                acl_violations=invalid,acl_violation_rate=invalid/returned if returned else 0.0,
                forbidden_hits=sum(r['forbidden_hits'] for r in rows),implicit_model_calls=sum(r['implicit_model_calls'] for r in rows))


class PairwiseRetrievalEvaluator:
    def __init__(self,client,actors,*,config=None):
        self.client=client;self.actors=dict(actors);self.config=config if config is not None else PairwiseEvalConfig()
        if not isinstance(self.config,PairwiseEvalConfig):raise ValidationError('Invalid evaluator config')

    def _corpus(self):
        result=[]
        for org in sorted({a.org_id for a in self.actors.values()}):
            result.extend(encode(k) for k in self.client.store.list_kbs(org))
            for d in self.client.store.list_documents(org):
                result.append(encode(d));result.append(encode(self.client.store.get_acl(d.doc_id)))
                result.append(encode(self.client.store.get_version(d.doc_id,d.current_version)))
                result.extend(encode(c) for c in self.client.store.get_chunks(d.doc_id,d.current_version))
        return digest(result)

    def evaluate(self,cases,*,index_sha256):
        if not isinstance(index_sha256,str) or len(index_sha256)!=64 or any(c not in '0123456789abcdef' for c in index_sha256):raise ValidationError('Invalid index fingerprint')
        cases=tuple(cases)
        if not cases or any(not isinstance(c,RetrievalEvalCase) for c in cases):raise ValidationError('Checked eval cases required')
        if len({c.case_id for c in cases})!=len(cases):raise ValidationError('Duplicate eval case')
        splits={}
        for c in cases:
            if c.doc_family in splits and splits[c.doc_family]!=c.split:raise ValidationError('Document family split leakage')
            splits[c.doc_family]=c.split
        chosen=[c for c in cases if c.split==self.config.split]
        if not chosen:raise ValidationError('Empty measured split')
        if any(c.actor_id not in self.actors for c in chosen):raise ValidationError('Missing trusted eval actor')
        # Neither labels nor family identity are ever passed to search/strategies.
        config=self.config.to_dict();strategy=dict(config);strategy.pop('split')
        records=[];arms={'baseline':[],'candidate':[]}
        with self.client._lock,self.client.store.runtime_transaction(),OfflineBoundaryMonitor() as monitor:
            before=self._corpus()
            for case in chosen:
                pair={};actor=self.actors[case.actor_id];grades=dict(case.relevant_doc_ids)
                for arm in ('baseline','candidate'):
                    start_calls=monitor.implicit_model_calls;start=time.perf_counter()
                    response=self.client.search(actor,case.query,case.mode,case.top_k,purpose=Purpose(case.purpose),**(strategy if arm=='candidate' else {}))
                    latency=(time.perf_counter()-start)*1000
                    ids=[];invalid=0;forbidden=0;valid=0;precise=0
                    for hit in response.hits:
                        if hit.doc_id not in ids:ids.append(hit.doc_id)
                        forbidden+=hit.doc_id in case.forbidden_doc_ids
                        allowed=False;citation=False
                        try:
                            d=self.client.store.get_document(hit.doc_id)
                            allowed=(d.org_id==actor.org_id and d.current_version==hit.version and not d.archived and
                                     self.client.evaluate_policy(actor,hit.doc_id,purpose=Purpose(case.purpose)).allowed)
                            ref=self.client.reference(actor,hit.doc_id,hit.version,[hit.chunk_id],hit.excerpt,purpose=Purpose(case.purpose))
                            receipt=self.client.consume(actor,ref,purpose=Purpose(case.purpose))
                            citation=allowed and receipt.status in ('consumed','partial') and ref.excerpt_hash==hit.excerpt_hash
                        except (PermissionDeniedError,NotFoundError):pass
                        invalid+=not allowed or hit.doc_id in case.forbidden_doc_ids
                        valid+=citation;precise+=citation and hit.doc_id in grades
                    gains=[grades.get(i,0) for i in ids[:case.top_k]]
                    ideal=sorted(grades.values(),reverse=True)[:case.top_k]
                    dcg=lambda v:sum((2**g-1)/math.log2(i+2) for i,g in enumerate(v))
                    row=dict(positive=bool(grades),returned_hits=len(response.hits),recall=len(set(ids)&set(grades))/len(grades) if grades else 0.0,
                             ndcg=dcg(gains)/dcg(ideal) if ideal else 0.0,mrr=next((1/(i+1) for i,d in enumerate(ids) if d in grades),0.0),
                             refusal_correct=float((not response.hits)==case.expect_refusal),false_refusal=float(bool(grades) and not response.hits),
                             valid_citations=valid,precise_citations=precise,acl_violations=invalid,forbidden_hits=forbidden,latency_ms=latency,
                             implicit_model_calls=monitor.implicit_model_calls-start_calls,doc_ids=ids)
                    arms[arm].append(row);pair[arm]=row
                records.append(dict(case_id=case.case_id,doc_family=case.doc_family,**pair))
            consistent=before==self._corpus()
            instrumentation={'boundaries':monitor.boundaries,'observed_provider_network_attempts':monitor.implicit_model_calls,'fixture_embeddings':'Explicit deterministic offline embeddings, not an online model; not counted as implicit provider calls'}
        base=_aggregate(arms['baseline']);cand=_aggregate(arms['candidate'])
        diffs=[r['candidate']['ndcg']-r['baseline']['ndcg'] for r in records]
        delta=dict(ndcg_delta=cand['ndcg_at_k']-base['ndcg_at_k'],mrr_delta=cand['mrr']-base['mrr'],wins=sum(x>1e-12 for x in diffs),ties=sum(abs(x)<=1e-12 for x in diffs),losses=sum(x< -1e-12 for x in diffs))
        families={}
        for family in sorted({r['doc_family'] for r in records}):
            rs=[r for r in records if r['doc_family']==family]
            families[family]={arm:_aggregate([r[arm] for r in rs]) for arm in arms}
        payload=dict(baseline=base,candidate=cand,pairwise_deltas=delta,family_breakdown=families,case_results=records,
                     gate_passed=_gate(base,cand,delta,consistent),configuration={'baseline':{},'candidate':config},dataset_sha256=digest([c.to_dict() for c in cases]),
                     corpus_sha256=before,index_sha256=index_sha256,snapshot_consistent=consistent,instrumentation=instrumentation,
                     split_counts={s:sum(c.split==s for c in cases) for s in ('train','calibration','evaluation')},
                     scope='Fixed offline split only; positive metrics exclude refusal-only cases; citation precision=relevant valid authorized citations/all returned hits; refusal accuracy=correct refusal/nonrefusal over all cases; zero denominators map to 0.0; no production or online model quality claim')
        return PairwiseEvalReport.from_dict(payload)
