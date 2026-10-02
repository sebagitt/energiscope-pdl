with source as (

    select * from {{ source('bronze', 'raw_rte_ecomix') }}

),

parsed as (

    select
        payload:code_insee_region::string             as code_insee_region,
        payload:libelle_region::string                as libelle_region,
        payload:nature::string                        as nature_donnees,
        try_cast(payload:date as date)                as date_locale,
        payload:heure::string                         as heure_locale,
        try_cast(payload:date_heure as timestamp)     as horodatage_utc,

        try_cast(payload:consommation as int)         as consommation_mw,
        try_cast(payload:thermique as int)            as production_thermique_mw,
        try_cast(payload:nucleaire as int)            as production_nucleaire_mw,
        try_cast(payload:eolien as int)               as production_eolien_mw,
        try_cast(payload:eolien_terrestre as int)     as production_eolien_terrestre_mw,
        try_cast(payload:eolien_offshore as int)      as production_eolien_offshore_mw,
        try_cast(payload:solaire as int)              as production_solaire_mw,
        try_cast(payload:hydraulique as int)          as production_hydraulique_mw,
        try_cast(payload:bioenergies as int)          as production_bioenergies_mw,
        try_cast(payload:pompage as int)              as pompage_mw,
        try_cast(payload:stockage_batterie as int)    as stockage_batterie_mw,
        try_cast(payload:destockage_batterie as int)  as destockage_batterie_mw,
        try_cast(payload:ech_physiques as int)        as echanges_physiques_mw,

        try_cast(payload:tco_thermique as double)     as taux_couverture_thermique_pct,
        try_cast(payload:tco_nucleaire as double)     as taux_couverture_nucleaire_pct,
        try_cast(payload:tco_eolien as double)        as taux_couverture_eolien_pct,
        try_cast(payload:tco_solaire as double)       as taux_couverture_solaire_pct,
        try_cast(payload:tco_hydraulique as double)   as taux_couverture_hydraulique_pct,
        try_cast(payload:tco_bioenergies as double)   as taux_couverture_bioenergies_pct,
        try_cast(payload:tch_thermique as double)     as taux_charge_thermique_pct,
        try_cast(payload:tch_nucleaire as double)     as taux_charge_nucleaire_pct,
        try_cast(payload:tch_eolien as double)        as taux_charge_eolien_pct,
        try_cast(payload:tch_solaire as double)       as taux_charge_solaire_pct,
        try_cast(payload:tch_hydraulique as double)   as taux_charge_hydraulique_pct,
        try_cast(payload:tch_bioenergies as double)   as taux_charge_bioenergies_pct,

        source_dataset,
        ingested_at

    from source

),

deduplicated as (

    -- Un même créneau peut venir de plusieurs ingestions ou des deux jeux ODRE :
    -- on garde le niveau de consolidation le plus élevé, puis le chargement le plus récent.
    select *
    from parsed
    where code_insee_region is not null
      and horodatage_utc is not null
      -- Le jeu temps réel publie à l'avance les créneaux de la journée, sans valeurs
      and consommation_mw is not null
    qualify row_number() over (
        partition by code_insee_region, horodatage_utc
        order by
            case nature_donnees
                when 'Données définitives' then 1
                when 'Données consolidées' then 2
                else 3
            end,
            ingested_at desc
    ) = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['code_insee_region', 'horodatage_utc']) }} as rte_ecomix_id,
    *
from deduplicated
