select
    stock_item_id,
    {{ clean_text('stock_item_name') }}                as stock_item_name,
    supplier_id,
    color_id,
    unit_package_id,
    outer_package_id,
    coalesce({{ clean_text('brand') }}, 'Sans marque') as brand,
    coalesce({{ clean_text('size') }}, 'N/A')          as size,
    lead_time_days,
    quantity_per_outer,
    coalesce(is_chiller_stock, false)                  as is_chiller_stock,
    tax_rate,
    unit_price,
    recommended_retail_price,
    typical_weight_per_unit
from {{ source('bronze', 'warehouse_stock_items') }}
{{ dedupe('stock_item_id', 'valid_from') }}
