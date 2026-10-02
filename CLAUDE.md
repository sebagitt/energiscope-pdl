# EnergiScope PDL — Contexte projet pour Claude Code

## Qui je suis
Analytics Engineer en formation (OpenClassrooms, finalisé août 2026).
Stack maîtrisée : SQL, Python, dbt Core, Snowflake, GitHub Actions, Power BI.
Ce projet est un portfolio personnel ciblant le marché nantais (Enedis, EDF, Lhyfe, Manitou, Groupe Atlantic, Région PDL).

## Ce que fait ce projet
Pipeline analytique sur la consommation électrique industrielle en Pays de la Loire.

**Question décisionnelle :**
> "La consommation électrique des sites industriels (C1-C4) en PDL varie-t-elle avec les
> indicateurs conjoncturels sectoriels (PMI, IPI) — et peut-on anticiper des tensions réseau 24h avant ?"

## Architecture médaillon (Bronze / Silver / Gold)

```
Sources externes                  Bronze (raw)          Silver (cleaned)       Gold (marts)
─────────────────                 ────────────          ────────────────       ────────────
RTE eco2mix API (30min)  ──────►  raw_rte_ecomix        stg_rte_ecomix        mart_production_regionale
Enedis Open Data API     ──────►  raw_enedis_conso       stg_enedis_conso      mart_conso_industrielle
INSEE IPI + emploi       ──────►  raw_insee_ipi          stg_insee_ipi         mart_correlation_conjoncture
Banque de France PMI     ──────►  raw_bdf_pmi            stg_bdf_pmi           mart_tension_reseau
```

## Stack technique

| Composant      | Outil                        | Statut        |
|----------------|------------------------------|---------------|
| Cloud DWH      | Databricks Free Edition      | À configurer  |
| Format stockage| Delta Lake (tables médaillon)| Via Databricks|
| Transform      | dbt Core + dbt-databricks    | Connu         |
| Orchestration  | Apache Airflow (Docker local)| Nouveau       |
| CI/CD          | GitHub Actions               | Connu         |
| Dashboard      | Power BI Desktop (JDBC)      | Connu         |
| Dev env        | VSCode + Claude Code         | Ce fichier    |
| Conteneur      | Docker Desktop (Airflow seul)| Nouveau       |

## Structure du repo

```
energiscope-pdl/
├── CLAUDE.md                    ← ce fichier
├── README.md
├── .github/
│   └── workflows/
│       ├── dbt_ci.yml           ← dbt test + slim CI
│       └── dbt_docs.yml         ← génération docs
├── ingestion/                   ← scripts Python d'ingestion
│   ├── src/
│   │   ├── rte_ecomix.py        ← API RTE eco2mix (30min)
│   │   ├── enedis_conso.py      ← API Enedis Open Data
│   │   ├── insee_ipi.py         ← INSEE IPI + emploi
│   │   └── bdf_pmi.py           ← Banque de France PMI
│   ├── tests/
│   └── requirements.txt
├── airflow/                     ← DAGs Airflow
│   ├── docker-compose.yml       ← setup officiel Airflow
│   ├── dags/
│   │   ├── dag_ingestion_rte.py ← toutes les 30min
│   │   ├── dag_ingestion_daily.py ← Enedis + INSEE + BdF quotidien
│   │   └── dag_dbt_run.py       ← déclenchement dbt via Databricks Jobs API
│   └── .env                     ← secrets locaux (gitignored)
├── dbt/                         ← projet dbt
│   ├── dbt_project.yml
│   ├── profiles.yml             ← connexion Databricks (gitignored, template fourni)
│   ├── models/
│   │   ├── staging/             ← stg_* : nettoyage source par source
│   │   ├── intermediate/        ← int_* : jointures cross-sources
│   │   └── marts/               ← mart_* : KPIs finaux pour Power BI
│   ├── tests/
│   ├── macros/
│   └── docs/
├── powerbi/
│   └── energiscope.pbix
└── docs/
    └── architecture.png
```

## Conventions de code

### Python (ingestion)
- `snake_case` pour tout
- Docstrings obligatoires sur chaque fonction
- Tests dans `tests/` avec pytest
- Gestion erreurs API : retry 3x avec backoff exponentiel
- Logs : logging stdlib (pas print)

### dbt
- Staging = 1 fichier source → 1 modèle `stg_<source>_<table>`
- Intermediate = jointures entre staging
- Marts = KPIs agronomés pour le dashboard
- Tests sur chaque modèle : `not_null`, `unique`, `accepted_values`
- Documentation YAML obligatoire sur chaque colonne des marts
- `{{ ref() }}` uniquement (jamais de hardcoded table names)

### Git
- Branches : `feature/<nom>`, `fix/<nom>`
- Commits : conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)
- PR avant merge sur main
- GitHub Actions doit passer avant merge

## Connexions & secrets

```bash
# Variables d'environnement (jamais dans le code)
DATABRICKS_HOST=         # https://<workspace>.azuredatabricks.net
DATABRICKS_TOKEN=        # Personal Access Token
DATABRICKS_HTTP_PATH=    # /sql/1.0/warehouses/<id>
RTE_API_KEY=             # ODRE API key (optionnel, accès libre)
AIRFLOW_FERNET_KEY=      # généré avec: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Sources de données

| Source | URL | Format | Fréquence |
|--------|-----|--------|-----------|
| RTE eco2mix | https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records | REST JSON | 30min |
| Enedis conso communes | https://data.enedis.fr/api/explore/v2.1/catalog/datasets/ | REST JSON | Mensuel |
| INSEE IPI | https://api.insee.fr/series/BDM/V1/data/ | REST JSON | Mensuel |
| Banque de France | https://webstat.banque-france.fr/api/ | REST JSON | Mensuel |

## Commandes fréquentes

```bash
# dbt
cd dbt/
dbt debug                          # vérifier connexion Databricks
dbt run --select staging           # run uniquement staging
dbt test                           # tous les tests
dbt docs generate && dbt docs serve # docs locale

# Airflow (depuis airflow/)
docker compose up -d               # démarrer Airflow
docker compose down                # arrêter
docker compose logs -f airflow-scheduler # logs scheduler

# Python ingestion
cd ingestion/
pip install -r requirements.txt
python src/rte_ecomix.py --date 2024-01-01  # test ingestion manuelle
pytest tests/ -v                   # tests unitaires

# GitHub Actions (déclenché sur push)
# Voir .github/workflows/dbt_ci.yml
```

## Tâches en cours (mettre à jour régulièrement)

- [ ] J1 : Setup Databricks Free Edition + LinkedIn verify
- [ ] J1 : Créer Personal Access Token Databricks
- [ ] J1 : Installer Docker Desktop + tester docker compose
- [ ] J2 : Configurer dbt-databricks (profiles.yml)
- [ ] J2 : Tester dbt debug → connexion OK
- [ ] J3 : Premier DAG Airflow fonctionnel
- [ ] J4 : Ingestion RTE eco2mix → Bronze Delta table
- [ ] J5 : Ingestion Enedis + INSEE + BdF → Bronze
- [ ] J6-J7 : Modèles dbt Staging (Silver)
- [ ] J8-J9 : Modèles dbt Marts (Gold) + KPIs corrélation
- [ ] J10-J11 : Pipeline orchestré bout-en-bout
- [ ] J12 : GitHub Actions CI/CD
- [ ] J13-J14 : Dashboard Power BI
- [ ] J15 : README + portfolio polish

## Ce que je ne veux pas

- Pas de hardcoded credentials dans le code
- Pas de `pd.read_csv()` pour les données qui viennent d'APIs (utiliser requests)
- Pas de notebooks Jupyter dans le repo final (prototypage OK, puis migration en scripts)
- Pas de `SELECT *` dans les modèles dbt marts
- Pas de commentaires évidents (`# incrémentation de i`)
