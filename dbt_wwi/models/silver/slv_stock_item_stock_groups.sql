select stock_item_stock_group_id, stock_item_id, stock_group_id
from {{ source('bronze', 'warehouse_stock_item_stock_groups') }}
{{ dedupe('stock_item_stock_group_id', 'last_edited_when') }}
