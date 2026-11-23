from __future__ import annotations
import io
import json
import traceback
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from knowledge_sdk import OpenAICompatibleEmbedder, EmbeddingError, ValidationError
from knowledge_sdk.retrieval.adapters import OpenAICompatibleEmbedder as Exported


def response(vectors):
    return io.BytesIO(json.dumps({"data":[{"index":i,"embedding":v}
                                       for i,v in reversed(list(enumerate(vectors)))]}).encode())


class EmbedderTests(unittest.TestCase):
    def client(self, **kwargs):
        return OpenAICompatibleEmbedder("http://embedding.example.test/v1", "semantic", **kwargs)

    def test_exports_semantic_and_empty(self):
        e=self.client()
        self.assertIs(Exported,OpenAICompatibleEmbedder)
        self.assertFalse(e.non_semantic)
        with patch.object(e._opener,"open") as call:
            self.assertEqual(e.embed([]),[])
            call.assert_not_called()

    def test_batch_order_dimensions_and_headers(self):
        e=self.client(api_key="fake-secret-for-test", dimensions=2, batch_size=2,
                      extra_headers={"X-Deployment":"test"}, timeout=12)
        with patch.object(e._opener,"open",side_effect=[response([[1,2],[3,4]]),response([[5,6]])]) as call:
            self.assertEqual(e.embed(["one","two","three"]),[[1.,2.],[3.,4.],[5.,6.]])
            first=call.call_args_list[0][0][0]
            self.assertEqual(first.full_url,"http://embedding.example.test/v1/embeddings")
            self.assertEqual(first.get_header("Authorization"),"Bearer fake-secret-for-test")
            self.assertEqual(first.get_header("X-deployment"),"test")
            self.assertEqual(json.loads(first.data),{"model":"semantic","input":["one","two"],"encoding_format":"float","dimensions":2})
            self.assertEqual(call.call_args_list[0][1]["timeout"],12)

    def test_endpoint_and_no_credential(self):
        e=OpenAICompatibleEmbedder("http://localhost/v1/embeddings/","m")
        with patch.object(e._opener,"open",return_value=response([[1,2]])) as call:
            e.embed(["text"])
            req=call.call_args[0][0]
            self.assertEqual(req.full_url,"http://localhost/v1/embeddings")
            self.assertIsNone(req.get_header("Authorization"))
            self.assertNotIn("dimensions",json.loads(req.data))

    def test_dimension_consistency_across_batches_and_calls(self):
        e=self.client(batch_size=1)
        with patch.object(e._opener,"open",side_effect=[response([[1,2]]),response([[1]])]):
            with self.assertRaises(EmbeddingError): e.embed(["a","b"])
        with patch.object(e._opener,"open",return_value=response([[1,2]])): e.embed(["a"])
        with patch.object(e._opener,"open",return_value=response([[1]])):
            with self.assertRaises(EmbeddingError): e.embed(["a"])

    def test_invalid_vectors_and_indices(self):
        bad=[[],[[1]],[[True,1]],[[float("nan"),1]],[[float("inf"),1]],[["1",2]],[[1,2],[3,4]]]
        for vectors in bad:
            e=self.client(dimensions=2)
            with patch.object(e._opener,"open",return_value=response(vectors)):
                with self.assertRaises(EmbeddingError): e.embed(["a"])
        for rows in ([{"index":1,"embedding":[1]}],
                     [{"index":0,"embedding":[1]},{"index":0,"embedding":[1]}],
                     [{"index":True,"embedding":[1]}]):
            e=self.client()
            with patch.object(e._opener,"open",return_value=io.BytesIO(json.dumps({"data":rows}).encode())):
                with self.assertRaises(EmbeddingError): e.embed(["a"]*len(rows))

    def test_errors_do_not_echo_credentials_or_provider_body(self):
        secret="not-a-real-provider-secret"
        for error in (HTTPError("http://example.test/"+secret,401,secret,{},io.BytesIO(secret.encode())),
                      URLError(secret), RuntimeError(secret)):
            e=self.client(api_key=secret,extra_headers={"X-Test":secret})
            with patch.object(e._opener,"open",side_effect=error):
                try: e.embed(["private input"])
                except EmbeddingError as exc:
                    self.assertNotIn(secret,str(exc))
                    self.assertNotIn(secret,traceback.format_exc())
                    self.assertNotIn("private input",str(exc))
                else: self.fail("must fail closed")
            self.assertNotIn(secret,repr(e))
        e=self.client()
        with patch.object(e._opener,"open",return_value=io.BytesIO(secret.encode())):
            with self.assertRaises(EmbeddingError): e.embed(["a"])

    def test_no_redirects(self):
        from knowledge_sdk.retrieval.adapters.openai_embedder import _NoRedirect
        self.assertIsNone(_NoRedirect().redirect_request(None,None,302,"",{},"https://other.test"))

    def test_configuration_and_input_validation(self):
        for kwargs in ({"dimensions":0},{"batch_size":0},{"batch_size":None},{"timeout":0},
                       {"timeout":float("nan")},{"api_key":"bad\nvalue"},
                       {"extra_headers":{"Authorization":"bad"}}, {"extra_headers":{"X":"bad\rvalue"}}):
            with self.assertRaises(ValidationError): self.client(**kwargs)
        for url in ("file:///tmp", "http://user:pass@host", "http://host/?key=secret", "http://host/#fragment", "http://host:bad"):
            with self.assertRaises(ValidationError): OpenAICompatibleEmbedder(url,"m")
        for texts in ("text",[1],None):
            with self.assertRaises(ValidationError): self.client().embed(texts)

    def test_stdlib_only(self):
        import subprocess,sys
        subprocess.run([sys.executable,"-S","-c",
                        "from knowledge_sdk import OpenAICompatibleEmbedder; "
                        "assert not OpenAICompatibleEmbedder('http://localhost/v1','m').non_semantic"],check=True)
