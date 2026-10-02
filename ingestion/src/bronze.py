"""Briques communes d'ingestion : appels HTTP résilients et chargement en Bronze (JSON brut).

Contrat Bronze partagé par toutes les sources : un enregistrement API par ligne, stocké tel quel
dans `payload`, avec `source_dataset`, `extracted_for` et `ingested_at`. Le typage et le
dédoublonnage sont faits en staging dbt.
"""

import json
import logging
import os
from datetime import datetime, timezone

import requests
from databricks import sql
from databricks.sql.client import Connection
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BRONZE_SCHEMA = "bronze"
INSERT_BATCH_SIZE = 50
REQUEST_TIMEOUT_S = 60


def is_retryable(exc: BaseException) -> bool:
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
    retry=retry_if_exception(is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def get_with_retry(url: str, params: dict | None = None, headers: dict | None = None) -> requests.Response:
    """Appel GET avec retry 3x et backoff exponentiel.

    Args:
        url: URL de l'endpoint.
        params: Paramètres de requête (None si déjà présents dans l'URL).
        headers: En-têtes HTTP.

    Returns:
        Réponse HTTP dont le statut est valide.
    """
    response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_S)
    response.raise_for_status()
    return response


def connect() -> Connection:
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


def append_to_bronze(table_name: str, records: list[dict], source_dataset: str, extracted_for: str) -> int:
    """Ajoute des enregistrements bruts dans une table Delta Bronze (append-only).

    Les ré-ingestions sont dédoublonnées dans le modèle staging (dernier `ingested_at` retenu),
    ce qui permet de rejouer une extraction sans risque.

    Args:
        table_name: Nom de la table Bronze (ex. `raw_enedis_conso`).
        records: Enregistrements renvoyés par l'API.
        source_dataset: Identifiant du jeu de données côté API.
        extracted_for: Paramètre d'extraction (année, période, jour…).

    Returns:
        Nombre de lignes insérées.
    """
    if not records:
        logger.warning("Aucun enregistrement à charger dans %s (%s, %s)", table_name, source_dataset, extracted_for)
        return 0

    catalog = os.getenv("DATABRICKS_CATALOG", "workspace")
    table = f"{catalog}.{BRONZE_SCHEMA}.{table_name}"
    ingested_at = datetime.now(timezone.utc)

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{BRONZE_SCHEMA}")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                source_dataset STRING COMMENT 'Identifiant du jeu de données côté API',
                extracted_for  STRING COMMENT 'Paramètre d extraction (jour, année ou période)',
                payload        STRING COMMENT 'Enregistrement JSON brut renvoyé par l API',
                ingested_at    TIMESTAMP COMMENT 'Horodatage UTC du chargement'
            ) USING DELTA
            """
        )

        for start in range(0, len(records), INSERT_BATCH_SIZE):
            batch = records[start : start + INSERT_BATCH_SIZE]
            params = {"ingested_at": ingested_at}
            for i, record in enumerate(batch):
                params[f"dataset_{i}"] = source_dataset
                params[f"extracted_for_{i}"] = extracted_for
                params[f"payload_{i}"] = json.dumps(record, ensure_ascii=False)
            cursor.execute(build_insert_statement(table, len(batch)), params)

    logger.info("%d lignes chargées dans %s", len(records), table)
    return len(records)
