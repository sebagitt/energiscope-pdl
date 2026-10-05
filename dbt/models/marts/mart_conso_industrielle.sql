select
    {{ dbt_utils.generate_surrogate_key([
        'annee', 'code_commune', 'code_secteur_naf2', 'code_categorie_consommation'
    ]) }}                                       as conso_industrielle_id,
    annee,
    code_commune,
    nom_commune                                 as libelle_commune,
    code_secteur_naf2,
    code_categorie_consommation                 as categorie_consommation,
    conso_totale_mwh                            as conso_mwh,
    nb_sites                                    as nb_points_de_soutirage

from {{ ref('stg_enedis_conso') }}
where code_grand_secteur = 'INDUSTRIE'
