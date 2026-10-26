select
    package_type_id,
    {{ clean_text('package_type_name') }} as package_type_name
from {{ source('bronze', 'warehouse_package_types') }}
{{ dedupe('package_type_id', 'valid_from') }}
