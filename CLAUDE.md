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
│   ├── workflows/
│   │   ├── dbt_ci.yml           ← compile + run/test slim CI (push et PR sur main/develop)
│   │   └── dbt_docs.yml         ← docs dbt publiées sur GitHub Pages (push sur main)
│   └── scripts/dbt_summary.py   ← résumé Markdown des résultats dbt pour la page du workflow
├── ingestion/                   ← scripts Python d'ingestion
│   ├── src/
│   │   ├── rte_ecomix.py        ← API RTE eco2mix (15min, --dataset cons-def pour l'historique)
│   │   ├── enedis_conso.py      ← API Enedis Open Data (annuel)
│   │   ├── insee_ipi.py         ← INSEE IPI + emploi
│   │   └── bdf_pmi.py           ← Banque de France conjoncture régionale PDL
│   ├── tests/
│   └── requirements.txt
├── airflow/                     ← DAGs Airflow
│   ├── docker-compose.yml       ← setup officiel Airflow 2.9.3, adapté (voir Commandes fréquentes)
│   ├── Dockerfile               ← image Airflow + venvs ingestion et dbt + copie du projet
│   ├── dags/
│   │   ├── energiscope_common.py ← chemins, default_args, chargement du .env (pas de DAG)
│   │   ├── dag_ingestion_rte_realtime.py ← energiscope_rte_realtime, toutes les 15 min (--since 120)
│   │   ├── dag_ingestion_daily.py ← energiscope_ingestion_daily, 6h00 : Enedis → INSEE → BdF
│   │   └── dag_dbt_run.py       ← energiscope_dbt, 7h00 : dbt run → test → docs (BashOperator, venv racine)
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
├── scripts/
│   └── activate_env.ps1         ← active le bon venv + charge .env (PowerShell)
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
| Airflow                                            | aucun (Docker)   | `airflow/`         | image `energiscope-airflow` : ses propres venvs Linux `/venvs/ingestion` et `/venvs/dbt` |

**Méthode recommandée (PowerShell) : `scripts/activate_env.ps1`.** Il active le bon venv, charge le `.env` et affiche un résumé (venv, Python, packages clés, variables du `.env` définies ou vides, sans jamais afficher leurs valeurs).

```powershell
. .\scripts\activate_env.ps1 ingestion   # ingestion\.venv : scripts Python, pytest
. .\scripts\activate_env.ps1 dbt         # .venv racine : dbt
```

- Le point initial (dot-sourcing) est obligatoire : sans lui, le venv et les variables disparaissent à la fin du script.
- On peut passer de l'un à l'autre directement : le venv précédent est désactivé automatiquement.
- Les variables du `.env` écrasent celles déjà définies dans la session. Les lignes vides ou commentées sont ignorées.
- Une variable marquée `VIDE` est présente dans le `.env` mais sans valeur (ex. `RTE_API_KEY`, optionnelle).
- Venv introuvable : le script le signale avec la commande de création. Argument autre que `ingestion` ou `dbt` : refusé.

```bash
# Activation manuelle (Windows), si on n'utilise pas le script
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
- Les versions de dbt sont épinglées dans `dbt/requirements.txt` (utilisé par les workflows GitHub Actions ; le Dockerfile Airflow épingle les mêmes).
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
| Banque de France conjoncture PDL | https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/observations/exports/json (séries `CONJ2.M.R52.*`) | JSON, `Authorization: Apikey <BDF_API_KEY>` | Mensuel |

Webstat est une instance Opendatasoft : les datasets `conj2-*` du catalogue public sont des fiches de séries sans valeurs. Les observations sont dans le dataset restreint `observations`, visible uniquement avec une clé (56 caractères). L'ancienne API `api.webstat.banque-france.fr` (en-tête `X-IBM-Client-Id`) refuse cette clé.

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

### Marts Gold : écarts à la spec initiale
- **`mart_correlation_conjoncture`** : la colonne est `conso_regionale_mwh`, pas `conso_industrie_mwh`. RTE ne distingue pas l'industrie ; la consommation industrielle n'existe qu'à la maille annuelle (Enedis). Une série par source (`mart_ipi_idbank`, `mart_bdf_series_key` dans `dbt_project.yml`) ; jointure interne, donc 2018-2024 tant que BdF et INSEE ne sont pas rechargés plus loin.
- **`mart_production_regionale`** : `stg_rte_mensuel` a été étendu avec les productions par filière (MWh). Énergies renouvelables = éolien + solaire + hydraulique + bioénergies.
- **`mart_tension_reseau`** : énergies en MWh sur la durée du créneau (15 min en temps réel, 30 min en consolidé, colonne `pas_minutes`). Le bilan prod − conso est structurellement négatif (la région importe ~2 100 MW en moyenne), donc l'ancien `statut_tension` (TENSION sur 99,8 % des créneaux) a été supprimé au profit de `taux_couverture_locale` (prod / conso × 100) et `variation_couverture_pct` (écart relatif à la moyenne non pondérée des taux du même mois civil local).
- **`mart_conso_industrielle`** : le grain inclut la catégorie de consommation (ENT/PRO). Les sites PRO n'ont pas de code NAF2.

### Banque de France : conjoncture régionale à la place du PMI
- **Constat :** le PMI est un indice S&P Global ; la Banque de France n'en publie pas.
- **Choix :** utiliser les séries de l'enquête mensuelle de conjoncture Pays de la Loire (`conj2-m-r52-*` sur Webstat : soldes d'opinion sur la production, les prévisions et l'utilisation des capacités).
- **Conséquences :** indicateur régional (plus pertinent pour la PDL que le PMI national). Les noms `raw_bdf_pmi` / `stg_bdf_pmi` sont conservés.

## CI/CD GitHub Actions

Deux workflows dans `.github/workflows/`. **Ils n'ont pas encore tourné sur GitHub** : seules leurs commandes dbt ont été répétées en local (compilation, sélection `state:modified`, `dbt docs generate`). Ils ne fonctionneront qu'après configuration des secrets ci-dessous.

| Workflow | Déclencheur | Rôle |
|---|---|---|
| `dbt_ci.yml` | push et pull request sur `main` et `develop` (+ lancement manuel) | `dbt deps`, `dbt compile` (sans connexion), puis `dbt run` et `dbt test` des seuls modèles modifiés (`state:modified+`) |
| `dbt_docs.yml` | push sur `main` | `dbt docs generate`, puis publication de `index.html`, `catalog.json` et `manifest.json` sur GitHub Pages |

Les deux ont un timeout de 20 minutes, un cache pip, la sortie dbt dans le log de chaque étape, et en cas d'échec `dbt/logs/dbt.log` complet affiché puis conservé comme artefact `dbt-logs`.

### Les 5 secrets à configurer

GitHub > Settings > Secrets and variables > Actions > New repository secret :

| Secret | Valeur |
|---|---|
| `DATABRICKS_HOST` | URL du workspace, la même que dans le `.env` (`https://dbc-….cloud.databricks.com`) |
| `DATABRICKS_TOKEN` | Personal Access Token Databricks ; préférer un token dédié à la CI, révocable séparément |
| `DATABRICKS_HTTP_PATH` | Chemin du SQL warehouse (`/sql/1.0/warehouses/<id>`) |
| `DBT_CATALOG` | Catalogue Unity Catalog (`workspace`) |
| `DBT_SCHEMA` | Préfixe des schémas de la CI : **`ci`** (voir ci-dessous) |

**Coller la valeur seule, jamais la ligne du `.env`.** `DATABRICKS_HOST=https://dbc-…` collé tel quel donne un hôte `databricks_host=…` : dbt reste bloqué ~15 minutes puis échoue (arrivé au premier run du 2026-10-05). Les workflows vérifient désormais le format (`.github/scripts/check_secrets.sh`) et testent la connexion (`dbt debug --connection`, 180 s max) avant tout `dbt run`.

En ligne de commande, la valeur est lue dans le `.env` local sans être affichée (depuis la racine du projet, Git Bash) :

```bash
for name in DATABRICKS_HOST DATABRICKS_TOKEN DATABRICKS_HTTP_PATH; do
  gh secret set "$name" --body "$(grep "^$name=" .env | cut -d= -f2- | tr -d '\r')"
done
gh secret set DBT_CATALOG --body "workspace"
gh secret set DBT_SCHEMA --body "ci"
gh secret list      # vérifier les noms et les dates (les valeurs ne sont jamais lisibles)
```

Les pull requests venant d'un fork n'ont pas accès aux secrets : seule la compilation y tourne.

### La CI n'écrit jamais en production

`dbt/macros/generate_schema_name.sql` renvoie `silver` et `gold` tels quels, sauf avec la cible `ci` : les modèles y sont construits dans `<DBT_SCHEMA>_silver` et `<DBT_SCHEMA>_gold` (`ci_silver`, `ci_gold`). Le profil des workflows est `dbt/ci/profiles.yml` (cibles `ci` et `prod`, aucun secret, tout vient de l'environnement). La cible `prod` ne sert qu'à lire les métadonnées pour la documentation : n'y jamais lancer `dbt run`. Ces schémas de CI persistent entre les exécutions ; nettoyage manuel : `DROP SCHEMA IF EXISTS workspace.ci_silver CASCADE` (idem `ci_gold`).

### Slim CI et manifest de référence

`state:modified` compare le projet courant au manifest d'un état précédent. Le manifest de référence est généré avec la cible `prod` (compilation seule) puis publié comme artefact `dbt-manifest` (actions/upload-artifact, conservé 90 jours) à chaque exécution réussie sur `main`. Les autres exécutions le récupèrent depuis le dernier run réussi de `main` (actions/download-artifact avec `run-id`) et l'utilisent aussi pour `--defer` : les modèles non modifiés sont lus dans la vraie production, en lecture seule. Sans manifest (premier run, artefact expiré), la CI construit tout (`staging` et `marts`) dans les schémas `ci_*`.

Un artefact ne peut pas être envoyé à la main (ni par `gh`, ni par l'API) : seul un run de workflow le crée. Pour l'amorcer, et pour le vérifier ou le récupérer :

```bash
gh workflow run dbt_ci.yml --ref main                         # lance le workflow sur main (déclencheur manuel) : crée l'artefact
gh run list --workflow dbt_ci.yml --branch main --limit 5     # trouver le dernier run réussi
gh run download <run-id> -n dbt-manifest -D /tmp/dbt-state    # récupérer manifest.json en local
```

Reproduire la sélection en local (profil CI, sans connexion). Sous Git Bash, protéger le chemin du warehouse, sinon il est réécrit en `C:/Program Files/Git/sql/...` :

```bash
export MSYS2_ENV_CONV_EXCL="DATABRICKS_HTTP_PATH;DATABRICKS_HOST" DBT_CATALOG=workspace DBT_SCHEMA=ci DBT_PROFILES_DIR=$PWD/dbt/ci
cd dbt
dbt compile --target prod --no-populate-cache --target-path state_out        # le manifest de référence
dbt ls --target ci --select state:modified+ --state /tmp/dbt-state --resource-type model
```

### Activer GitHub Pages (étape manuelle, une seule fois)

1. GitHub > Settings > Pages > Build and deployment > **Source : « GitHub Actions »** (sans cela, `dbt_docs.yml` échoue à l'étape de configuration de Pages).
2. Le dépôt doit être public, ou le plan GitHub doit autoriser Pages sur un dépôt privé. Le site est public : il montre le SQL des modèles, leurs descriptions et les noms de colonnes (jamais de données ni de secrets : vérifié sur les trois fichiers publiés).
3. Au premier push sur `main`, le site apparaît sur `https://sebagitt.github.io/energiscope-pdl/`.

## Commandes fréquentes

```bash
# dbt (venv racine .venv)
cd dbt/
dbt debug                          # vérifier connexion Databricks
dbt run --select staging           # run uniquement staging
dbt test                           # tous les tests
dbt docs generate && dbt docs serve # docs locale

# Airflow 2.9.3 (depuis airflow/) : UI http://localhost:8080, login airflow / airflow
# Le docker-compose.yml est l'officiel 2.9.3, avec ces modifications :
#  - AIRFLOW__CORE__FERNET_KEY lit ${AIRFLOW_FERNET_KEY} (l'officiel la fige à '') ; airflow/.env contient AIRFLOW_UID et la clé
#  - le port est publié sur 127.0.0.1 uniquement (mot de passe par défaut, pas d'accès depuis le réseau)
#  - AIRFLOW__CORE__LOAD_EXAMPLES à 'false' (pas de DAGs d'exemple)
#  - image personnalisée energiscope-airflow:2.9.3 (airflow/Dockerfile), construite par le seul service airflow-init
#    avec la racine du projet comme contexte ; elle contient /venvs/ingestion et /venvs/dbt (Linux)
#  - env_file ../.env : DATABRICKS_*, BDF_API_KEY... sont injectées dans les conteneurs (jamais dans l'image : voir .dockerignore)
#  - ingestion/src et dbt/ montés en lecture seule sous /opt/energiscope : une modification de code ne demande pas de rebuild
#    (target/, logs/ et dbt_packages/ de dbt sont redirigés vers /tmp/dbt et /opt/energiscope/dbt_packages)
# Les 3 DAGs (energiscope_rte_realtime, _ingestion_daily, _dbt) sont ACTIFS depuis le 2026-10-05.
# Limite connue : la fenêtre d'INSEE et de la Banque de France (mois courant) ne charge rien, ces séries étant
# publiées avec 1 à 3 mois de retard ; l'historique 2025-2026 s'y rattrape à la main avec --start-date.
# Rebuild nécessaire si requirements.txt, packages.yml ou le Dockerfile changent (pas pour le code : montage) :
docker compose build --no-cache
# Première installation : docker compose up airflow-init (migrations + création de l'utilisateur)
docker compose up -d               # démarrer Airflow
docker compose down                # arrêter
docker compose logs -f airflow-scheduler # logs scheduler

# Python ingestion (venv ingestion/.venv)
cd ingestion/
pip install -r requirements.txt
python src/enedis_conso.py --year 2023 2024                                  # une ou plusieurs années (2011-2024)
python src/insee_ipi.py --start-date 2020-01 --end-date 2024-12              # séries IPI mensuelles (bornes optionnelles)
python src/bdf_pmi.py --start-date 2020-01 --end-date 2024-12                # nécessite BDF_API_KEY
python src/rte_ecomix.py --date 2026-09-30                      # temps réel (~3 derniers mois), journée entière
python src/rte_ecomix.py --date 2026-10-05 --since 120          # fenêtre glissante : créneaux des 120 dernières minutes (≤ 8 lignes), --date = simple étiquette
python src/rte_ecomix.py --dataset cons-def --start-date 2018-01              # backfill mensuel (1 requête + 1 chargement par mois), reprise possible en relançant depuis le mois en échec
python src/rte_ecomix.py --date 2024-01-01 --dataset cons-def                # un seul jour de l'historique
pytest tests/ -v                   # tests unitaires

# GitHub Actions : voir la section « CI/CD GitHub Actions » ci-dessus
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
