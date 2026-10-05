"""Transformations dbt à 7h00, après l'ingestion de 6h00 (couches Silver et Gold).

Trois tâches en séquence :

1. `dbt_run`  : construit les modèles `staging` (vues Silver) et `marts` (tables Gold).
2. `dbt_test` : lance les tests sur ces mêmes modèles.
3. `dbt_docs` : régénère la documentation du projet.

Si `dbt_run` échoue, `dbt_test` et `dbt_docs` ne tournent pas ; si `dbt_test` échoue, `dbt_docs`
non plus. dbt s'exécute avec le venv `/venvs/dbt` de l'image Airflow, depuis le projet `dbt/` monté en lecture
seule (les dossiers `target/`, `logs/` et les paquets sont redirigés vers des emplacements inscriptibles).
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from energiscope_common import DBT_DIR, DEFAULT_ARGS, START_DATE, dbt_command

with DAG(
    dag_id="energiscope_dbt",
    description="dbt run, test et docs sur les modèles staging et marts",
    doc_md=__doc__,
    schedule="0 7 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["energiscope", "silver", "gold"],
) as dag:
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=dbt_command("run --select staging marts"),
        cwd=DBT_DIR,
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=dbt_command("test --select staging marts"),
        cwd=DBT_DIR,
    )
    dbt_docs = BashOperator(
        task_id="dbt_docs",
        bash_command=dbt_command("docs generate"),
        cwd=DBT_DIR,
    )

    dbt_run >> dbt_test >> dbt_docs
