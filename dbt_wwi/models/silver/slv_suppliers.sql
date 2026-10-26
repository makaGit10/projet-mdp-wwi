select
    supplier_id,
    {{ clean_text('supplier_name') }} as supplier_name,
    supplier_category_id,
    delivery_method_id,
    delivery_city_id,
    payment_days,
    {{ clean_text('website_url') }}   as website_url
from {{ source('bronze', 'purchasing_suppliers') }}
{{ dedupe('supplier_id', 'valid_from') }}
