{#-
    Schéma des modèles :
    - sans schéma personnalisé : le schéma du profil ;
    - target « ci » (GitHub Actions) : <schéma du profil>_<schéma personnalisé>, par exemple ci_silver,
      pour que la CI ne touche jamais aux tables de production ;
    - sinon : le schéma personnalisé tel quel (silver, gold).
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif target.name == 'ci' -%}
        {{ target.schema }}_{{ custom_schema_name | trim }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
