select
    transaction_type_id,
    {{ clean_text('transaction_type_name') }} as transaction_type_name
from {{ source('bronze', 'application_transaction_types') }}
{{ dedupe('transaction_type_id', 'valid_from') }}
