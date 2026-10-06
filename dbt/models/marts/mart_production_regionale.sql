-- Énergies renouvelables : éolien, solaire, hydraulique, bioénergies (le thermique est fossile).
-- Une filière sans aucune valeur sur le mois compte pour zéro (ex. nucléaire : pas de centrale en Pays de la Loire).
with filieres as (

    select
        annee,
        mois,
        mois_debut,
        code_insee_region,
        libelle_region,
        est_mois_complet,
        consommation_mwh,
        coalesce(production_thermique_mwh, 0)       as prod_thermique_mwh,
        coalesce(production_nucleaire_mwh, 0)       as prod_nucleaire_mwh,
        coalesce(production_eolien_mwh, 0)          as prod_eolien_mwh,
        coalesce(production_solaire_mwh, 0)         as prod_solaire_mwh,
        coalesce(production_hydraulique_mwh, 0)     as prod_hydraulique_mwh,
        coalesce(production_bioenergies_mwh, 0)     as prod_bioenergies_mwh

    from {{ ref('stg_rte_mensuel') }}

),

totaux as (

    select
        annee,
        mois,
        mois_debut,
        code_insee_region,
        libelle_region,
        est_mois_complet,
        consommation_mwh,
        prod_eolien_mwh,
        prod_solaire_mwh,
        prod_hydraulique_mwh,
        prod_bioenergies_mwh,
        prod_eolien_mwh + prod_solaire_mwh + prod_hydraulique_mwh + prod_bioenergies_mwh   as prod_enr_mwh,
        prod_thermique_mwh + prod_nucleaire_mwh
            + prod_eolien_mwh + prod_solaire_mwh + prod_hydraulique_mwh + prod_bioenergies_mwh   as prod_totale_mwh

    from filieres

)

select
    {{ dbt_utils.generate_surrogate_key(['annee', 'mois', 'code_insee_region']) }} as production_regionale_id,
    annee,
    mois,
    date_format(mois_debut, 'yyyy-MM')                  as periode,
    code_insee_region,
    libelle_region                                      as region,
    prod_totale_mwh,
    prod_enr_mwh,
    prod_eolien_mwh,
    prod_solaire_mwh,
    prod_hydraulique_mwh,
    prod_bioenergies_mwh,
    consommation_mwh                                    as conso_totale_mwh,
    round(prod_enr_mwh / nullif(consommation_mwh, 0) * 100, 2) as taux_couverture_enr,
    est_mois_complet

from totaux
