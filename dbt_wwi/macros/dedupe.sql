{# Conserve la version la plus recente de chaque cle (protection contre les doublons d'ingestion) #}
{% macro dedupe(key, order_by) -%}
    qualify row_number() over (partition by {{ key }} order by {{ order_by }} desc) = 1
{%- endmacro %}
