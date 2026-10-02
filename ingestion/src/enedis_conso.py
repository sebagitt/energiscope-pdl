"""Ingestion Enedis Open Data vers la table Bronze `raw_enedis_conso`.

Jeu `j75xc8cglfk5cp800y9uwqx9` : consommation et thermosensibilité annuelles d'électricité par
secteur d'activité à la maille commune (2011-2024). Une ligne par année × commune × grand
secteur × secteur NAF2. L'API est une instance data-fair, paginée par curseur (`next`).
"""

import argparse
import logging

from dotenv import load_dotenv

from bronze import append_to_bronze, get_with_retry

logger = logging.getLogger(__name__)

SOURCE_DATASET = "j75xc8cglfk5cp800y9uwqx9"
ENEDIS_LINES_URL = f"https://opendata.enedis.fr/data-fair/api/v1/datasets/{SOURCE_DATASET}/lines"
REGION_CODE_PDL = "52"
BRONZE_TABLE = "raw_enedis_conso"
PAGE_SIZE = 10000


def build_params(annee: int, region_code: str = REGION_CODE_PDL) -> dict:
    """Construit les paramètres de la première page (filtres région et année).

    Args:
        annee: Année de consommation.
        region_code: Code INSEE de la région.

    Returns:
        Paramètres de requête data-fair.
    """
    return {"size": PAGE_SIZE, "code_region_eq": region_code, "annee_eq": annee}


def fetch_records(annee: int, region_code: str = REGION_CODE_PDL) -> list[dict]:
    """Récupère toutes les lignes d'une année pour une région, en suivant la pagination.

    Args:
        annee: Année de consommation (2011 à 2024).
        region_code: Code INSEE de la région.

    Returns:
        Liste des enregistrements JSON bruts.
    """
    records: list[dict] = []
    url = ENEDIS_LINES_URL
    params: dict | None = build_params(annee, region_code)

    while url:
        payload = get_with_retry(url, params=params).json()
        records.extend(payload["results"])
        url = payload.get("next")
        params = None  # le lien `next` embarque déjà tous les paramètres

    logger.info("%d enregistrements reçus d'Enedis pour %s (région %s)", len(records), annee, region_code)
    return records


def load_to_bronze(records: list[dict], annee: int) -> int:
    """Ajoute les enregistrements bruts dans la table Delta `raw_enedis_conso`.

    Args:
        records: Enregistrements renvoyés par `fetch_records`.
        annee: Année extraite.

    Returns:
        Nombre de lignes insérées.
    """
    return append_to_bronze(BRONZE_TABLE, records, SOURCE_DATASET, str(annee))


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Ingestion Enedis consommation par commune et secteur")
    parser.add_argument("--annee", required=True, type=int, nargs="+", help="Une ou plusieurs années (2011-2024)")
    parser.add_argument("--region", default=REGION_CODE_PDL, help="Code INSEE région (52 = Pays de la Loire)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    load_dotenv()

    for annee in args.annee:
        load_to_bronze(fetch_records(annee, args.region), annee)


if __name__ == "__main__":
    main()
