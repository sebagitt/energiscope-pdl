"""Ingestion Banque de France (Webstat) vers la table Bronze `raw_bdf_pmi`.

Séries de l'enquête mensuelle de conjoncture, région Pays de la Loire (jeu `CONJ2`, industrie
manufacturière). Les observations sont dans le dataset restreint `observations` de l'API Explore
de Webstat, lisible uniquement avec une clé (`BDF_API_KEY`, en-tête `Authorization: Apikey`).
L'ancienne API `api.webstat.banque-france.fr` (X-IBM-Client-Id) refuse ce type de clé.
"""

import argparse
import logging
import os

from dotenv import load_dotenv

from bronze import append_to_bronze, get_with_retry, period_label, year_month

logger = logging.getLogger(__name__)

SOURCE_DATASET = "CONJ2"
BDF_EXPORT_URL = "https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/observations/exports/json"
BRONZE_TABLE = "raw_bdf_pmi"
SELECTED_FIELDS = "series_key,title_fr,time_period,obs_value,obs_status"
DEFAULT_SERIES_KEYS = (
    "CONJ2.M.R52.S.IN.000CZ.ICAIN000.10",  # Climat des affaires - CVS
    "CONJ2.M.R52.S.IN.000CZ.PRTEM100.10",  # Évolution de la production / M-1 - CVS
    "CONJ2.M.R52.S.IN.000CZ.CRTEM100.10",  # Évolution des commandes reçues / M-1 - CVS
    "CONJ2.M.R52.T.IN.000CZ.TUTSM000.10",  # Taux d'utilisation de la capacité de production - Tendance
)


def build_headers() -> dict:
    """Construit les en-têtes d'authentification Webstat.

    Returns:
        En-têtes HTTP avec la clé d'API.

    Raises:
        RuntimeError: si `BDF_API_KEY` n'est pas défini.
    """
    api_key = os.getenv("BDF_API_KEY")
    if not api_key:
        raise RuntimeError("BDF_API_KEY manquante : créer une clé sur Webstat (compte utilisateur)")
    return {"Authorization": f"Apikey {api_key}"}


def build_where_clause(series_keys: tuple[str, ...] | list[str], start_date: str | None, end_date: str | None) -> str:
    """Construit le filtre ODSQL sur les séries et la fenêtre de périodes.

    Args:
        series_keys: Clés de séries Webstat.
        start_date: Première période (YYYY-MM) ou None.
        end_date: Dernière période (YYYY-MM) ou None.

    Returns:
        Clause `where` ODSQL.
    """
    keys = ", ".join(f'"{key}"' for key in series_keys)
    clauses = [f"series_key IN ({keys})"]
    if start_date:
        clauses.append(f"time_period_start >= date'{start_date}-01'")
    if end_date:
        clauses.append(f"time_period_start <= date'{end_date}-01'")
    return " and ".join(clauses)


def fetch_records(
    series_keys: tuple[str, ...] | list[str] = DEFAULT_SERIES_KEYS,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Récupère les observations des séries Webstat demandées en un seul export.

    Args:
        series_keys: Clés de séries à extraire.
        start_date: Première période à renvoyer (YYYY-MM), début de série si None.
        end_date: Dernière période à renvoyer (YYYY-MM), fin de série si None.

    Returns:
        Liste d'observations `series_key`, `title_fr`, `time_period`, `obs_value`, `obs_status`.
    """
    params = {"where": build_where_clause(series_keys, start_date, end_date), "select": SELECTED_FIELDS}
    records = get_with_retry(BDF_EXPORT_URL, params=params, headers=build_headers()).json()
    logger.info("%d observations reçues de la Banque de France pour %d séries", len(records), len(series_keys))
    return records


def load_to_bronze(records: list[dict], start_date: str | None = None, end_date: str | None = None) -> int:
    """Ajoute les observations brutes dans la table Delta `raw_bdf_pmi`.

    Args:
        records: Observations renvoyées par `fetch_records`.
        start_date: Première période demandée, tracée dans `extracted_for`.
        end_date: Dernière période demandée, tracée dans `extracted_for`.

    Returns:
        Nombre de lignes insérées.
    """
    return append_to_bronze(BRONZE_TABLE, records, SOURCE_DATASET, period_label(start_date, end_date))


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Ingestion Banque de France conjoncture régionale PDL")
    parser.add_argument("--series", nargs="+", default=list(DEFAULT_SERIES_KEYS), help="Clés de séries Webstat")
    parser.add_argument("--start-date", type=year_month, help="Première période (YYYY-MM), début de série par défaut")
    parser.add_argument("--end-date", type=year_month, help="Dernière période (YYYY-MM), fin de série par défaut")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    load_dotenv()

    records = fetch_records(args.series, args.start_date, args.end_date)
    load_to_bronze(records, args.start_date, args.end_date)


if __name__ == "__main__":
    main()
