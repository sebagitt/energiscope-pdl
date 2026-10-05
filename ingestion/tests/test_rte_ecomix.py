import argparse
from datetime import date, datetime, timedelta, timezone
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


def _slots(first: datetime, count: int, step_minutes: int = 15) -> list[dict]:
    return [
        {"date_heure": (first + timedelta(minutes=step_minutes * i)).isoformat(), "consommation": 3000 + i}
        for i in range(count)
    ]


def test_filter_recent_window_is_half_open_and_holds_eight_slots_for_120_minutes():
    now = datetime(2026, 10, 5, 12, 7, tzinfo=timezone.utc)
    records = _slots(datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc), 96)

    recent = rte_ecomix.filter_recent(records, now - timedelta(minutes=120), now)

    assert len(recent) == 8
    assert recent[0]["date_heure"] == "2026-10-05T10:15:00+00:00"
    assert recent[-1]["date_heure"] == "2026-10-05T12:00:00+00:00"


@pytest.mark.parametrize("offset_minutes", [0, 1, 7, 14])
def test_filter_recent_never_exceeds_eight_slots_whatever_the_alignment(offset_minutes):
    now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)
    records = _slots(datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc), 96)
    assert len(rte_ecomix.filter_recent(records, now - timedelta(minutes=120), now)) == 8


def test_filter_recent_start_is_inclusive_and_end_is_exclusive():
    start = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 5, 10, 30, tzinfo=timezone.utc)
    records = _slots(datetime(2026, 10, 5, 9, 45, tzinfo=timezone.utc), 4)  # 9:45, 10:00, 10:15, 10:30
    assert [r["date_heure"][11:16] for r in rte_ecomix.filter_recent(records, start, end)] == ["10:00", "10:15"]


def test_filter_recent_skips_invalid_records_and_reads_naive_dates_as_utc():
    start = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)
    records = [
        {"consommation": 1},
        {"date_heure": None},
        {"date_heure": "pas une date"},
        {"date_heure": "2026-10-05T10:30:00"},
        {"date_heure": "2026-10-05T12:30:00+02:00"},  # 10:30 UTC
        {"date_heure": "2026-10-05T10:30:00+00:00", "ok": True},
    ]
    kept = rte_ecomix.filter_recent(records, start, end)
    assert len(kept) == 3
    assert kept[-1].get("ok") is True


def test_fetch_recent_spans_utc_midnight_so_no_slot_after_paris_midnight_is_missed():
    now = datetime(2026, 10, 6, 0, 20, tzinfo=timezone.utc)
    records = _slots(datetime(2026, 10, 5, 22, 0, tzinfo=timezone.utc), 12)

    with patch.object(rte_ecomix, "fetch_window", return_value=records) as mock_window:
        recent = rte_ecomix.fetch_recent(120, "eco2mix-regional-tr", now=now)

    start_day, end_day, dataset = mock_window.call_args.args
    assert (start_day, end_day, dataset) == (date(2026, 10, 5), date(2026, 10, 7), "eco2mix-regional-tr")
    assert recent[0]["date_heure"] == "2026-10-05T22:30:00+00:00"
    assert len(recent) == 8


def test_fetch_recent_defaults_to_the_present_instant():
    with patch.object(rte_ecomix, "fetch_window", return_value=[]) as mock_window:
        assert rte_ecomix.fetch_recent(60, "eco2mix-regional-tr") == []
    today = datetime.now(timezone.utc).date()
    assert mock_window.call_args.args[1] == today + timedelta(days=1)


@pytest.mark.parametrize(("value", "expected"), [("120", 120), ("1", 1)])
def test_positive_int_accepts_positive_integers(value, expected):
    assert rte_ecomix.positive_int(value) == expected


@pytest.mark.parametrize("value", ["0", "-5", "abc", "", "1.5"])
def test_positive_int_rejects_everything_else(value):
    with pytest.raises(argparse.ArgumentTypeError, match="entier > 0"):
        rte_ecomix.positive_int(value)


def _run_main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["rte_ecomix.py", *argv])
    rte_ecomix.main()


def test_main_with_since_loads_only_the_recent_window_labelled_with_the_date(monkeypatch):
    recent = [{"date_heure": "2026-10-05T11:45:00+00:00"}]
    with patch.object(rte_ecomix, "fetch_recent", return_value=recent) as mock_recent, patch.object(
        rte_ecomix, "fetch_records"
    ) as mock_day, patch.object(rte_ecomix, "load_to_bronze") as mock_load:
        _run_main(monkeypatch, "--date", "2026-10-05", "--dataset", "tr", "--since", "120")

    mock_recent.assert_called_once_with(120, "eco2mix-regional-tr")
    mock_day.assert_not_called()
    mock_load.assert_called_once_with(recent, "eco2mix-regional-tr", date(2026, 10, 5))


def test_main_without_since_keeps_the_full_day_behaviour(monkeypatch):
    with patch.object(rte_ecomix, "fetch_recent") as mock_recent, patch.object(
        rte_ecomix, "fetch_records", return_value=[{"a": 1}]
    ) as mock_day, patch.object(rte_ecomix, "load_to_bronze") as mock_load:
        _run_main(monkeypatch, "--date", "2026-10-05")

    mock_recent.assert_not_called()
    mock_day.assert_called_once_with(date(2026, 10, 5), "eco2mix-regional-tr")
    mock_load.assert_called_once()


@pytest.mark.parametrize(
    "argv",
    [
        ("--start-date", "2018-01", "--since", "120"),
        ("--date", "2026-10-05", "--since", "0"),
        ("--date", "2026-10-05", "--since", "abc"),
    ],
)
def test_main_rejects_invalid_since_combinations(monkeypatch, argv):
    with pytest.raises(SystemExit) as exit_info:
        _run_main(monkeypatch, *argv)
    assert exit_info.value.code == 2
