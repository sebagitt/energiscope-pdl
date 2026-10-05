"""Paramètres communs aux DAGs Energiscope : chemins dans l'image Airflow et arguments par défaut.

Les chemins sont ceux de l'image construite par `airflow/Dockerfile` : deux environnements virtuels
Linux (`/venvs/ingestion`, `/venvs/dbt`) et une copie du projet sous `/opt/energiscope`. Les variables
d'environnement du projet (DATABRICKS_*, BDF_API_KEY...) sont injectées dans les conteneurs par
`env_file` dans `docker-compose.yml`.

Ce module ne définit aucun DAG.
"""

from datetime import timedelta

import pendulum

INGESTION_PYTHON = "/venvs/ingestion/bin/python"
INGESTION_SRC = "/opt/energiscope/ingestion/src"

DBT_PYTHON = "/venvs/dbt/bin/python"
DBT_DIR = "/opt/energiscope/dbt"

# Les horaires des DAGs sont interprétés en heure de Paris (6h00 = 6h00 locales, été comme hiver)
START_DATE = pendulum.datetime(2026, 10, 1, tz="Europe/Paris")

DEFAULT_ARGS = {
    "owner": "energiscope",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def ingestion_command(script: str, args: str) -> str:
    """Commande shell qui lance un script d'ingestion avec le venv d'ingestion.

    À exécuter avec `cwd=INGESTION_SRC`.

    Args:
        script: Nom du script dans `ingestion/src/` (ex. `rte_ecomix.py`).
        args: Arguments de la ligne de commande, Jinja autorisé (ex. `--date {{ ds }}`).

    Returns:
        Commande à passer à `BashOperator(bash_command=...)`.
    """
    return f"{INGESTION_PYTHON} {INGESTION_SRC}/{script} {args}"


def dbt_command(args: str) -> str:
    """Commande shell qui lance dbt avec le venv dbt.

    À exécuter avec `cwd=DBT_DIR`.

    Args:
        args: Sous-commande et options dbt (ex. `run --select staging marts`).

    Returns:
        Commande à passer à `BashOperator(bash_command=...)`.
    """
    return f"{DBT_PYTHON} -m dbt.cli.main {args}"
