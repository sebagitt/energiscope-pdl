from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

import rte_ecomix


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


def test_build_where_clause_filters_region_and_local_day():
    assert rte_ecomix.build_where_clause(date(2026, 9, 30)) == (
        "code_insee_region = '52' and date = '2026-09-30'"
    )


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_http_error(500), True),
        (_http_error(503), True),
        (_http_error(429), True),
        (_http_error(400), False),
        (_http_error(404), False),
        (requests.ConnectionError(), True),
        (requests.Timeout(), True),
        (ValueError(), False),
    ],
)
def test_is_retryable(exc, expected):
    assert rte_ecomix._is_retryable(exc) is expected


def test_get_json_retries_three_times_on_server_error():
    response = MagicMock()
    response.raise_for_status.side_effect = _http_error(503)
    with patch.object(rte_ecomix.requests, "get", return_value=response) as mock_get, patch(
        "tenacity.nap.time.sleep"
    ):
        with pytest.raises(requests.HTTPError):
            rte_ecomix._get_json("https://example.org", {}, {})
    assert mock_get.call_count == 3


def test_get_json_does_not_retry_on_client_error():
    response = MagicMock()
    response.raise_for_status.side_effect = _http_error(400)
    with patch.object(rte_ecomix.requests, "get", return_value=response) as mock_get:
        with pytest.raises(requests.HTTPError):
            rte_ecomix._get_json("https://example.org", {}, {})
    assert mock_get.call_count == 1


def test_fetch_records_sends_api_key_when_set(monkeypatch):
    monkeypatch.setenv("RTE_API_KEY", "secret")
    with patch.object(rte_ecomix, "_get_json", return_value=[{"date": "2026-09-30"}]) as mock_get:
        records = rte_ecomix.fetch_records(date(2026, 9, 30))
    assert records == [{"date": "2026-09-30"}]
    _, kwargs = mock_get.call_args
    assert kwargs["headers"] == {"Authorization": "Apikey secret"}


def test_build_insert_statement_has_one_tuple_per_row():
    statement = rte_ecomix.build_insert_statement("c.bronze.raw_rte_ecomix", 2)
    assert statement.count("(:dataset_") == 2
    assert ":payload_1" in statement
    assert ":payload_2" not in statement


def test_load_to_bronze_skips_empty_batch():
    with patch.object(rte_ecomix, "_connect") as mock_connect:
        assert rte_ecomix.load_to_bronze([], "eco2mix-regional-tr", date(2026, 9, 30)) == 0
    mock_connect.assert_not_called()


def test_load_to_bronze_inserts_in_batches(monkeypatch):
    monkeypatch.setattr(rte_ecomix, "INSERT_BATCH_SIZE", 2)
    cursor = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor

    records = [{"consommation": i} for i in range(5)]
    with patch.object(rte_ecomix, "_connect", return_value=connection):
        loaded = rte_ecomix.load_to_bronze(records, "eco2mix-regional-tr", date(2026, 9, 30))

    assert loaded == 5
    insert_calls = [c for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT")]
    assert [len([k for k in c.args[1] if k.startswith("payload_")]) for c in insert_calls] == [2, 2, 1]


def test_month_windows_covers_inclusive_range_across_year_end():
    windows = rte_ecomix.month_windows("2018-11", "2019-02")
    assert [w[0] for w in windows] == ["2018-11", "2018-12", "2019-01", "2019-02"]
    assert windows[1][1:] == (date(2018, 12, 1), date(2019, 1, 1))
    assert windows[-1][1:] == (date(2019, 2, 1), date(2019, 3, 1))


def test_month_windows_is_contiguous_so_no_slot_is_lost_or_duplicated():
    windows = rte_ecomix.month_windows("2018-01", "2026-06")
    assert len(windows) == 102
    assert all(current[2] == following[1] for current, following in zip(windows, windows[1:]))


def test_month_windows_single_month_and_empty_range():
    assert [w[0] for w in rte_ecomix.month_windows("2024-05", "2024-05")] == ["2024-05"]
    assert rte_ecomix.month_windows("2024-06", "2024-05") == []


def test_build_range_where_uses_utc_datetime_bounds():
    assert rte_ecomix.build_range_where(date(2018, 1, 1), date(2018, 2, 1)) == (
        "code_insee_region = '52' and date_heure >= date'2018-01-01' and date_heure < date'2018-02-01'"
    )


def test_fetch_window_calls_export_endpoint():
    with patch.object(rte_ecomix, "_get_json", return_value=[{"a": 1}]) as mock_get:
        assert rte_ecomix.fetch_window(date(2018, 1, 1), date(2018, 2, 1), "eco2mix-regional-cons-def") == [{"a": 1}]
    assert mock_get.call_args.args[0].endswith("/eco2mix-regional-cons-def/exports/json")
    assert "date_heure >= date'2018-01-01'" in mock_get.call_args.kwargs["params"]["where"]


def test_backfill_loads_each_month_with_its_label_and_returns_total():
    with patch.object(rte_ecomix, "fetch_window", side_effect=[[{"i": 1}, {"i": 2}], [], [{"i": 3}]]), patch.object(
        rte_ecomix, "append_to_bronze", side_effect=[2, 0, 1]
    ) as mock_append:
        total = rte_ecomix.backfill("2018-01", "2018-03", "eco2mix-regional-cons-def")

    assert total == 3
    labels = [c.args[3] for c in mock_append.call_args_list]
    assert labels == ["2018-01", "2018-02", "2018-03"]
    assert mock_append.call_args_list[0].args[:3] == ("raw_rte_ecomix", [{"i": 1}, {"i": 2}], "eco2mix-regional-cons-def")
