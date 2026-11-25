import unittest,json,copy,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]/'docs/architecture/knowledge-sdk-alignment'
spec=importlib.util.spec_from_file_location('m1_pending',ROOT/'validate_m1_manifest.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class PendingManifest(unittest.TestCase):
    def test_pending_wellformed_is_not_authorized(self):
        result=module.check(json.loads((ROOT/'m1-freeze-manifest.json').read_text()));self.assertEqual(result['status'],'WELL_FORMED_PENDING');self.assertIs(result['freeze_authorized'],False)
    def test_missing_partial_forged_refs_falseapproval_all_fail(self):
        base=json.loads((ROOT/'m1-freeze-manifest.json').read_text());bad=[]
        d=copy.deepcopy(base);d['decisions'].pop();bad.append(d)
        for status in ('frozen','approved','partially_signed',True):
            d=copy.deepcopy(base);d['status']=status;bad.append(d)
        d=copy.deepcopy(base);d['approvals']=[{'role':'owner','signed_by':'execution-agent'}];bad.append(d)
        d=copy.deepcopy(base);d['decisions'][0]['approvals']=[{'approved':True}];bad.append(d)
        d=copy.deepcopy(base);d['refs']['main']='0'*40;bad.append(d)
        d=copy.deepcopy(base);d['decisions'][2]['selected_option']='A';bad.append(d)
        d=copy.deepcopy(base);d['required_signoff_roles']=['owner'];bad.append(d)
        d=copy.deepcopy(base);d['freeze_authorized']=True;bad.append(d)
        d=copy.deepcopy(base);del d['decisions'][0]['options'][0]['risks'];bad.append(d)
        for data in bad:
            with self.subTest(data_status=data['status']):
                with self.assertRaises((ValueError,KeyError,TypeError)):module.check(data)
