"""Ingestion quotidienne Enedis, INSEE et Banque de France, à 6h00 (couche Bronze).

Trois tâches en séquence : si l'une échoue, les suivantes ne tournent pas.

1. `ingest_enedis` : consommation annuelle par commune, pour l'année précédant la date logique, plafonnée
   à 2024 (dernière année publiée). Tant que 2025 n'est pas disponible, la même année est donc rechargée
   chaque jour ; les doublons sont éliminés dans `stg_enedis_conso`.
2. `ingest_insee`  : IPI mensuel, des 3 derniers mois et du mois courant (délai de publication de l'INSEE).
3. `ingest_bdf`    : conjoncture régionale de la Banque de France, même fenêtre (mêmes raisons).

Les mois déjà chargés sont rechargés à chaque passage, ce qui récupère aussi les révisions des séries.

Les tables Bronze sont alimentées en ajout seul : les doublons sont éliminés dans les modèles
staging dbt (dernier chargement retenu).
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from energiscope_common import DEFAULT_ARGS, INGESTION_SRC, START_DATE, ingestion_command

# Du mois situé 3 mois avant la date logique jusqu'au mois courant : l'INSEE et la Banque de France publient
# avec 1 à 3 mois de retard (au 5 octobre, derniers mois disponibles : juillet et août), et révisent les
# derniers mois publiés. Une fenêtre sur le seul mois courant ne chargeait jamais rien.
PERIOD = "--start-date {{ data_interval_start.subtract(months=3).strftime('%Y-%m') }} --end-date {{ ds[:7] }}"
# Jinja n'a pas de fonction int() : le filtre `| int` convertit l'année
ENEDIS_YEAR = "--year {{ [(macros.ds_format(ds, '%Y-%m-%d', '%Y') | int) - 1, 2024] | min }}"

with DAG(
    dag_id="energiscope_ingestion_daily",
    description="Ingestion quotidienne Enedis, INSEE et Banque de France vers Bronze",
    doc_md=__doc__,
    schedule="0 6 * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["energiscope", "bronze"],
) as dag:
    ingest_enedis = BashOperator(
        task_id="ingest_enedis",
        bash_command=ingestion_command("enedis_conso.py", ENEDIS_YEAR),
        cwd=INGESTION_SRC,
    )
    ingest_insee = BashOperator(
        task_id="ingest_insee",
        bash_command=ingestion_command("insee_ipi.py", PERIOD),
        cwd=INGESTION_SRC,
    )
    ingest_bdf = BashOperator(
        task_id="ingest_bdf",
        bash_command=ingestion_command("bdf_pmi.py", PERIOD),
        cwd=INGESTION_SRC,
    )

    ingest_enedis >> ingest_insee >> ingest_bdf
