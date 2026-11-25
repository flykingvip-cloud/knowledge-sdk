"""Known named strategies only on transport; object injection is local/trusted."""
from __future__ import annotations
from types import MappingProxyType
from .rerank import DeterministicLexicalReranker, identifier
from .calibration import ScoreCalibrator, validate_threshold
from ..exceptions import ValidationError


def registries(rerankers=None,calibrators=None):
    r={'lexical-v1':DeterministicLexicalReranker()};c={'default-v1':ScoreCalibrator()}
    for supplied,target,kind in ((rerankers,r,'reranker'),(calibrators,c,'calibrator')):
        if supplied is not None:
            if not hasattr(supplied,'items'):raise ValidationError('Invalid strategy registry')
            for key,value in supplied.items():
                identifier(key)
                if kind=='reranker':
                    if not callable(getattr(value,'score',None)) or getattr(value,'reranker_id',None)!=key:raise ValidationError('Invalid reranker registry')
                elif not isinstance(value,ScoreCalibrator) or value.calibrator_id!=key:raise ValidationError('Invalid calibrator registry')
                target[key]=value
    return MappingProxyType(r),MappingProxyType(c)


def resolve(rerank=False,reranker_id=None,calibrator_id=None,min_calibrated_score=None,rerank_top_k=None,reranker=None,calibrator=None,reranker_registry=None,calibrator_registry=None):
    if type(rerank) is not bool:raise ValidationError('Invalid rerank flag')
    validate_threshold(min_calibrated_score)
    if rerank_top_k is not None and (type(rerank_top_k) is not int or not 1<=rerank_top_k<=500):raise ValidationError('Invalid rerank window')
    rr,cc=registries(reranker_registry,calibrator_registry)
    if reranker_id is not None:
        identifier(reranker_id)
        if reranker_id not in rr:raise ValidationError('Unknown reranker_id')
        if reranker is not None:raise ValidationError('Choose named or injected reranker')
        reranker=rr[reranker_id]
    if reranker is not None and (not callable(getattr(reranker,'score',None)) or not isinstance(getattr(reranker,'reranker_id',None),str)):
        raise ValidationError('Invalid injected reranker')
    if reranker is not None:identifier(reranker.reranker_id)
    if rerank and reranker is None:reranker=rr['lexical-v1']
    if calibrator_id is not None:
        identifier(calibrator_id)
        if calibrator_id not in cc:raise ValidationError('Unknown calibrator_id')
        if calibrator is not None:raise ValidationError('Choose named or injected calibrator')
        calibrator=cc[calibrator_id]
    if calibrator is not None and not isinstance(calibrator,ScoreCalibrator):raise ValidationError('Invalid calibrator')
    if min_calibrated_score is not None and calibrator is None:calibrator=cc['default-v1']
    return reranker,calibrator
