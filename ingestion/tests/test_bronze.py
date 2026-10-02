import argparse
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

import bronze


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_http_error(500), True),
        (_http_error(429), True),
        (_http_error(401), False),
        (_http_error(404), False),
        (requests.ConnectionError(), True),
        (requests.Timeout(), True),
        (ValueError(), False),
    ],
)
def test_is_retryable(exc, expected):
    assert bronze.is_retryable(exc) is expected


def test_get_with_retry_retries_three_times_on_server_error():
    response = MagicMock()
    response.raise_for_status.side_effect = _http_error(503)
    with patch.object(bronze.requests, "get", return_value=response) as mock_get, patch("tenacity.nap.time.sleep"):
        with pytest.raises(requests.HTTPError):
            bronze.get_with_retry("https://example.org")
    assert mock_get.call_count == 3


def test_get_with_retry_does_not_retry_on_auth_error():
    response = MagicMock()
    response.raise_for_status.side_effect = _http_error(401)
    with patch.object(bronze.requests, "get", return_value=response) as mock_get:
        with pytest.raises(requests.HTTPError):
            bronze.get_with_retry("https://example.org")
    assert mock_get.call_count == 1


def test_build_insert_statement_has_one_tuple_per_row():
    statement = bronze.build_insert_statement("c.bronze.raw_x", 2)
    assert statement.count("(:dataset_") == 2
    assert ":payload_1" in statement
    assert ":payload_2" not in statement


def test_append_to_bronze_skips_empty_batch():
    with patch.object(bronze, "connect") as mock_connect:
        assert bronze.append_to_bronze("raw_x", [], "ds", "2024") == 0
    mock_connect.assert_not_called()


def _mock_connection():
    cursor = MagicMock()
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


def test_append_to_bronze_inserts_in_batches_with_json_payload(monkeypatch):
    monkeypatch.setattr(bronze, "INSERT_BATCH_SIZE", 2)
    monkeypatch.setenv("DATABRICKS_CATALOG", "cat")
    connection, cursor = _mock_connection()

    records = [{"nom": f"Café {i}"} for i in range(5)]
    with patch.object(bronze, "connect", return_value=connection):
        loaded = bronze.append_to_bronze("raw_x", records, "ds", "2024")

    assert loaded == 5
    inserts = [c for c in cursor.execute.call_args_list if c.args[0].startswith("INSERT")]
    assert [sum(k.startswith("payload_") for k in c.args[1]) for c in inserts] == [2, 2, 1]
    assert "cat.bronze.raw_x" in inserts[0].args[0]

    first_params = inserts[0].args[1]
    assert json.loads(first_params["payload_0"]) == {"nom": "Café 0"}
    assert "Café" in first_params["payload_0"]
    assert first_params["dataset_0"] == "ds"
    assert first_params["extracted_for_0"] == "2024"
    assert isinstance(first_params["ingested_at"], datetime)


def test_append_to_bronze_creates_schema_and_table_first():
    connection, cursor = _mock_connection()
    with patch.object(bronze, "connect", return_value=connection):
        bronze.append_to_bronze("raw_x", [{"a": 1}], "ds", "full")
    statements = [c.args[0].strip() for c in cursor.execute.call_args_list]
    assert statements[0].startswith("CREATE SCHEMA IF NOT EXISTS")
    assert statements[1].startswith("CREATE TABLE IF NOT EXISTS")
    assert statements[2].startswith("INSERT")


@pytest.mark.parametrize("value", ["2020-01", "2024-12", "1999-06"])
def test_year_month_accepts_valid_periods(value):
    assert bronze.year_month(value) == value


@pytest.mark.parametrize("value", ["2020", "2020-13", "2020-1-1", "01-2020", "abc", ""])
def test_year_month_rejects_invalid_periods(value):
    with pytest.raises(argparse.ArgumentTypeError, match="YYYY-MM"):
        bronze.year_month(value)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [(None, None, "full"), ("2020-01", "2024-12", "2020-01/2024-12"), ("2020-01", None, "2020-01/"), (None, "2024-12", "/2024-12")],
)
def test_period_label(start, end, expected):
    assert bronze.period_label(start, end) == expected
