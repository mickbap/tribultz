"""Unit tests for the object-storage probe (_probe_s3) — #399.

Kept in a separate file (no autouse _probe_s3 patch) so the real function runs.
boto3 is mocked; no live storage needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


class TestS3Probe:
    def _cfg(self, cfg, endpoint="https://br-se1.magaluobjects.com", bucket="tribultz"):
        cfg.S3_ENDPOINT = endpoint
        cfg.S3_BUCKET = bucket
        cfg.S3_ACCESS_KEY = "key"
        cfg.S3_SECRET_KEY = "secret"
        cfg.S3_REGION = "br-se1"
        cfg.S3_FORCE_PATH_STYLE = False

    def test_unconfigured_when_no_endpoint(self):
        with patch("app.routers.health.settings") as cfg:
            self._cfg(cfg, endpoint="")
            from app.routers.health import _probe_s3
            assert _probe_s3() == "unconfigured"

    def test_unconfigured_when_no_bucket(self):
        with patch("app.routers.health.settings") as cfg:
            self._cfg(cfg, bucket="")
            from app.routers.health import _probe_s3
            assert _probe_s3() == "unconfigured"

    def test_ok_when_head_bucket_succeeds(self):
        mock_client = MagicMock()
        with (
            patch("app.routers.health.settings") as cfg,
            patch("app.routers.health.boto3.client", return_value=mock_client),
        ):
            self._cfg(cfg)
            from app.routers.health import _probe_s3
            assert _probe_s3() == "ok"
        mock_client.head_bucket.assert_called_once_with(Bucket="tribultz")

    def test_unreachable_on_timeout(self):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = Exception("connect timeout")
        with (
            patch("app.routers.health.settings") as cfg,
            patch("app.routers.health.boto3.client", return_value=mock_client),
        ):
            self._cfg(cfg, endpoint="https://dead.endpoint.invalid")
            from app.routers.health import _probe_s3
            assert _probe_s3() == "unreachable"

    def test_unreachable_on_invalid_credentials(self):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadBucket"
        )
        with (
            patch("app.routers.health.settings") as cfg,
            patch("app.routers.health.boto3.client", return_value=mock_client),
        ):
            self._cfg(cfg)
            from app.routers.health import _probe_s3
            assert _probe_s3() == "unreachable"
