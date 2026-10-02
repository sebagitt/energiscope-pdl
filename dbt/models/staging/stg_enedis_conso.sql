with source as (

    select * from {{ source('bronze', 'raw_enedis_conso') }}

),

parsed as (

    select
        try_cast(payload:annee as int)                    as annee,
        lpad(payload:code_commune::string, 5, '0')        as code_commune,
        payload:nom_commune::string                       as nom_commune,
        payload:code_region::string                       as code_region,
        upper(trim(payload:code_grand_secteur::string))   as code_grand_secteur,
        payload:code_secteur_naf2::string                 as code_secteur_naf2,
        upper(trim(payload:code_categorie_consommation::string)) as code_categorie_consommation,
        try_cast(payload:nb_sites as int)                 as nb_sites,
        try_cast(payload:conso_totale_mwh as double)      as conso_totale_mwh,

        source_dataset,
        ingested_at

    from source

),

deduplicated as (

    select *
    from parsed
    where annee is not null
      and code_commune is not null
      and code_grand_secteur is not null
    qualify row_number() over (
        partition by annee, code_commune, code_grand_secteur, code_secteur_naf2, code_categorie_consommation
        order by ingested_at desc
    ) = 1

)

select
    {{ dbt_utils.generate_surrogate_key([
        'annee', 'code_commune', 'code_grand_secteur', 'code_secteur_naf2', 'code_categorie_consommation'
    ]) }} as enedis_conso_id,
    *
from deduplicated
