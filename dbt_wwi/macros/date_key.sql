{# Cle de date entiere au format AAAAMMJJ (ex : 20160531) #}
{% macro date_key(col) -%}
    (year({{ col }}) * 10000 + month({{ col }}) * 100 + day({{ col }}))
{%- endmacro %}
