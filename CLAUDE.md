# EnergiScope PDL — Contexte projet pour Claude Code

## Qui je suis
Analytics Engineer en formation (OpenClassrooms, finalisé août 2026).
Stack maîtrisée : SQL, Python, dbt Core, Snowflake, GitHub Actions, Power BI.
Ce projet est un portfolio personnel ciblant le marché nantais (Enedis, EDF, Lhyfe, Manitou, Groupe Atlantic, Région PDL).

## Ce que fait ce projet
Pipeline analytique sur la consommation électrique industrielle en Pays de la Loire.

**Question décisionnelle :**
> "La consommation électrique des sites industriels (C1-C4) en PDL varie-t-elle avec les
> indicateurs conjoncturels sectoriels (conjoncture régionale Banque de France, IPI) — et peut-on anticiper des tensions réseau 24h avant ?"

## Architecture médaillon (Bronze / Silver / Gold)

```
Sources externes                  Bronze (raw)          Silver (cleaned)       Gold (marts)
─────────────────                 ────────────          ────────────────       ────────────
RTE eco2mix API (15min)  ──────►  raw_rte_ecomix        stg_rte_ecomix        mart_production_regionale
                                                         stg_rte_mensuel       mart_correlation_conjoncture
Enedis Open Data (annuel)──────►  raw_enedis_conso       stg_enedis_conso      mart_conso_industrielle
INSEE IPI + emploi       ──────►  raw_insee_ipi          stg_insee_ipi         mart_correlation_conjoncture
BdF conjoncture PDL      ──────►  raw_bdf_pmi            stg_bdf_pmi           mart_correlation_conjoncture
                                                                               mart_tension_reseau (stg_rte_ecomix)
```

`raw_rte_ecomix` alimente deux modèles staging : `stg_rte_ecomix` (grain fin, 15/30 min) et
`stg_rte_mensuel` (agrégation mensuelle du seul jeu `cons-def`).

Toutes les tables Bronze partagent le même schéma JSON brut (4 colonnes) :

| Colonne          | Type      | Contenu                                              |
|------------------|-----------|------------------------------------------------------|
| `source_dataset` | STRING    | Identifiant du jeu côté API                          |
| `extracted_for`  | STRING    | Paramètre d'extraction (jour ou période demandée)    |
| `payload`        | STRING    | Enregistrement JSON brut renvoyé par l'API           |
| `ingested_at`    | TIMESTAMP | Horodatage UTC du chargement                         |

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
│   │   ├── rte_ecomix.py        ← API RTE eco2mix (15min, --dataset cons-def pour l'historique)
│   │   ├── enedis_conso.py      ← API Enedis Open Data (annuel)
│   │   ├── insee_ipi.py         ← INSEE IPI + emploi
│   │   └── bdf_pmi.py           ← Banque de France conjoncture régionale PDL
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

## Environnements virtuels

Deux venvs séparés, ignorés par git (`.venv/` dans `.gitignore`). Ne jamais les mélanger.

| Tâche                                              | Venv à activer   | Dossier de travail | Contenu clé                                                          |
|----------------------------------------------------|------------------|--------------------|----------------------------------------------------------------------|
| dbt : `debug`, `compile`, `run`, `test`, `docs`    | `.venv` (racine) | `dbt/`             | dbt-core, dbt-databricks                                             |
| Ingestion : scripts `src/*.py` et `pytest`         | `ingestion/.venv`| `ingestion/`       | requests, tenacity, python-dotenv, databricks-sql-connector, pytest  |
| Airflow                                            | aucun (Docker)   | `airflow/`         | image officielle via `docker compose`                                |

```bash
# Activation (Windows)
source .venv/Scripts/activate              # Git Bash : venv racine (dbt)
source ingestion/.venv/Scripts/activate    # Git Bash : venv ingestion
.\.venv\Scripts\Activate.ps1               # PowerShell : venv racine (dbt)
.\ingestion\.venv\Scripts\Activate.ps1     # PowerShell : venv ingestion
deactivate                                 # avant de changer de venv

# Sans activer : appeler directement l'exécutable du bon venv
.venv/Scripts/dbt run --select staging
ingestion/.venv/Scripts/python -m pytest ingestion/tests -v
```

- `pytest` et `tenacity` n'existent que dans `ingestion/.venv` ; `dbt` n'existe que dans `.venv`. Une commande qui échoue avec « module introuvable » signifie presque toujours le mauvais venv.
- Dépendance d'ingestion : l'ajouter à `ingestion/requirements.txt`, puis `pip install -r` dans `ingestion/.venv`.
- Paquets dbt (ex. `dbt_utils`) : `dbt/packages.yml` puis `dbt deps`, pas `pip`.
- Le venv racine n'a pas de fichier de dépendances : les versions de dbt ne sont pas épinglées dans le dépôt.
- Recréation : `python -m venv .venv && .venv/Scripts/python -m pip install dbt-databricks` (idem dans `ingestion/` avec `-r requirements.txt`).

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
DATABRICKS_CATALOG=      # catalogue Unity Catalog cible (défaut : workspace)
RTE_API_KEY=             # ODRE API key (optionnel, accès libre)
BDF_API_KEY=             # clé Webstat Banque de France (obligatoire pour bdf_pmi.py)
AIRFLOW_FERNET_KEY=      # généré avec: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Sources de données

| Source | URL | Format | Fréquence |
|--------|-----|--------|-----------|
| RTE eco2mix temps réel | https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/exports/json | REST JSON | 15min (~3 derniers mois) |
| RTE eco2mix historique | https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-cons-def/exports/json | REST JSON | 30min (depuis 2013) |
| Enedis conso communes | https://opendata.enedis.fr/data-fair/api/v1/datasets/j75xc8cglfk5cp800y9uwqx9/lines | REST JSON (data-fair, pagination `next`) | Annuel (année × commune × grand secteur × NAF2), 2011-2024 |
| INSEE IPI | https://api.insee.fr/series/BDM/V1/data/SERIES_BDM/ | SDMX XML, sans authentification | Mensuel (IPI France entière, pas de série régionale) |
| Banque de France conjoncture PDL | https://api.webstat.banque-france.fr/webstat-fr/v1/data/CONJ2/ (séries `conj2-m-r52-*`) | JSON, clé `BDF_API_KEY` obligatoire | Mensuel |

Webstat n'expose pas de valeurs via son API publique (`explore/v2.1`) : seul le catalogue des séries y est lisible. Les observations passent par l'API authentifiée.

## Décisions architecturales

### Bronze en JSON brut (schéma commun à 4 colonnes)
- **Choix :** chaque enregistrement API est stocké tel quel dans `payload` (STRING), avec `source_dataset`, `extracted_for` et `ingested_at`. Les tables sont alimentées en ajout seul (append-only).
- **Pourquoi :** les API renvoient des types instables (ex. RTE : `"ND"`, nombres sérialisés en chaîne). Typer à l'ingestion ferait échouer le chargement ou perdrait de la donnée.
- **Conséquences :** le typage se fait en staging (`payload:champ` + `try_cast`, une valeur invalide devient `NULL`). Le dédoublonnage aussi (`qualify row_number()`, dernier `ingested_at` retenu), ce qui permet de rejouer une ingestion sans créer de doublons.

### RTE : granularité 15 min et deux jeux de données
- **Constat :** `eco2mix-regional-tr` est au pas de 15 min et ne couvre que les ~3 derniers mois. L'historique depuis 2013 est dans `eco2mix-regional-cons-def`, au pas de 30 min.
- **Choix :** `rte_ecomix.py` prend une option `--dataset` (`tr` par défaut, `cons-def` pour le backfill). `stg_rte_ecomix` fusionne les deux en gardant la donnée la plus consolidée (définitive > consolidée > temps réel), puis la plus récente.
- **Conséquences :** le grain de `stg_rte_ecomix` est mixte (15 min récent, 30 min historique) ; les marts devront agréger à un pas commun. Les créneaux sans consommation (pré-publiés par le jeu temps réel) sont exclus en staging.

### Enedis : maille annuelle
- **Constat :** l'open data Enedis a migré sur `opendata.enedis.fr` ; les consommations par commune sont publiées à la maille annuelle, pas mensuelle.
- **Choix :** grain `stg_enedis_conso` = année × commune × secteur NAF.
- **Conséquences :** la corrélation conso ↔ conjoncture se fera au pas annuel avec Enedis ; le suivi infra-annuel repose sur la consommation régionale RTE.

### Option C : deux grains temporels, un mart par usage
- **Constat :** Enedis est annuel (année × commune × secteur NAF) alors que la conjoncture BdF/INSEE est mensuelle et que RTE est infra-horaire. Aucun grain unique ne sert à la fois la carte par commune et la corrélation temporelle.
- **Choix :**
  - `stg_enedis_conso` reste inchangé (année × commune × secteur NAF) et alimente `mart_conso_industrielle` (carte géographique par commune).
  - `stg_rte_mensuel` (nouveau) agrège le jeu `eco2mix-regional-cons-def` au mois : somme de la consommation par année × mois × région. Il alimente `mart_correlation_conjoncture`, joint sur `mois_debut` à `stg_bdf_pmi` et `stg_insee_ipi`.
  - `stg_rte_ecomix` (grain fin) reste la base de `mart_production_regionale` et `mart_tension_reseau`.
- **Pourquoi `cons-def` seul :** le temps réel (`tr`) ne couvre que ~3 mois et son pas diffère ; mélanger les deux fausserait la somme mensuelle.
- **Conséquences :**
  - `cons-def` est au pas de 30 min : la consommation mensuelle est en MWh (somme des MW × 0,5 h), pas une somme brute de MW.
  - Le dernier mois publié peut être incomplet : `est_mois_complet` (48 créneaux par jour) doit filtrer le mart de corrélation.
  - L'historique `cons-def` s'arrête fin juin 2026 : la corrélation n'inclura pas les mois plus récents tant que le jeu n'est pas rafraîchi.
  - Il n'y a pas de nouvelle table Bronze : `stg_rte_mensuel` lit `stg_rte_ecomix` filtré sur `source_dataset`.

### Banque de France : conjoncture régionale à la place du PMI
- **Constat :** le PMI est un indice S&P Global ; la Banque de France n'en publie pas.
- **Choix :** utiliser les séries de l'enquête mensuelle de conjoncture Pays de la Loire (`conj2-m-r52-*` sur Webstat : soldes d'opinion sur la production, les prévisions et l'utilisation des capacités).
- **Conséquences :** indicateur régional (plus pertinent pour la PDL que le PMI national). Les noms `raw_bdf_pmi` / `stg_bdf_pmi` sont conservés.

## Commandes fréquentes

```bash
# dbt (venv racine .venv)
cd dbt/
dbt debug                          # vérifier connexion Databricks
dbt run --select staging           # run uniquement staging
dbt test                           # tous les tests
dbt docs generate && dbt docs serve # docs locale

# Airflow (depuis airflow/)
docker compose up -d               # démarrer Airflow
docker compose down                # arrêter
docker compose logs -f airflow-scheduler # logs scheduler

# Python ingestion (venv ingestion/.venv)
cd ingestion/
pip install -r requirements.txt
python src/enedis_conso.py --annee 2023 2024                    # une ou plusieurs années (2011-2024)
python src/insee_ipi.py --start-period 2020-01                  # séries IPI mensuelles
python src/bdf_pmi.py --start-period 2020-01                    # nécessite BDF_API_KEY
python src/rte_ecomix.py --date 2026-09-30                      # temps réel (~3 derniers mois)
python src/rte_ecomix.py --date 2024-01-01 --dataset cons-def  # backfill historique (depuis 2013)
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
