select
    supplier_category_id,
    {{ clean_text('supplier_category_name') }} as supplier_category_name
from {{ source('bronze', 'purchasing_supplier_categories') }}
{{ dedupe('supplier_category_id', 'valid_from') }}
