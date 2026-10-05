-- Une série par source (voir vars dans dbt_project.yml). La jointure interne limite le mart
-- aux mois couverts par les trois sources (2018-2024 au dernier chargement).
with conso as (

    select
        annee,
        mois,
        mois_debut,
        est_mois_complet,
        consommation_mwh        as conso_regionale_mwh

    from {{ ref('stg_rte_mensuel') }}

),

ipi as (

    select
        mois,
        idbank                  as ipi_serie,
        valeur                  as ipi_valeur

    from {{ ref('stg_insee_ipi') }}
    where idbank = '{{ var("mart_ipi_idbank") }}'

),

bdf as (

    select
        mois,
        cle_serie               as bdf_serie,
        valeur                  as bdf_valeur

    from {{ ref('stg_bdf_pmi') }}
    where cle_serie = '{{ var("mart_bdf_series_key") }}'

),

joined as (

    select
        conso.annee,
        conso.mois,
        conso.mois_debut,
        conso.est_mois_complet,
        conso.conso_regionale_mwh,
        ipi.ipi_serie,
        ipi.ipi_valeur,
        bdf.bdf_serie,
        bdf.bdf_valeur

    from conso
    inner join ipi on ipi.mois = conso.mois_debut
    inner join bdf on bdf.mois = conso.mois_debut

),

with_previous as (

    select
        annee,
        mois,
        mois_debut,
        est_mois_complet,
        conso_regionale_mwh,
        ipi_serie,
        ipi_valeur,
        bdf_serie,
        bdf_valeur,
        lag(mois_debut) over w                  as mois_precedent,
        lag(conso_regionale_mwh) over w         as conso_precedente,
        lag(ipi_valeur) over w                  as ipi_precedent,
        lag(bdf_valeur) over w                  as bdf_precedent

    from joined
    window w as (order by mois_debut)

)

-- La variation n'est calculée que si le mois précédent est bien le mois civil précédent
select
    {{ dbt_utils.generate_surrogate_key(['annee', 'mois']) }} as correlation_id,
    annee,
    mois,
    date_format(mois_debut, 'yyyy-MM')          as periode,
    est_mois_complet,
    conso_regionale_mwh,
    ipi_serie,
    ipi_valeur,
    bdf_serie,
    bdf_valeur,
    case when mois_precedent = add_months(mois_debut, -1)
        then round((conso_regionale_mwh - conso_precedente) / nullif(conso_precedente, 0) * 100, 2)
    end                                         as variation_conso_pct,
    case when mois_precedent = add_months(mois_debut, -1)
        then round((ipi_valeur - ipi_precedent) / nullif(ipi_precedent, 0) * 100, 2)
    end                                         as variation_ipi_pct,
    case when mois_precedent = add_months(mois_debut, -1)
        then round((bdf_valeur - bdf_precedent) / nullif(bdf_precedent, 0) * 100, 2)
    end                                         as variation_bdf_pct

from with_previous
