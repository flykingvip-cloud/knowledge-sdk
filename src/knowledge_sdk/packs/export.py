"""Deterministic JSON / RO-Crate 1.2 using only the Python standard library."""
from __future__ import annotations
import io
import zipfile
from ..contracts.packs import canonical, plain

def render(pack,format):
    snapshot=canonical(pack)
    if format=='json':return snapshot
    parts=[{'@id':'evidence-pack.json'},{'@id':'REVIEW_SUMMARY.md'}]
    graph=[{'@id':'ro-crate-metadata.json','@type':'CreativeWork','conformsTo':{'@id':'https://w3id.org/ro/crate/1.2'},'about':{'@id':'./'}},
           {'@id':'./','@type':'Dataset','name':pack.title,'description':pack.topic or 'Policy-checked sealed evidence and review snapshot.','license':'No additional rights are granted; source rights and organizational policy apply.','datePublished':pack.created_at,'hasPart':parts},
           {'@id':'evidence-pack.json','@type':['File','DigitalDocument'],'encodingFormat':'application/json'},
           {'@id':'REVIEW_SUMMARY.md','@type':['File','DigitalDocument'],'encodingFormat':'text/markdown'}]
    summary=['# '+pack.title,'','Status: '+pack.status,'','## Dissent']+list(pack.dissent_notes)
    for stance in ('supporting','refuting','negative','conflict','contextual'):
        summary+=['','## '+stance]
        for n,item in enumerate(pack.items):
            if item.stance==stance:summary+=['- '+item.source_uri+' — '+item.condition_note,'  '+item.excerpt.replace('\n','\n  ')]
    for n,item in enumerate(pack.items):
        identity='#item-'+str(n+1);parts.append({'@id':identity})
        graph.append({'@id':identity,'@type':['DigitalDocument','EvidenceItem'],'stance':item.stance,'conditionNote':item.condition_note,'sourceUri':item.source_uri,'sha256':item.excerpt_hash,'dissentNotes':list(pack.dissent_notes),'text':item.excerpt})
    files={'ro-crate-metadata.json':canonical({'@context':'https://w3id.org/ro/crate/1.2/context','@graph':graph}),'evidence-pack.json':snapshot,'REVIEW_SUMMARY.md':'\n'.join(summary).encode()}
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.external_attr=0o644<<16
            archive.writestr(info,data)
    return output.getvalue()
