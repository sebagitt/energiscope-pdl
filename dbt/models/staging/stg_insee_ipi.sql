with source as (

    select * from {{ source('bronze', 'raw_insee_ipi') }}

),

parsed as (

    select
        payload:idbank::string                                         as idbank,
        payload:libelle_serie::string                                  as libelle_serie,
        payload:time_period::string                                    as periode,
        try_cast(concat(payload:time_period::string, '-01') as date)   as mois,
        try_cast(payload:obs_value as double)                          as valeur,
        payload:obs_status::string                                     as statut_observation,

        source_dataset,
        ingested_at

    from source

),

deduplicated as (

    -- Les séries INSEE sont révisées : la dernière ingestion fait foi
    select *
    from parsed
    where idbank is not null
      and mois is not null
    qualify row_number() over (
        partition by idbank, mois
        order by ingested_at desc
    ) = 1

)

select
    {{ dbt_utils.generate_surrogate_key(['idbank', 'mois']) }} as insee_ipi_id,
    *
from deduplicated
