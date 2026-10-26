select
    color_id,
    {{ clean_text('color_name') }} as color_name
from {{ source('bronze', 'warehouse_colors') }}
{{ dedupe('color_id', 'valid_from') }}
