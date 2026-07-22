"""Tráfego do site (Cloudflare Analytics) — #518."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cloudflare_analytics import get_today_traffic


@pytest.mark.asyncio
async def test_sem_token_retorna_none_sem_chamar_api():
    with patch("app.services.cloudflare_analytics.settings") as mock_settings:
        mock_settings.CLOUDFLARE_ANALYTICS_TOKEN = ""
        with patch("httpx.AsyncClient") as mock_client_cls:
            result = await get_today_traffic()
    assert result is None
    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_resposta_valida_extrai_uniques_pageviews_requests():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "data": {
            "viewer": {
                "zones": [
                    {
                        "httpRequests1dGroups": [
                            {"uniq": {"uniques": 168}, "sum": {"requests": 1687, "pageViews": 117}}
                        ]
                    }
                ]
            }
        },
        "errors": None,
    }
    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response
    mock_client.__aenter__.return_value = mock_client

    with patch("app.services.cloudflare_analytics.settings") as mock_settings:
        mock_settings.CLOUDFLARE_ANALYTICS_TOKEN = "fake-token"
        mock_settings.CLOUDFLARE_ZONE_ID = "fake-zone"
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_today_traffic()

    assert result is not None
    assert result["uniques"] == 168
    assert result["page_views"] == 117
    assert result["requests"] == 1687


@pytest.mark.asyncio
async def test_erro_http_degrada_graciosamente():
    fake_response = MagicMock()
    fake_response.status_code = 403
    mock_client = AsyncMock()
    mock_client.post.return_value = fake_response
    mock_client.__aenter__.return_value = mock_client

    with patch("app.services.cloudflare_analytics.settings") as mock_settings:
        mock_settings.CLOUDFLARE_ANALYTICS_TOKEN = "fake-token"
        mock_settings.CLOUDFLARE_ZONE_ID = "fake-zone"
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_today_traffic()

    assert result is None


@pytest.mark.asyncio
async def test_excecao_de_rede_degrada_graciosamente():
    with patch("app.services.cloudflare_analytics.settings") as mock_settings:
        mock_settings.CLOUDFLARE_ANALYTICS_TOKEN = "fake-token"
        mock_settings.CLOUDFLARE_ZONE_ID = "fake-zone"
        with patch("httpx.AsyncClient", side_effect=Exception("timeout")):
            result = await get_today_traffic()

    assert result is None
