# Image Airflow du projet Energiscope : Airflow 2.9.3 + deux environnements virtuels Linux.
#
# Le contexte de build est la RACINE du projet (voir docker-compose.yml : context: ..), car l'image
# embarque ingestion/ et dbt/. Les secrets n'entrent jamais dans l'image (voir .dockerignore) :
# ils arrivent à l'exécution par `env_file` dans docker-compose.yml.
FROM apache/airflow:2.9.3

USER root
RUN mkdir -p /venvs /opt/energiscope /tmp/dbt \
    && chown -R airflow:0 /venvs /opt/energiscope /tmp/dbt

USER airflow

# Venv d'ingestion (Python + dépendances des scripts)
COPY --chown=airflow:0 ingestion/requirements.txt /tmp/ingestion-requirements.txt
RUN python -m venv /venvs/ingestion \
    && /venvs/ingestion/bin/pip install --no-cache-dir --upgrade pip \
    && /venvs/ingestion/bin/pip install --no-cache-dir -r /tmp/ingestion-requirements.txt

# Venv dbt, aux versions utilisées en développement
RUN python -m venv /venvs/dbt \
    && /venvs/dbt/bin/pip install --no-cache-dir --upgrade pip \
    && /venvs/dbt/bin/pip install --no-cache-dir "dbt-core==1.12.3" "dbt-databricks==1.12.5"

# Code du projet. Copie de secours : docker-compose.yml monte ces dossiers en lecture seule par-dessus
# pour que les modifications soient prises en compte sans reconstruire l'image.
COPY --chown=airflow:0 ingestion/src /opt/energiscope/ingestion/src
COPY --chown=airflow:0 dbt /opt/energiscope/dbt

# Profil dbt de l'image : sans secret, il lit la connexion dans les variables d'environnement
RUN mkdir -p /opt/energiscope/profiles \
    && cp /opt/energiscope/dbt/profiles.yml.example /opt/energiscope/profiles/profiles.yml

# dbt écrit dans son projet (target/, logs/, dbt_packages/), or le projet est monté en lecture seule :
# ces trois dossiers sont redirigés vers des emplacements inscriptibles (DBT_PACKAGES_DIR est lu par
# `packages-install-path` dans dbt/dbt_project.yml).
ENV DBT_PROFILES_DIR=/opt/energiscope/profiles \
    DBT_TARGET_PATH=/tmp/dbt/target \
    DBT_LOG_PATH=/tmp/dbt/logs \
    DBT_PACKAGES_DIR=/opt/energiscope/dbt_packages \
    PYTHONDONTWRITEBYTECODE=1

# Paquets dbt (dbt_utils) installés une fois pour toutes dans l'image. La connexion n'est pas utilisée
# par `dbt deps` ; les variables factices ne servent qu'à résoudre le profil.
RUN DATABRICKS_HOST=build.invalid DATABRICKS_HTTP_PATH=build DATABRICKS_TOKEN=build \
    /venvs/dbt/bin/dbt deps --project-dir /opt/energiscope/dbt \
    && ls /opt/energiscope/dbt_packages
