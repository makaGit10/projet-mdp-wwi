select
    country_id,
    {{ clean_text('country_name') }}           as country_name,
    {{ clean_text('formal_name') }}            as formal_name,
    upper({{ clean_text('iso_alpha3_code') }}) as iso_alpha3_code,
    {{ clean_text('continent') }}              as continent,
    {{ clean_text('region') }}                 as region,
    {{ clean_text('subregion') }}              as subregion,
    latest_recorded_population
from {{ source('bronze', 'application_countries') }}
{{ dedupe('country_id', 'valid_from') }}
