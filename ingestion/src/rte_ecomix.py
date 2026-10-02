"""Ingestion RTE eco2mix régional (Pays de la Loire) vers la table Bronze `raw_rte_ecomix`.

Deux jeux ODRE au schéma quasi identique :
- `eco2mix-regional-tr` : temps réel, pas 15 min, ~3 derniers mois seulement ;
- `eco2mix-regional-cons-def` : consolidé / définitif, pas 30 min, depuis 2013.

Chaque enregistrement est stocké tel quel (JSON brut) : l'API renvoie des types instables
(`"ND"`, nombres sérialisés en chaîne), le typage est fait dans `stg_rte_ecomix`.
"""

import argparse
import json
import logging
import os
from datetime import date, datetime, timezone

import requests
from databricks import sql
from databricks.sql.client import Connection
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

ODRE_BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets"
DATASETS = {
    "tr": "eco2mix-regional-tr",
    "cons-def": "eco2mix-regional-cons-def",
}
REGION_CODE_PDL = "52"
BRONZE_SCHEMA = "bronze"
BRONZE_TABLE = "raw_rte_ecomix"
INSERT_BATCH_SIZE = 100
REQUEST_TIMEOUT_S = 60


def _is_retryable(exc: BaseException) -> bool:
    """Indique si une erreur HTTP mérite un nouvel essai (réseau, 429, 5xx).

    Args:
        exc: Exception levée par `requests`.

    Returns:
        True pour les erreurs transitoires, False pour les erreurs client (4xx hors 429).
    """
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _get_json(url: str, params: dict, headers: dict) -> list[dict]:
    """Appel GET avec retry 3x et backoff exponentiel.

    Args:
        url: URL de l'endpoint.
        params: Paramètres de requête.
        headers: En-têtes HTTP.

    Returns:
        Corps de la réponse décodé.
    """
    response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    return response.json()


def build_where_clause(day: date, region_code: str = REGION_CODE_PDL) -> str:
    """Construit le filtre ODSQL pour une région et un jour (heure locale).

    `date` est un champ texte côté ODRE : la comparaison se fait sur la chaîne ISO.

    Args:
        day: Jour à extraire.
        region_code: Code INSEE de la région.

    Returns:
        Clause `where` ODSQL.
    """
    return f"code_insee_region = '{region_code}' and date = '{day.isoformat()}'"


def fetch_records(day: date, dataset: str = DATASETS["tr"]) -> list[dict]:
    """Récupère les enregistrements eco2mix d'une journée pour les Pays de la Loire.

    Utilise l'endpoint `exports/json`, sans pagination ni plafond de 10 000 lignes.

    Args:
        day: Jour à extraire (heure locale).
        dataset: Identifiant du jeu ODRE.

    Returns:
        Liste des enregistrements JSON bruts.
    """
    headers = {}
    api_key = os.getenv("RTE_API_KEY")
    if api_key:
        headers["Authorization"] = f"Apikey {api_key}"

    records = _get_json(
        f"{ODRE_BASE_URL}/{dataset}/exports/json",
        params={"where": build_where_clause(day)},
        headers=headers,
    )
    logger.info("%d enregistrements reçus de %s pour %s", len(records), dataset, day)
    return records


def _connect() -> Connection:
    """Ouvre une connexion Databricks SQL à partir des variables d'environnement.

    Returns:
        Connexion databricks-sql-connector.
    """
    return sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/"),
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def build_insert_statement(table: str, n_rows: int) -> str:
    """Génère un INSERT multi-lignes à paramètres nommés.

    Args:
        table: Nom complet de la table cible.
        n_rows: Nombre de lignes du lot.

    Returns:
        Requête SQL paramétrée.
    """
    values = ", ".join(
        f"(:dataset_{i}, :extracted_for_{i}, :payload_{i}, :ingested_at)" for i in range(n_rows)
    )
    return f"INSERT INTO {table} (source_dataset, extracted_for, payload, ingested_at) VALUES {values}"


def load_to_bronze(records: list[dict], dataset: str, day: date) -> int:
    """Ajoute les enregistrements bruts dans la table Delta Bronze (append-only).

    Les ré-ingestions d'une même journée sont dédoublonnées dans `stg_rte_ecomix`
    (dernier `ingested_at` retenu), ce qui permet de rejouer sans risque.

    Args:
        records: Enregistrements renvoyés par `fetch_records`.
        dataset: Identifiant du jeu ODRE d'origine.
        day: Jour extrait.

    Returns:
        Nombre de lignes insérées.
    """
    if not records:
        logger.warning("Aucun enregistrement à charger pour %s (%s)", day, dataset)
        return 0

    catalog = os.getenv("DATABRICKS_CATALOG", "workspace")
    table = f"{catalog}.{BRONZE_SCHEMA}.{BRONZE_TABLE}"
    ingested_at = datetime.now(timezone.utc)

    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{BRONZE_SCHEMA}")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                source_dataset STRING COMMENT 'Identifiant du jeu ODRE',
                extracted_for  STRING COMMENT 'Jour extrait (YYYY-MM-DD, heure locale)',
                payload        STRING COMMENT 'Enregistrement JSON brut renvoyé par l API',
                ingested_at    TIMESTAMP COMMENT 'Horodatage UTC du chargement'
            ) USING DELTA
            """
        )

        for start in range(0, len(records), INSERT_BATCH_SIZE):
            batch = records[start : start + INSERT_BATCH_SIZE]
            params = {"ingested_at": ingested_at}
            for i, record in enumerate(batch):
                params[f"dataset_{i}"] = dataset
                params[f"extracted_for_{i}"] = day.isoformat()
                params[f"payload_{i}"] = json.dumps(record, ensure_ascii=False)
            cursor.execute(build_insert_statement(table, len(batch)), params)

    logger.info("%d lignes chargées dans %s", len(records), table)
    return len(records)


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(description="Ingestion RTE eco2mix régional (PDL)")
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Jour à ingérer (YYYY-MM-DD)")
    parser.add_argument(
        "--dataset",
        choices=DATASETS,
        default="tr",
        help="tr = temps réel (~3 derniers mois), cons-def = historique consolidé/définitif",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    load_dotenv()

    dataset = DATASETS[args.dataset]
    records = fetch_records(args.date, dataset)
    load_to_bronze(records, dataset, args.date)


if __name__ == "__main__":
    main()
