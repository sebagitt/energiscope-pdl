"""Ingestion RTE eco2mix en quasi temps réel, toutes les 15 minutes (couche Bronze).

Une seule tâche : `ingestion_rte` lance `rte_ecomix.py --date {{ ds }} --dataset tr --since 120`, qui charge
dans `workspace.bronze.raw_rte_ecomix` les créneaux du jeu temps réel (pas de 15 min) des 2 dernières
heures, soit au plus 8 lignes par exécution (environ 770 par jour, contre 9 200 en rechargeant la journée).

Pourquoi 2 heures : RTE publie avec un retard variable (de 30 minutes à une heure environ), et les créneaux
récents sont d'abord publiés sans valeur. La fenêtre recouvre donc plusieurs exécutions, pour que chaque créneau soit chargé
une fois renseigné. Les doublons sont éliminés dans `stg_rte_ecomix` (dernière valeur renseignée retenue).
Si l'ordonnanceur est arrêté plus de 2 heures, les créneaux manqués se rattrapent avec un backfill
(`rte_ecomix.py --date AAAA-MM-JJ`).

`--date` ne sert ici que d'étiquette de chargement (`extracted_for`) : la fenêtre est relative à l'instant
présent, en UTC, pour qu'aucun créneau ne tombe entre deux jours.

Une seule exécution à la fois (`max_active_runs=1`) pour éviter des chargements concurrents.
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from energiscope_common import DEFAULT_ARGS, INGESTION_SRC, START_DATE, ingestion_command

with DAG(
    dag_id="energiscope_rte_realtime",
    description="Ingestion RTE eco2mix (temps réel) vers Bronze, toutes les 15 minutes",
    doc_md=__doc__,
    schedule="*/15 * * * *",
    start_date=START_DATE,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["energiscope", "bronze"],
) as dag:
    ingestion_rte = BashOperator(
        task_id="ingestion_rte",
        bash_command=ingestion_command("rte_ecomix.py", "--date {{ ds }} --dataset tr --since 120"),
        cwd=INGESTION_SRC,
    )
