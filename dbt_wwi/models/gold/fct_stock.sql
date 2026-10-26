-- Grain : un article (photo actuelle du stock)
select
    h.stock_item_id                                   as product_key,
    h.quantity_on_hand,
    h.bin_location,
    h.reorder_level,
    h.target_stock_level,
    h.last_cost_price,
    h.quantity_on_hand * h.last_cost_price            as stock_value,
    h.quantity_on_hand <= h.reorder_level             as is_below_reorder_level
from {{ ref('slv_stock_item_holdings') }} h
