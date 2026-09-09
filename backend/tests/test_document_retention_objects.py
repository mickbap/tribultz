"""Retention removes both staging and confirmed content, retaining failed work."""
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from app.tasks import task_j_retention as retention


@pytest.mark.parametrize("fail_staging", [False, True])
def test_retention_handles_both_objects(monkeypatch, fail_staging):
    doc = SimpleNamespace(id="doc", storage_key="final", fiscal_metadata={"upload_storage_key": "staging"})
    db = Mock()
    db.execute.return_value.scalars.return_value.all.return_value = [doc]
    monkeypatch.setattr(retention, "SessionLocal", lambda: db)
    delete = Mock(side_effect=[None, ConnectionError("unavailable")] if fail_staging else None)
    monkeypatch.setattr(retention, "delete_object", delete)
    retention.purge_expired_documents.run()
    assert delete.call_args_list == [call("final"), call("staging")]
    if fail_staging:
        db.delete.assert_not_called()
    else:
        db.delete.assert_called_once_with(doc)
    db.close.assert_called_once()
