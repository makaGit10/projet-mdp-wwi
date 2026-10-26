select
    city_id,
    {{ clean_text('city_name') }} as city_name,
    state_province_id,
    latest_recorded_population
from {{ source('bronze', 'application_cities') }}
{{ dedupe('city_id', 'valid_from') }}
