-- Le jeu cons-def est au pas de 30 min : chaque créneau pèse 0,5 h pour passer de MW à MWh
{% set heures_par_creneau = 0.5 %}
{% set creneaux_par_jour = 48 %}

with cons_def as (

    select *
    from {{ ref('stg_rte_ecomix') }}
    where source_dataset = 'eco2mix-regional-cons-def'

),

mensuel as (

    select
        year(date_locale)                                    as annee,
        month(date_locale)                                   as mois,
        code_insee_region,
        max(libelle_region)                                  as libelle_region,
        count(*)                                             as nb_creneaux,
        sum(consommation_mw) * {{ heures_par_creneau }}      as consommation_mwh,
        sum(production_thermique_mw) * {{ heures_par_creneau }}     as production_thermique_mwh,
        sum(production_nucleaire_mw) * {{ heures_par_creneau }}     as production_nucleaire_mwh,
        sum(production_eolien_mw) * {{ heures_par_creneau }}        as production_eolien_mwh,
        sum(production_solaire_mw) * {{ heures_par_creneau }}       as production_solaire_mwh,
        sum(production_hydraulique_mw) * {{ heures_par_creneau }}   as production_hydraulique_mwh,
        sum(production_bioenergies_mw) * {{ heures_par_creneau }}   as production_bioenergies_mwh

    from cons_def
    where date_locale is not null
    group by year(date_locale), month(date_locale), code_insee_region

)

select
    {{ dbt_utils.generate_surrogate_key(['annee', 'mois', 'code_insee_region']) }} as rte_mensuel_id,
    annee,
    mois,
    make_date(annee, mois, 1)                                as mois_debut,
    code_insee_region,
    libelle_region,
    nb_creneaux,
    -- Mars perd 1 h (passage à l'heure d'été : 2 créneaux). En octobre, ODRE ne publie pas
    -- l'heure répétée : le mois garde 48 créneaux par jour, il n'y a rien à ajouter.
    nb_creneaux = day(last_day(make_date(annee, mois, 1))) * {{ creneaux_par_jour }}
        - case when mois = 3 then 2 else 0 end                as est_mois_complet,
    consommation_mwh,
    production_thermique_mwh,
    production_nucleaire_mwh,
    production_eolien_mwh,
    production_solaire_mwh,
    production_hydraulique_mwh,
    production_bioenergies_mwh
from mensuel
