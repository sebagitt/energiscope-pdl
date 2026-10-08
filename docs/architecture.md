# Architecture d'EnergiScope PDL

Pipeline analytique sur la consommation électrique en Pays de la Loire, croisée avec la conjoncture
industrielle (INSEE, Banque de France). Question décisionnelle : la consommation varie-t-elle avec la
conjoncture sectorielle, et peut-on anticiper des tensions réseau ?

Chiffres relevés le 6 octobre 2026. Le détail de chaque transformation est dans
[dbt_dag_description.md](dbt_dag_description.md).

## Pipeline Bronze / Silver / Gold

```
SOURCES                INGESTION (Python)   BRONZE (Delta)        SILVER (vues dbt)               GOLD (tables dbt)
-------                ------------------   --------------        -----------------               -----------------
RTE eco2mix (ODRE)  -> rte_ecomix.py     -> raw_rte_ecomix     -> stg_rte_ecomix ---------------> mart_tension_reseau
 15 min / 30 min                                                       |
                                                                       v
                                                                  stg_rte_mensuel -----------+--> mart_production_regionale
                                                                                             |
INSEE BDM (IPI)     -> insee_ipi.py      -> raw_insee_ipi      -> stg_insee_ipi -------------+--> mart_correlation_conjoncture
Banque de France    -> bdf_pmi.py        -> raw_bdf_pmi        -> stg_bdf_pmi ---------------+

Enedis Open Data    -> enedis_conso.py   -> raw_enedis_conso   -> stg_enedis_conso -------------> mart_conso_industrielle
```

Entrées de chaque table Gold :

| Table Gold | Construite à partir de |
|---|---|
| `mart_tension_reseau` | `stg_rte_ecomix` |
| `mart_production_regionale` | `stg_rte_mensuel` |
| `mart_correlation_conjoncture` | `stg_rte_mensuel`, `stg_insee_ipi` et `stg_bdf_pmi` |
| `mart_conso_industrielle` | `stg_enedis_conso` |

Autour du pipeline :

- **Stockage et calcul :** Databricks (Delta Lake), catalogue `workspace`, schémas `bronze`, `silver`, `gold`.
- **Orchestration :** Apache Airflow 2.9.3 dans Docker, avec une image qui embarque deux environnements
  Python (ingestion et dbt).
- **Qualité :** 101 tests dbt, tous au vert.
- **Intégration continue :** GitHub Actions valide chaque changement dbt dans des schémas isolés
  (`ci_silver`, `ci_gold`) et publie la documentation dbt sur GitHub Pages.
- **Restitution :** rapport Power BI de 4 pages.

Les tables Bronze partagent un même schéma de 4 colonnes (`source_dataset`, `extracted_for`, `payload`
en JSON brut, `ingested_at`), alimentées en ajout seul ; le typage et le dédoublonnage se font en Silver.

## Les 9 modèles dbt

| Couche | Modèle | Grain | Lignes |
|---|---|---|---|
| Silver | `stg_rte_ecomix` | région × créneau (15 min en temps réel, 30 min en historique) | 149 092 |
| Silver | `stg_rte_mensuel` | région × mois (jeu consolidé de RTE, en MWh) | 102 |
| Silver | `stg_enedis_conso` | année × commune × grand secteur × secteur NAF2 × catégorie de consommation | 31 552 |
| Silver | `stg_insee_ipi` | série × mois | 309 |
| Silver | `stg_bdf_pmi` | série × mois | 416 |
| Gold | `mart_conso_industrielle` | année × commune × secteur NAF2 × catégorie (industrie uniquement) | 8 335 |
| Gold | `mart_production_regionale` | année × mois × région | 102 |
| Gold | `mart_correlation_conjoncture` | année × mois | 102 |
| Gold | `mart_tension_reseau` | région × créneau | 149 092 |

Les modèles Silver sont des vues, les modèles Gold des tables.

## Les 3 DAGs Airflow

Horaires en heure de Paris. Tous les DAGs sont actifs.

| DAG | Planification | Tâches |
|---|---|---|
| `energiscope_rte_realtime` | toutes les 15 minutes (`*/15 * * * *`) | `ingestion_rte` : créneaux RTE des 2 dernières heures (au plus 8 lignes) |
| `energiscope_ingestion_daily` | tous les jours à 6h00 (`0 6 * * *`) | `ingest_enedis`, puis `ingest_insee`, puis `ingest_bdf` ; l'échec d'une tâche arrête la suite |
| `energiscope_dbt` | tous les jours à 7h00 (`0 7 * * *`) | `dbt_run`, puis `dbt_test`, puis `dbt_docs` |

## Limites connues

**Données**

- **Enedis :** les données sont annuelles et seules 2023 et 2024 sont chargées ; 2025 n'est pas encore
  publié. Le plafond à 2024 est codé en dur dans le DAG quotidien et devra être relevé à la main. En
  attendant, la même année est rechargée chaque jour (doublons éliminés en Silver).
- **RTE :** le jeu consolidé s'arrête fin juin 2026. Les marts mensuels couvrent donc de janvier 2018 à
  juin 2026 (102 mois), alors que `mart_tension_reseau` va jusqu'aux derniers créneaux temps réel.
- **Grain mixte :** les créneaux RTE sont à 15 minutes en temps réel et à 30 minutes dans l'historique.
- **INSEE :** l'indice de production industrielle est national, la BDM ne publie pas de série régionale.
- **Banque de France :** il n'existe pas de PMI public ; les soldes d'opinion régionaux de l'enquête de
  conjoncture en tiennent lieu.
- **Bronze :** il contient des doublons (447 178 lignes brutes de RTE pour 149 092 créneaux en Silver),
  sans effet sur Silver et Gold qui dédoublonnent.

**Analyse**

- **Consommation régionale, pas industrielle :** RTE ne distingue pas les secteurs. La consommation
  utilisée dans `mart_correlation_conjoncture` est celle de toute la région.
- **Corrélation faible :** sur 102 mois, la corrélation mensuelle entre consommation et indice de
  production industrielle vaut 0,13 ; la consommation brute est dominée par le chauffage. Répondre à la
  question décisionnelle demanderait de corriger de la température.
- **Tension du réseau :** le bilan production − consommation ignore les échanges avec les régions
  voisines ; la région importe l'essentiel de son électricité, d'où des indicateurs relatifs (taux de
  couverture) plutôt qu'un statut de tension. La colonne `annee` est calculée en UTC.

**Restitution et exploitation**

- **Dashboard Power BI :** usage portfolio uniquement. Les slicers sont limités à la page 1 et ne
  s'appliquent pas entre les marts (pas de filtrage croisé). Le fichier `.pbix` n'est pas versionné.
- **Airflow :** il tourne en local dans Docker, donc les DAGs ne s'exécutent que lorsque Docker est lancé.
- **CI :** les schémas `ci_silver` et `ci_gold` persistent entre les exécutions et se nettoient à la main.
