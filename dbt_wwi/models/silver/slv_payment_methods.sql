select
    payment_method_id,
    {{ clean_text('payment_method_name') }} as payment_method_name
from {{ source('bronze', 'application_payment_methods') }}
{{ dedupe('payment_method_id', 'valid_from') }}
