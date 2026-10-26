select
    stock_group_id,
    {{ clean_text('stock_group_name') }} as stock_group_name
from {{ source('bronze', 'warehouse_stock_groups') }}
{{ dedupe('stock_group_id', 'valid_from') }}
