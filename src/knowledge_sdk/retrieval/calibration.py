"""Serializable, independent, monotone score channels; no callback or network."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
from .rerank import finite, identifier
from ..exceptions import ValidationError

CHANNELS=('keyword','vector','hybrid','rerank')


@dataclass(frozen=True)
class CalibrationChannelConfig:
    channel: str
    method: str = 'minmax'
    min_raw: float = 0.0
    max_raw: float = 1.0
    midpoint: float = .5
    steepness: float = 1.0
    anchors: tuple = ()

    def __post_init__(self):
        if self.channel not in CHANNELS or self.method not in ('minmax','sigmoid','piecewise_quantile'):
            raise ValidationError('Invalid calibration channel/method')
        for name in ('min_raw','max_raw','midpoint','steepness'):
            object.__setattr__(self,name,finite(getattr(self,name),'calibration parameter'))
        if self.max_raw<=self.min_raw or self.steepness<=0:raise ValidationError('Invalid calibration range')
        if not isinstance(self.anchors,(list,tuple)):raise ValidationError('Invalid calibration anchors')
        pairs=[]
        for pair in self.anchors:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2:raise ValidationError('Invalid calibration anchors')
            x,y=(finite(v,'anchor') for v in pair)
            if not 0<=y<=1 or pairs and (x<=pairs[-1][0] or y<pairs[-1][1]):raise ValidationError('Nonmonotone calibration anchors')
            pairs.append((x,y))
        if self.method=='piecewise_quantile' and len(pairs)<2:raise ValidationError('Need two calibration anchors')
        object.__setattr__(self,'anchors',tuple(pairs))

    def map(self,raw):
        raw=finite(raw)
        if self.method=='minmax':
            if raw<=self.min_raw:return 0.0
            if raw>=self.max_raw:return 1.0
            width=self.max_raw-self.min_raw
            value=((raw/2-self.min_raw/2)/(self.max_raw/2-self.min_raw/2)) if math.isinf(width) else (raw-self.min_raw)/width
        elif self.method=='sigmoid':
            x=self.steepness*(raw-self.midpoint)
            value=1/(1+math.exp(-x)) if x>=0 else math.exp(x)/(1+math.exp(x))
        else:
            if raw<=self.anchors[0][0]:return self.anchors[0][1]
            if raw>=self.anchors[-1][0]:return self.anchors[-1][1]
            for (x,a),(y,b) in zip(self.anchors,self.anchors[1:]):
                if x<=raw<=y:
                    width=y-x
                    ratio=(raw/2-x/2)/(y/2-x/2) if math.isinf(width) else (raw-x)/width
                    value=a+(b-a)*ratio;break
        return float(min(1.0,max(0.0,value)))

    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,data):
        try:return cls(**data)
        except (TypeError,ValueError) as exc:raise ValidationError('Invalid calibration fields') from exc


@dataclass(frozen=True)
class ScoreCalibrationConfig:
    channels: tuple = ()
    calibrator_id: str = 'default-v1'

    def __post_init__(self):
        identifier(self.calibrator_id)
        if not isinstance(self.channels,(tuple,list)):raise ValidationError('Invalid channel configs')
        channels=tuple(CalibrationChannelConfig.from_dict(v) if isinstance(v,dict) else v for v in self.channels)
        if not channels:
            channels=tuple(CalibrationChannelConfig(c,max_raw=1.0 if c=='rerank' else 1/61) for c in CHANNELS)
        if any(not isinstance(c,CalibrationChannelConfig) for c in channels) or sorted(c.channel for c in channels)!=sorted(CHANNELS):
            raise ValidationError('Each channel needs exactly one independent config')
        object.__setattr__(self,'channels',channels)

    def to_dict(self):return {'calibrator_id':self.calibrator_id,'channels':[c.to_dict() for c in self.channels]}
    @classmethod
    def from_dict(cls,data):
        try:return cls(**data)
        except (TypeError,ValueError) as exc:raise ValidationError('Invalid calibration configuration') from exc


@dataclass(frozen=True)
class ScoreCalibrator:
    config: ScoreCalibrationConfig = ScoreCalibrationConfig()
    def __post_init__(self):
        if not isinstance(self.config,ScoreCalibrationConfig):raise ValidationError('Invalid calibrator config')
    @property
    def calibrator_id(self):return self.config.calibrator_id
    def calibrate(self,channel,raw):
        if channel not in CHANNELS:raise ValidationError('Unknown calibration channel')
        return next(c for c in self.config.channels if c.channel==channel).map(raw)
    def to_dict(self):return self.config.to_dict()
    @classmethod
    def from_dict(cls,data):return cls(ScoreCalibrationConfig.from_dict(data))


def validate_threshold(value):
    if value is not None and not 0<=finite(value,'threshold')<=1:raise ValidationError('Invalid threshold')
    return value
