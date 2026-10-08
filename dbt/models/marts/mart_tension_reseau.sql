-- Les puissances eco2mix (MW) sont converties en énergie sur la durée du créneau :
-- 15 min pour le jeu temps réel, 30 min pour le jeu consolidé/définitif.
with creneaux as (

    select
        rte_ecomix_id,
        code_insee_region,
        libelle_region,
        horodatage_utc,
        date_locale,
        heure_locale,
        consommation_mw,
        case source_dataset
            when 'eco2mix-regional-tr' then 15
            else 30
        end                                                 as pas_minutes,
        coalesce(production_thermique_mw, 0)
            + coalesce(production_nucleaire_mw, 0)
            + coalesce(production_eolien_mw, 0)
            + coalesce(production_solaire_mw, 0)
            + coalesce(production_hydraulique_mw, 0)
            + coalesce(production_bioenergies_mw, 0)       as production_mw

    from {{ ref('stg_rte_ecomix') }}

),

energie as (

    select
        rte_ecomix_id,
        code_insee_region,
        libelle_region,
        horodatage_utc,
        date_locale,
        heure_locale,
        pas_minutes,
        production_mw * pas_minutes / 60.0                  as prod_mwh,
        consommation_mw * pas_minutes / 60.0                as conso_mwh,
        production_mw / nullif(consommation_mw, 0) * 100    as taux_couverture_locale

    from creneaux

)

select
    rte_ecomix_id                                           as tension_id,
    horodatage_utc                                          as date_heure,
    year(horodatage_utc)                                    as annee,
    code_insee_region,
    libelle_region                                          as region,
    date_locale                                             as date,
    heure_locale                                            as heure,
    pas_minutes,
    prod_mwh,
    conso_mwh,
    prod_mwh - conso_mwh                                    as ecart_mwh,
    round(taux_couverture_locale, 2)                        as taux_couverture_locale,
    -- Écart relatif à la moyenne (non pondérée) des taux des créneaux du même mois civil local
    round(
        (taux_couverture_locale
            / nullif(avg(taux_couverture_locale) over (
                partition by code_insee_region, year(date_locale), month(date_locale)
            ), 0) - 1) * 100,
        2
    )                                                       as variation_couverture_pct

from energie
