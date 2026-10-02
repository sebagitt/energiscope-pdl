from unittest.mock import MagicMock, patch

import enedis_conso


def _page(results, next_url=None):
    response = MagicMock()
    response.json.return_value = {"results": results, "next": next_url}
    return response


def test_build_params_filters_region_and_year():
    assert enedis_conso.build_params(2023) == {"size": 10000, "code_region_eq": "52", "annee_eq": 2023}


def test_fetch_records_follows_next_links_until_last_page():
    pages = [
        _page([{"_id": "a"}, {"_id": "b"}], "https://next/page2"),
        _page([{"_id": "c"}]),
    ]
    with patch.object(enedis_conso, "get_with_retry", side_effect=pages) as mock_get:
        records = enedis_conso.fetch_records(2023)

    assert [r["_id"] for r in records] == ["a", "b", "c"]
    first_call, second_call = mock_get.call_args_list
    assert first_call.args[0] == enedis_conso.ENEDIS_LINES_URL
    assert first_call.kwargs["params"]["annee_eq"] == 2023
    assert second_call.args[0] == "https://next/page2"
    assert second_call.kwargs["params"] is None


def test_fetch_records_returns_empty_list_when_no_data():
    with patch.object(enedis_conso, "get_with_retry", return_value=_page([])):
        assert enedis_conso.fetch_records(1999) == []


def test_load_to_bronze_targets_enedis_table_with_year_as_extracted_for():
    with patch.object(enedis_conso, "append_to_bronze", return_value=2) as mock_append:
        assert enedis_conso.load_to_bronze([{"a": 1}, {"a": 2}], 2023) == 2
    mock_append.assert_called_once_with(
        "raw_enedis_conso", [{"a": 1}, {"a": 2}], "j75xc8cglfk5cp800y9uwqx9", "2023"
    )
