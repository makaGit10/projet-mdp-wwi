select
    order_line_id,
    order_id,
    stock_item_id,
    package_type_id,
    quantity,
    coalesce(picked_quantity, 0) as picked_quantity,
    unit_price,
    tax_rate
from {{ source('bronze', 'sales_order_lines') }}
where quantity > 0 and unit_price >= 0
{{ dedupe('order_line_id', 'last_edited_when') }}
