select
    delivery_method_id,
    {{ clean_text('delivery_method_name') }} as delivery_method_name
from {{ source('bronze', 'application_delivery_methods') }}
{{ dedupe('delivery_method_id', 'valid_from') }}
