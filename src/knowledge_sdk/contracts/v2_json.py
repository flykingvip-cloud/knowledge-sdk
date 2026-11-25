"""Small stdlib validator for the exact frozen schema vocabulary used by v2."""
from __future__ import annotations
import json
import math
import re
from .v2_schemas import SCHEMAS
from .idempotency import request_fingerprint
from ..exceptions import ValidationError


def loads(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError()
            result[key]=value
        return result
    def invalid(value):raise ValueError()
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
        request_fingerprint(value)
        return value
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise ValidationError('VALIDATION_ERROR') from None


def validate(name,value):
    try:_validate(SCHEMAS[name],value)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        raise ValidationError('VALIDATION_ERROR') from None
    return value


def _validate(schema,value):
    if '$ref' in schema:
        return _validate(SCHEMAS[schema['$ref'].rsplit('/',1)[1]],value)
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:_validate(option,value);return
            except (ValueError,TypeError):pass
        raise ValueError()
    kind=schema.get('type')
    valid={'null':value is None,'boolean':type(value) is bool,'integer':type(value) is int,
           'number':type(value) in (int,float) and (type(value) is int or math.isfinite(value)),
           'string':type(value) is str,'object':type(value) is dict,'array':type(value) is list}
    if kind and not valid.get(kind,False):raise ValueError()
    if 'const' in schema and (type(value) is not type(schema['const']) or value!=schema['const']):raise ValueError()
    if 'enum' in schema and value not in schema['enum']:raise ValueError()
    if type(value) in (int,float):
        if value<schema.get('minimum',float('-inf')) or value>schema.get('maximum',float('inf')):raise ValueError()
    if type(value) is str:
        value.encode('utf-8')
        if not schema.get('minLength',0)<=len(value)<=schema.get('maxLength',2**31):raise ValueError()
        if 'pattern' in schema and not re.search(schema['pattern'],value):raise ValueError()
        # OpenAPI 3.1 format is annotation-only by default, as in the frozen validator.
    if type(value) is list:
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',2**31):raise ValueError()
        for item in value:_validate(schema.get('items',{}),item)
    if type(value) is dict:
        if any(type(k) is not str for k in value) or not set(schema.get('required',())).issubset(value):raise ValueError()
        properties=schema.get('properties',{})
        for key,item in value.items():
            if key in properties:_validate(properties[key],item)
            else:
                extra=schema.get('additionalProperties',True)
                if extra is False:raise ValueError()
                if type(extra) is dict:_validate(extra,item)
