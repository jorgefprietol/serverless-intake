import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from app.runtime import Store, Conflict, handler
from app import providers


def work(payload, store):
    store.event("accepted", {"id": payload.get("id")})
    if payload.get("internal"):
        raise RuntimeError("confidential_internal_details")
    if payload.get("fail"):
        raise ValueError("invalid")
    return {"accepted": True}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        Path("var").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir="var")
        self.store = Store(Path(self.temp.name)/"test.db")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_replay_has_no_duplicate_events(self):
        first, replay = self.store.run({"id": "1"}, "key", work)
        second, replay2 = self.store.run({"id": "1"}, "key", work)
        self.assertEqual(first, second)
        self.assertFalse(replay)
        self.assertTrue(replay2)
        self.assertEqual(self.store.metrics()["audit_events"], 1)

    def test_key_reuse_conflict(self):
        self.store.run({"id": 1}, "key", work)
        with self.assertRaises(Conflict):
            self.store.run({"id": 2}, "key", work)

    def test_reordered_json_is_same_content(self):
        first, _ = self.store.run({"a":1,"b":2}, "ordered", work)
        second, replay = self.store.run({"b":2,"a":1}, "ordered", work)
        self.assertTrue(replay)
        self.assertEqual(first,second)

    def test_failure_rolls_back_domain_events(self):
        with self.assertRaises(ValueError):
            self.store.run({"fail": True}, "key", work)
        self.assertEqual(self.store.metrics()["audit_events"], 0)
        self.assertEqual(self.store.metrics()["completed_requests"], 0)

    def test_failed_key_can_be_retried(self):
        with self.assertRaises(ValueError):
            self.store.run({"fail": True}, "retry", work)
        result, replay = self.store.run({}, "retry", work)
        self.assertFalse(replay)

    def test_invalid_key_and_payload(self):
        for payload, key in [(None, "x"), ({}, ""), ({}, "with space"), ({}, "x"*129)]:
            with self.assertRaises(ValueError):
                self.store.run(payload, key, work)

    def test_metrics_exclude_replay(self):
        self.store.run({}, "same", work)
        self.store.run({}, "same", work)
        self.assertEqual(self.store.metrics()["completed_requests"], 1)

    def test_local_provider_does_not_invent_result(self):
        with patch.dict(os.environ, {"MODEL_BACKEND": "local"}):
            with self.assertRaises(ValueError):
                providers.generate("question")

    def test_provider_schema_is_forwarded_and_decoded(self):
        with patch.object(providers, "_request", return_value='{"ok": true}') as call:
            self.assertEqual(providers.structured("prompt", {"type":"object"}), {"ok":True})
            self.assertEqual(call.call_args[0][2], {"type":"object"})

    def test_ollama_wire_contract(self):
        from unittest.mock import MagicMock
        wire=MagicMock()
        wire.open.return_value.__enter__.return_value.read.return_value=json.dumps({"response":json.dumps({"ok":True}),"done":True}).encode()
        with patch.dict(os.environ,{"MODEL_BACKEND":"ollama","OLLAMA_MODEL":"installed-model","OLLAMA_URL":"http://127.0.0.1:11434"}), patch.object(providers,"build_opener",return_value=wire):
            result=providers.structured("document",{"type":"object"})
        self.assertEqual(result,{"ok":True})
        request=wire.open.call_args[0][0]
        body=json.loads(request.data)
        self.assertEqual(request.full_url,"http://127.0.0.1:11434/api/generate")
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"],{"type":"object"})
        self.assertEqual(wire.open.call_args.kwargs["timeout"],45)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Path("var").mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir="var")
        domain = SimpleNamespace(TITLE="Test", DESCRIPTION="Test service", DEMO={}, process=work)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler(domain, Path(cls.temp.name)/"http.db", "test-service-token-at-least-24"))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:"+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, payload=None, authorized=True, key="http-1", extra=None):
        headers={"Content-Type":"application/json", "Idempotency-Key":key}
        if authorized:
            headers["Authorization"]="Bearer test-service-token-at-least-24"
        headers.update(extra or {})
        req=Request(self.url+path, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            return urlopen(req, timeout=5)
        except HTTPError as error:
            return error

    def test_health_and_ui(self):
        with self.request("/health", authorized=False) as response:
            self.assertEqual(json.load(response)["status"], "ok")
        with self.request("/", authorized=False) as response:
            self.assertIn(b"Operations Lab", response.read())

    def test_post_requires_authentication(self):
        with self.request("/api/run", {}, authorized=False) as response:
            self.assertEqual(response.status, 401)

    def test_metrics_requires_authentication(self):
        with self.request("/api/metrics", authorized=False) as response:
            self.assertEqual(response.status, 401)

    def test_content_type_validation(self):
        with self.request("/api/run", {}, extra={"Content-Type":"text/plain"}) as response:
            self.assertEqual(response.status, 415)

    def test_replay_and_conflict_over_http(self):
        with self.request("/api/run", {"id":1}) as first:
            result=json.load(first)
        with self.request("/api/run", {"id":1}) as second:
            self.assertEqual(json.load(second), result)
            self.assertEqual(second.headers["Idempotency-Replayed"], "true")
        with self.request("/api/run", {"id":2}) as third:
            self.assertEqual(third.status, 409)

    def test_missing_key_rejected(self):
        with self.request("/api/run", {}, key="") as response:
            self.assertEqual(response.status, 422)

    def test_internal_exception_is_redacted(self):
        with self.request("/api/run", {"internal":True}, key="fail-internal") as response:
            self.assertEqual(response.status, 500)
            self.assertNotIn(b"confidential", response.read())

    def test_non_object_payload_rejected(self):
        with self.request("/api/run", [1,2], key="list") as response:
            self.assertEqual(response.status,422)

    def test_concurrent_replay_records_one_transaction(self):
        from concurrent.futures import ThreadPoolExecutor
        def submit(_):
            with self.request("/api/run", {"id":"parallel"}, key="parallel") as response:
                return json.load(response)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(submit,[1,2]))
        self.assertEqual(results[0], results[1])
        store=Store(Path(self.temp.name)/"http.db")
        try:
            self.assertEqual(store.connection.execute("SELECT count(*) FROM requests WHERE key='parallel'").fetchone()[0],1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
