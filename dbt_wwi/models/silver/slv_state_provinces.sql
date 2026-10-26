select
    state_province_id,
    upper({{ clean_text('state_province_code') }}) as state_province_code,
    {{ clean_text('state_province_name') }}        as state_province_name,
    country_id,
    {{ clean_text('sales_territory') }}            as sales_territory,
    latest_recorded_population
from {{ source('bronze', 'application_state_provinces') }}
{{ dedupe('state_province_id', 'valid_from') }}
