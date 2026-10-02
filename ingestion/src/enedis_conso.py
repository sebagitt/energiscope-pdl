"""Ingestion Enedis Open Data vers la table Bronze `raw_enedis_conso`."""

import argparse
import logging

logger = logging.getLogger(__name__)


def fetch_records(date: str) -> list[dict]:
    """Récupère les enregistrements bruts depuis l'API Enedis Open Data pour une date donnée.

    Args:
        date: Date au format YYYY-MM-DD.

    Returns:
        Liste des enregistrements JSON bruts.
    """
    raise NotImplementedError


def load_to_bronze(records: list[dict]) -> None:
    """Écrit les enregistrements bruts dans la table Delta `raw_enedis_conso`.

    Args:
        records: Enregistrements renvoyés par `fetch_records`.
    """
    raise NotImplementedError


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Ingestion Enedis Open Data")
    parser.add_argument("--date", required=True, help="Date à ingérer (YYYY-MM-DD)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    records = fetch_records(args.date)
    load_to_bronze(records)
    logger.info("%d enregistrements ingérés pour %s", len(records), args.date)


if __name__ == "__main__":
    main()
