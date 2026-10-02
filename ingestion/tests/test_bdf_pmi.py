from unittest.mock import MagicMock, patch

import pytest

import bdf_pmi

SERIES = ("CONJ2.M.R52.S.IN.000CZ.ICAIN000.10", "CONJ2.M.R52.S.IN.000CZ.PRTEM100.10")


def test_build_headers_requires_api_key(monkeypatch):
    monkeypatch.delenv("BDF_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="BDF_API_KEY"):
        bdf_pmi.build_headers()


def test_build_headers_uses_apikey_authorization(monkeypatch):
    monkeypatch.setenv("BDF_API_KEY", "secret")
    assert bdf_pmi.build_headers() == {"Authorization": "Apikey secret"}


def test_build_where_clause_filters_series_only_without_bounds():
    assert bdf_pmi.build_where_clause(SERIES, None, None) == (
        'series_key IN ("CONJ2.M.R52.S.IN.000CZ.ICAIN000.10", "CONJ2.M.R52.S.IN.000CZ.PRTEM100.10")'
    )


def test_build_where_clause_adds_inclusive_period_bounds():
    where = bdf_pmi.build_where_clause(SERIES, "2018-01", "2024-12")
    assert where.endswith("and time_period_start >= date'2018-01-01' and time_period_start <= date'2024-12-01'")


def test_build_where_clause_accepts_a_single_bound():
    assert "date'2020-03-01'" in bdf_pmi.build_where_clause(SERIES, "2020-03", None)
    assert "time_period_start <=" not in bdf_pmi.build_where_clause(SERIES, "2020-03", None)


def test_fetch_records_calls_export_with_auth_and_selected_fields(monkeypatch):
    monkeypatch.setenv("BDF_API_KEY", "secret")
    rows = [{"series_key": SERIES[0], "title_fr": "T", "time_period": "2024-01", "obs_value": 98.5, "obs_status": "A"}]
    response = MagicMock()
    response.json.return_value = rows

    with patch.object(bdf_pmi, "get_with_retry", return_value=response) as mock_get:
        records = bdf_pmi.fetch_records(SERIES, "2018-01", "2024-12")

    assert records == rows
    assert mock_get.call_args.args[0] == bdf_pmi.BDF_EXPORT_URL
    assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Apikey secret"}
    params = mock_get.call_args.kwargs["params"]
    assert params["select"] == "series_key,title_fr,time_period,obs_value,obs_status"
    assert "date'2018-01-01'" in params["where"]


def test_fetch_records_fails_before_any_call_without_api_key(monkeypatch):
    monkeypatch.delenv("BDF_API_KEY", raising=False)
    with patch.object(bdf_pmi, "get_with_retry") as mock_get:
        with pytest.raises(RuntimeError):
            bdf_pmi.fetch_records()
    mock_get.assert_not_called()


def test_default_series_keys_are_pdl_conjoncture():
    assert all(key.startswith("CONJ2.M.R52.") for key in bdf_pmi.DEFAULT_SERIES_KEYS)


def test_selected_fields_cover_staging_contract():
    assert {"series_key", "title_fr", "time_period", "obs_value"} <= set(bdf_pmi.SELECTED_FIELDS.split(","))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [(None, None, "full"), ("2020-01", "2024-12", "2020-01/2024-12"), (None, "2024-12", "/2024-12")],
)
def test_load_to_bronze_traces_requested_window(start, end, expected):
    with patch.object(bdf_pmi, "append_to_bronze", return_value=1) as mock_append:
        bdf_pmi.load_to_bronze([{"a": 1}], start, end)
    mock_append.assert_called_once_with("raw_bdf_pmi", [{"a": 1}], "CONJ2", expected)
