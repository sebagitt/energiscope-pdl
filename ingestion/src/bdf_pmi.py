"""Ingestion Banque de France (Webstat) vers la table Bronze `raw_bdf_pmi`.

Séries de l'enquête mensuelle de conjoncture, région Pays de la Loire (jeu `CONJ2`, industrie
manufacturière, CVS). Les observations ne sont servies que par l'API Webstat authentifiée : une
clé (`BDF_API_KEY`) créée sur le portail développeur Webstat est obligatoire.

ATTENTION : le format de réponse attendu (SDMX-JSON) et le chemin d'appel n'ont pas pu être
vérifiés contre l'API réelle (clé indisponible lors de l'écriture). `parse_observations` échoue
bruyamment si la structure diffère, plutôt que de charger zéro ligne en silence.
"""

import argparse
import logging
import os

from dotenv import load_dotenv

from bronze import append_to_bronze, get_with_retry

logger = logging.getLogger(__name__)

SOURCE_DATASET = "CONJ2"
BDF_BASE_URL = "https://api.webstat.banque-france.fr/webstat-fr/v1"
BRONZE_TABLE = "raw_bdf_pmi"
DEFAULT_SERIES = {
    "CONJ2.M.R52.S.IN.000CZ.ICAIN000.10": "Pays de la Loire - Industrie manufacturière - Indicateur mensuel du climat des affaires - CVS",
    "CONJ2.M.R52.S.IN.000CZ.PRTEM100.10": "Pays de la Loire - Industrie manufacturière - Évolution de la production / M-1 - CVS",
    "CONJ2.M.R52.S.IN.000CZ.CRTEM100.10": "Pays de la Loire - Industrie manufacturière - Évolution des commandes reçues / M-1 - CVS",
    "CONJ2.M.R52.T.IN.000CZ.TUTSM000.10": "Pays de la Loire - Industrie manufacturière - Taux moyen d'utilisation de la capacité de production - Tendance",
}


def build_headers() -> dict:
    """Construit les en-têtes d'authentification Webstat.

    Returns:
        En-têtes HTTP avec l'identifiant client.

    Raises:
        RuntimeError: si `BDF_API_KEY` n'est pas défini.
    """
    api_key = os.getenv("BDF_API_KEY")
    if not api_key:
        raise RuntimeError("BDF_API_KEY manquante : créer une clé sur le portail développeur Webstat")
    return {"X-IBM-Client-Id": api_key, "Accept": "application/json"}


def parse_observations(payload: dict, series_key: str, title_fr: str) -> list[dict]:
    """Aplati une réponse SDMX-JSON en une ligne par période.

    Les valeurs restent telles que renvoyées par l'API.

    Args:
        payload: Réponse JSON décodée.
        series_key: Clé de la série demandée.
        title_fr: Libellé français de la série.

    Returns:
        Liste de dictionnaires `series_key`, `title_fr`, `time_period`, `obs_value`.

    Raises:
        ValueError: si la réponse n'a pas la structure SDMX-JSON attendue.
    """
    try:
        periods = payload["structure"]["dimensions"]["observation"][0]["values"]
        series_list = payload["dataSets"][0]["series"].values()
        return [
            {
                "series_key": series_key,
                "title_fr": title_fr,
                "time_period": periods[int(index)]["id"],
                "obs_value": observation[0],
            }
            for series in series_list
            for index, observation in series["observations"].items()
        ]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Structure de réponse Webstat inattendue pour {series_key}: {exc!r}") from exc


def fetch_records(series: dict[str, str] | None = None, start_period: str | None = None) -> list[dict]:
    """Récupère les observations des séries Webstat demandées, une requête par série.

    Args:
        series: Association clé de série → libellé (séries par défaut si None).
        start_period: Première période à renvoyer (YYYY-MM), toute la série si None.

    Returns:
        Liste des observations aplaties.
    """
    headers = build_headers()
    params = {"format": "json"}
    if start_period:
        params["startPeriod"] = start_period

    records: list[dict] = []
    for series_key, title_fr in (series or DEFAULT_SERIES).items():
        dataset, _, key_tail = series_key.partition(".")
        payload = get_with_retry(f"{BDF_BASE_URL}/data/{dataset}/{key_tail}", params=params, headers=headers).json()
        records.extend(parse_observations(payload, series_key, title_fr))

    logger.info("%d observations reçues de la Banque de France", len(records))
    return records


def load_to_bronze(records: list[dict], start_period: str | None = None) -> int:
    """Ajoute les observations brutes dans la table Delta `raw_bdf_pmi`.

    Args:
        records: Observations renvoyées par `fetch_records`.
        start_period: Période de départ demandée, tracée dans `extracted_for` ("full" si absente).

    Returns:
        Nombre de lignes insérées.
    """
    return append_to_bronze(BRONZE_TABLE, records, SOURCE_DATASET, start_period or "full")


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Ingestion Banque de France conjoncture régionale PDL")
    parser.add_argument("--start-period", help="Première période (YYYY-MM), toute la série par défaut")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    load_dotenv()

    records = fetch_records(start_period=args.start_period)
    load_to_bronze(records, args.start_period)


if __name__ == "__main__":
    main()
