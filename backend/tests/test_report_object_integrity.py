"""Reports generated in the same second must preserve each returned checksum."""
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.tasks import task_b_report as report


@pytest.mark.parametrize("second_job,second_company", [("job-b", "Company A"), ("job-a", "Company B")])
def test_report_key_survives_other_job_or_changed_retry(monkeypatch, second_job, second_company):
    objects = {}

    def put(*, key, data, **kwargs):
        objects[key] = data
        return {"checksum_sha256": hashlib.sha256(data).hexdigest()}

    clock = Mock()
    clock.now.return_value = datetime(2026, 9, 9, tzinfo=timezone.utc)
    monkeypatch.setattr(report, "datetime", clock)
    monkeypatch.setattr(report, "put_object", put)
    monkeypatch.setattr(report, "get_object_url", lambda key, **kwargs: key)
    monkeypatch.setattr(report, "get_tax_rules", lambda *args: [])
    monkeypatch.setattr(report, "persist_artifact_metadata", Mock())
    monkeypatch.setattr(report, "insert_audit_log", Mock(return_value={"id": "audit"}))
    monkeypatch.setattr(report, "job_status_update", Mock())
    task = report.task_b_compliance_report

    def run(job, company):
        task.push_request(id=job)
        try:
            return task.run(tenant_id="tenant", tenant_slug="tenant", company_name=company,
                            cnpj="123", reference_period="2026-09", invoices=[])
        finally:
            task.pop_request()

    first = run("job-a", "Company A")
    second = run(second_job, second_company)
    assert first["s3_key"] != second["s3_key"]
    assert hashlib.sha256(objects[first["s3_key"]]).hexdigest() == first["checksum"]
    assert hashlib.sha256(objects[second["s3_key"]]).hexdigest() == second["checksum"]
    # An identical retry is safe and reuses its own content key.
    assert run(second_job, second_company)["s3_key"] == second["s3_key"]
