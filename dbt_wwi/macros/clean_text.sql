{# Supprime les espaces superflus et remplace les chaines vides par NULL #}
{% macro clean_text(col) -%}
    nullif(trim({{ col }}), '')
{%- endmacro %}
