select
    purchase_order_id,
    supplier_id,
    order_date,
    delivery_method_id,
    expected_delivery_date,
    coalesce(is_order_finalized, false) as is_order_finalized
from {{ source('bronze', 'purchasing_purchase_orders') }}
{{ dedupe('purchase_order_id', 'last_edited_when') }}
