import hashlib
import json
import os
import unittest
from unittest.mock import patch
from app import domain, aws_handlers as aws
from app.runtime import Store


class Conditional(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class Dynamo:
    def __init__(self):
        self.items = {}

    def put_item(self, **kw):
        item = kw["Item"]
        if item["id"]["S"] in self.items:
            raise Conditional()
        self.items[item["id"]["S"]] = item.copy()

    def get_item(self, **kw):
        item = self.items.get(kw["Key"]["id"]["S"])
        return {"Item": item.copy()} if item else {}

    def update_item(self, **kw):
        item = self.items[kw["Key"]["id"]["S"]]
        values = kw["ExpressionAttributeValues"]
        if "ConditionExpression" in kw:
            if item["status"]["S"] not in ("queued", "retry") and not (item["status"]["S"] == "running" and int(item.get("lease_until", {"N":"0"})["N"]) < int(values[":now"]["N"])):
                raise Conditional()
            item["status"] = values[":running"]
            item["lease_until"] = values[":lease"]
        elif ":done" in values:
            item["status"] = values[":done"]
            item["result_key"] = values[":key"]
        else:
            item["status"] = values[":retry"]


class Queue:
    def __init__(self):
        self.messages = []
        self.fail = False

    def send_message(self, **kw):
        if self.fail:
            raise RuntimeError("down")
        self.messages.append(kw["MessageBody"])


class Bedrock:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def converse(self, **kw):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider unavailable")
        return {"output": {"message": {"content": [{"text": "Resumen del documento"}]}}, "usage": {"inputTokens": 12, "outputTokens": 6}}


class S3:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kw):
        self.objects[kw["Key"]] = kw


class LocalTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.close()

    def run_operation(self, payload, key):
        return self.store.run(payload, key, domain.process)[0]["result"]

    def test_inline_demo_completed(self):
        result = self.run_operation(domain.DEMO, "demo")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["result"]["method"], "extractive_local")

    def test_queued_job_processes_once(self):
        job = self.run_operation({"text":"Documento uno"}, "submit")
        self.assertEqual(job["status"], "queued")
        payload = {"action":"process", "job_id":job["job_id"]}
        first = self.run_operation(payload, "process-1")
        second = self.run_operation(payload, "process-2")
        self.assertTrue(second["reused"])
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(self.store.connection.execute("SELECT count(*) FROM events WHERE kind='job.completed'").fetchone()[0], 1)

    def test_invalid_document_and_operation(self):
        for payload in [{"text":""}, {"text":"a"*20001}, {"text":"abc", "operation":"exec"}]:
            with self.assertRaises(ValueError):
                self.run_operation(payload,"invalid")

    def test_unknown_job(self):
        with self.assertRaises(ValueError):
            self.run_operation({"action":"process", "job_id":"unknown"}, "unknown")

    def test_extraction_is_pattern_based(self):
        result = self.run_operation({"text":"Revisar INC-123 y HR-456", "operation":"extract", "run_inline":True}, "extract")
        self.assertEqual(result["result"]["references"], ["INC-123","HR-456"])


class AwsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"JOBS_TABLE":"jobs", "QUEUE_URL":"queue", "RESULTS_BUCKET":"results", "MODEL_ID":"test-model"})
        self.env.start()
        self.db, self.queue, self.s3, self.model = Dynamo(), Queue(), S3(), Bedrock()
        self.services = {"dynamodb":self.db,"sqs":self.queue,"s3":self.s3,"bedrock-runtime":self.model}

    def tearDown(self):
        self.env.stop()

    def submit(self, text="Documento operativo", key="request-1"):
        event={"requestContext":{"http":{"method":"POST"}},"headers":{"Idempotency-Key":key},"body":json.dumps({"text":text})}
        return aws.api_handler(event,None,self.services)

    def event(self, key="request-1", identifier="message-1"):
        return {"Records":[{"messageId":identifier,"body":json.dumps({"job_id":hashlib.sha256(key.encode()).hexdigest()})}]}

    def test_submit_is_durable_and_retries_reenqueue(self):
        first=self.submit()
        second=self.submit()
        self.assertEqual(first["statusCode"],202)
        self.assertEqual(json.loads(first["body"])["job_id"],json.loads(second["body"])["job_id"])
        self.assertEqual(len(self.db.items),1)
        self.assertEqual(len(self.queue.messages),2)

    def test_key_conflict(self):
        self.submit()
        self.assertEqual(self.submit("Otro documento")["statusCode"],409)

    def test_send_failure_repaired_by_client_retry(self):
        self.queue.fail=True
        self.assertEqual(self.submit()["statusCode"],503)
        self.assertEqual(len(self.db.items),1)
        self.queue.fail=False
        self.assertEqual(self.submit()["statusCode"],202)

    def test_worker_completion_s3_and_dedup(self):
        self.submit()
        self.assertEqual(aws.worker_handler(self.event(),None,self.services),{"batchItemFailures":[]})
        self.assertEqual(aws.worker_handler(self.event(),None,self.services),{"batchItemFailures":[]})
        self.assertEqual(self.model.calls,1)
        self.assertEqual(len(self.s3.objects),1)
        self.assertEqual(next(iter(self.s3.objects.values()))["ServerSideEncryption"],"AES256")

    def test_completed_submission_does_not_reenqueue(self):
        self.submit()
        aws.worker_handler(self.event(),None,self.services)
        self.submit()
        self.assertEqual(len(self.queue.messages),1)

    def test_provider_failure_returns_partial_batch_failure(self):
        self.submit()
        self.model.fail=True
        result=aws.worker_handler(self.event(),None,self.services)
        self.assertEqual(result["batchItemFailures"],[{"itemIdentifier":"message-1"}])
        self.assertEqual(next(iter(self.db.items.values()))["status"]["S"],"retry")
        self.model.fail=False
        self.assertEqual(aws.worker_handler(self.event(),None,self.services)["batchItemFailures"],[])

    def test_active_lease_does_not_invoke_model(self):
        self.submit()
        item=next(iter(self.db.items.values()))
        item["status"]={"S":"running"}
        item["lease_until"]={"N":"9999999999"}
        self.assertTrue(aws.worker_handler(self.event(),None,self.services)["batchItemFailures"])
        self.assertEqual(self.model.calls,0)

    def test_expired_lease_can_be_recovered(self):
        self.submit()
        item=next(iter(self.db.items.values()))
        item["status"]={"S":"running"}
        item["lease_until"]={"N":"1"}
        self.assertEqual(aws.worker_handler(self.event(),None,self.services)["batchItemFailures"],[])

    def test_malformed_queue_message_is_not_acknowledged(self):
        result=aws.worker_handler({"Records":[{"messageId":"bad","body":"{}"}]},None,self.services)
        self.assertEqual(result["batchItemFailures"],[{"itemIdentifier":"bad"}])

    def test_invalid_http_body(self):
        event={"requestContext":{"http":{"method":"POST"}},"headers":{"idempotency-key":"key"},"body":"null"}
        self.assertEqual(aws.api_handler(event,None,self.services)["statusCode"],422)

    def test_status_unknown_job(self):
        event={"requestContext":{"http":{"method":"GET"}},"pathParameters":{"id":"a"*64}}
        self.assertEqual(aws.api_handler(event,None,self.services)["statusCode"],404)


if __name__ == "__main__":
    unittest.main()
