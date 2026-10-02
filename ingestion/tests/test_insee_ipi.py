from unittest.mock import MagicMock, patch

import pytest

import insee_ipi

SDMX_XML = """<?xml version='1.0' encoding='UTF-8'?>
<message:StructureSpecificData xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message">
<message:DataSet>
<Series IDBANK="010768265" FREQ="M" TITLE_FR="IPI CVS-CJO - Industrie manufacturière">
<Obs TIME_PERIOD="2026-07" OBS_VALUE="97.3" OBS_STATUS="A" OBS_QUAL="DEF"/>
<Obs TIME_PERIOD="2026-06" OBS_VALUE="96.1" OBS_STATUS="P"/>
</Series>
<Series IDBANK="010768135" FREQ="M" TITLE_FR="IPI CVS-CJO - Industrie automobile">
<Obs TIME_PERIOD="2026-07" OBS_VALUE="94.8" OBS_STATUS="A"/>
</Series>
</message:DataSet>
</message:StructureSpecificData>
""".encode("utf-8")


def test_parse_series_xml_flattens_one_row_per_series_and_period():
    records = insee_ipi.parse_series_xml(SDMX_XML)

    assert len(records) == 3
    assert records[0] == {
        "idbank": "010768265",
        "libelle_serie": "IPI CVS-CJO - Industrie manufacturière",
        "time_period": "2026-07",
        "obs_value": "97.3",
        "obs_status": "A",
    }
    assert records[1]["obs_status"] == "P"
    assert records[2]["idbank"] == "010768135"


def test_parse_series_xml_keeps_staging_contract_keys():
    expected = {"idbank", "libelle_serie", "time_period", "obs_value", "obs_status"}
    assert all(set(r) == expected for r in insee_ipi.parse_series_xml(SDMX_XML))


def test_parse_series_xml_returns_empty_list_without_series():
    assert insee_ipi.parse_series_xml(b"<root><other/></root>") == []


def test_fetch_records_joins_idbanks_and_passes_start_period():
    response = MagicMock(content=SDMX_XML)
    with patch.object(insee_ipi, "get_with_retry", return_value=response) as mock_get:
        records = insee_ipi.fetch_records(["111", "222"], start_period="2026-01")

    assert len(records) == 3
    assert mock_get.call_args.args[0].endswith("/SERIES_BDM/111+222")
    assert mock_get.call_args.kwargs["params"] == {"startPeriod": "2026-01"}


def test_fetch_records_omits_params_for_full_history():
    with patch.object(insee_ipi, "get_with_retry", return_value=MagicMock(content=SDMX_XML)) as mock_get:
        insee_ipi.fetch_records(["111"])
    assert mock_get.call_args.kwargs["params"] is None


def test_default_series_are_monthly_idbanks():
    assert all(idbank.isdigit() and len(idbank) == 9 for idbank in insee_ipi.DEFAULT_IDBANKS)


@pytest.mark.parametrize(("start", "expected"), [(None, "full"), ("2024-01", "2024-01")])
def test_load_to_bronze_traces_start_period(start, expected):
    with patch.object(insee_ipi, "append_to_bronze", return_value=1) as mock_append:
        insee_ipi.load_to_bronze([{"a": 1}], start)
    mock_append.assert_called_once_with("raw_insee_ipi", [{"a": 1}], "SERIES_BDM", expected)
