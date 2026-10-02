"""Tests de bdf_pmi.py.

Les fixtures reproduisent le format SDMX-JSON *supposé* de Webstat : il n'a pas été vérifié
contre l'API réelle (clé indisponible). Ces tests valident la logique du script, pas le contrat
de l'API : à confirmer avec un premier appel réel.
"""

from unittest.mock import MagicMock, patch

import pytest

import bdf_pmi

SDMX_JSON = {
    "structure": {"dimensions": {"observation": [{"id": "TIME_PERIOD", "values": [{"id": "2026-05"}, {"id": "2026-06"}]}]}},
    "dataSets": [{"series": {"0:0:0": {"observations": {"0": [101.5, 0], "1": [99.0, 0]}}}}],
}


def test_build_headers_requires_api_key(monkeypatch):
    monkeypatch.delenv("BDF_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BDF_API_KEY"):
        bdf_pmi.build_headers()


def test_build_headers_sends_client_id(monkeypatch):
    monkeypatch.setenv("BDF_API_KEY", "secret")
    assert bdf_pmi.build_headers()["X-IBM-Client-Id"] == "secret"


def test_parse_observations_flattens_one_row_per_period():
    records = bdf_pmi.parse_observations(SDMX_JSON, "CONJ2.M.R52.S.IN.000CZ.ICAIN000.10", "Climat des affaires")

    assert records == [
        {"series_key": "CONJ2.M.R52.S.IN.000CZ.ICAIN000.10", "title_fr": "Climat des affaires", "time_period": "2026-05", "obs_value": 101.5},
        {"series_key": "CONJ2.M.R52.S.IN.000CZ.ICAIN000.10", "title_fr": "Climat des affaires", "time_period": "2026-06", "obs_value": 99.0},
    ]


def test_parse_observations_keeps_staging_contract_keys():
    expected = {"series_key", "title_fr", "time_period", "obs_value"}
    assert all(set(r) == expected for r in bdf_pmi.parse_observations(SDMX_JSON, "K", "T"))


@pytest.mark.parametrize("payload", [{}, {"dataSets": []}, {"error": "unauthorized"}, None])
def test_parse_observations_fails_loudly_on_unexpected_structure(payload):
    with pytest.raises(ValueError, match="inattendue"):
        bdf_pmi.parse_observations(payload, "K", "T")


def test_fetch_records_requests_each_series_with_auth(monkeypatch):
    monkeypatch.setenv("BDF_API_KEY", "secret")
    response = MagicMock()
    response.json.return_value = SDMX_JSON
    series = {"CONJ2.M.R52.S.IN.000CZ.ICAIN000.10": "A", "CONJ2.M.R52.S.IN.000CZ.PRTEM100.10": "B"}

    with patch.object(bdf_pmi, "get_with_retry", return_value=response) as mock_get:
        records = bdf_pmi.fetch_records(series, start_period="2026-01")

    assert len(records) == 4
    assert mock_get.call_count == 2
    first = mock_get.call_args_list[0]
    assert first.args[0].endswith("/data/CONJ2/M.R52.S.IN.000CZ.ICAIN000.10")
    assert first.kwargs["headers"]["X-IBM-Client-Id"] == "secret"
    assert first.kwargs["params"] == {"format": "json", "startPeriod": "2026-01"}


def test_fetch_records_fails_before_any_call_without_api_key(monkeypatch):
    monkeypatch.delenv("BDF_API_KEY", raising=False)
    with patch.object(bdf_pmi, "get_with_retry") as mock_get:
        with pytest.raises(RuntimeError):
            bdf_pmi.fetch_records()
    mock_get.assert_not_called()


def test_default_series_keys_follow_catalog_naming():
    assert all(key.startswith("CONJ2.M.R52.") for key in bdf_pmi.DEFAULT_SERIES)


@pytest.mark.parametrize(("start", "expected"), [(None, "full"), ("2024-01", "2024-01")])
def test_load_to_bronze_traces_start_period(start, expected):
    with patch.object(bdf_pmi, "append_to_bronze", return_value=1) as mock_append:
        bdf_pmi.load_to_bronze([{"a": 1}], start)
    mock_append.assert_called_once_with("raw_bdf_pmi", [{"a": 1}], "CONJ2", expected)
