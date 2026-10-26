select
    purchase_order_line_id,
    purchase_order_id,
    stock_item_id,
    package_type_id,
    ordered_outers,
    coalesce(received_outers, 0)             as received_outers,
    expected_unit_price_per_outer,
    last_receipt_date,
    coalesce(is_order_line_finalized, false) as is_order_line_finalized
from {{ source('bronze', 'purchasing_purchase_order_lines') }}
{{ dedupe('purchase_order_line_id', 'last_edited_when') }}
