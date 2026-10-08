-- Dimension calendrier au mois, générée sans source avec dbt_utils.date_spine.
-- La borne de fin est exclue : janvier 2018 inclus, janvier 2027 exclu = janvier 2018 à décembre 2026.
{% set premier_mois = "2018-01-01" %}
{% set mois_apres_le_dernier = "2027-01-01" %}

with mois as (

    {{ dbt_utils.date_spine(
        datepart="month",
        start_date="cast('" ~ premier_mois ~ "' as date)",
        end_date="cast('" ~ mois_apres_le_dernier ~ "' as date)"
    ) }}

)

select
    year(date_month)                                    as annee,
    month(date_month)                                   as mois,
    date_format(date_month, 'yyyy-MM')                  as periode,
    quarter(date_month)                                 as trimestre,
    case when month(date_month) <= 6 then 1 else 2 end  as semestre

from mois
