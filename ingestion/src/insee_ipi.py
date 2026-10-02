"""Ingestion INSEE (BDM) vers la table Bronze `raw_insee_ipi`.

L'API BDM renvoie du SDMX XML (sans authentification). Chaque observation est aplatie en une
ligne série × période. Les séries par défaut sont des indices IPI mensuels CVS-CJO (base 100 en
2021) au niveau France entière : l'INSEE ne publie pas d'IPI régional dans la BDM.
"""

import argparse
import logging
import xml.etree.ElementTree as ET

from dotenv import load_dotenv

from bronze import append_to_bronze, get_with_retry

logger = logging.getLogger(__name__)

SOURCE_DATASET = "SERIES_BDM"
INSEE_DATA_URL = f"https://api.insee.fr/series/BDM/V1/data/{SOURCE_DATASET}"
BRONZE_TABLE = "raw_insee_ipi"
DEFAULT_IDBANKS = (
    "010768265",  # IPI CVS-CJO - Industrie manufacturière (section C)
    "010768135",  # IPI CVS-CJO - Industrie automobile (division 29)
    "010768273",  # IPI CVS-CJO - Fabrication de matériels de transport (A17 C4)
)


def parse_series_xml(content: bytes) -> list[dict]:
    """Aplati une réponse SDMX XML de la BDM en une ligne par série × période.

    Les valeurs restent en texte, comme renvoyées par l'API.

    Args:
        content: Corps de la réponse HTTP (XML).

    Returns:
        Liste de dictionnaires `idbank`, `libelle_serie`, `time_period`, `obs_value`, `obs_status`.
    """
    records: list[dict] = []
    for series in ET.fromstring(content).iter():
        if series.tag.rsplit("}", 1)[-1] != "Series":
            continue
        for obs in series:
            records.append(
                {
                    "idbank": series.get("IDBANK"),
                    "libelle_serie": series.get("TITLE_FR"),
                    "time_period": obs.get("TIME_PERIOD"),
                    "obs_value": obs.get("OBS_VALUE"),
                    "obs_status": obs.get("OBS_STATUS"),
                }
            )
    return records


def fetch_records(idbanks: tuple[str, ...] | list[str] = DEFAULT_IDBANKS, start_period: str | None = None) -> list[dict]:
    """Récupère les observations de séries INSEE BDM.

    Args:
        idbanks: Identifiants de séries (idbank) à extraire.
        start_period: Première période à renvoyer (YYYY-MM), toute la série si None.

    Returns:
        Liste des observations aplaties.
    """
    params = {"startPeriod": start_period} if start_period else None
    response = get_with_retry(f"{INSEE_DATA_URL}/{'+'.join(idbanks)}", params=params)
    records = parse_series_xml(response.content)
    logger.info("%d observations reçues de l'INSEE pour %d séries", len(records), len(idbanks))
    return records


def load_to_bronze(records: list[dict], start_period: str | None = None) -> int:
    """Ajoute les observations brutes dans la table Delta `raw_insee_ipi`.

    Args:
        records: Observations renvoyées par `fetch_records`.
        start_period: Période de départ demandée, tracée dans `extracted_for` ("full" si absente).

    Returns:
        Nombre de lignes insérées.
    """
    return append_to_bronze(BRONZE_TABLE, records, SOURCE_DATASET, start_period or "full")


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Ingestion INSEE IPI")
    parser.add_argument("--idbank", nargs="+", default=list(DEFAULT_IDBANKS), help="Identifiants de séries BDM")
    parser.add_argument("--start-period", help="Première période (YYYY-MM), toute la série par défaut")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    load_dotenv()

    records = fetch_records(args.idbank, args.start_period)
    load_to_bronze(records, args.start_period)


if __name__ == "__main__":
    main()
