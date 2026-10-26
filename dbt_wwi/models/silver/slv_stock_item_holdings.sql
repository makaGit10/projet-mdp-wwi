select
    stock_item_id,
    greatest(quantity_on_hand, 0)    as quantity_on_hand,
    {{ clean_text('bin_location') }} as bin_location,
    last_stocktake_quantity,
    last_cost_price,
    reorder_level,
    target_stock_level
from {{ source('bronze', 'warehouse_stock_item_holdings') }}
{{ dedupe('stock_item_id', 'last_edited_when') }}
