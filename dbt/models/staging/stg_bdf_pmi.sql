with source as (

    select * from {{ source('bronze', 'raw_bdf_pmi') }}

),

parsed as (

    select
        payload:series_key::string                                     as cle_serie,
        payload:title_fr::string                                       as libelle_serie,
        payload:time_period::string                                    as periode,
        try_cast(concat(payload:time_period::string, '-01') as date)   as mois,
        try_cast(payload:obs_value as double)                          as valeur,

        source_dataset,
        ingested_at

    from source

),

deduplicated as (

    -- Les soldes d'opinion sont révisés le mois suivant : la dernière ingestion fait foi
    select *
    from parsed
    where cle_serie is not null
      and mois is not null
    qualify row_number() over (
        partition by cle_serie, mois
        order by ingested_at desc
    ) = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['cle_serie', 'mois']) }} as bdf_pmi_id,
    *
from deduplicated
