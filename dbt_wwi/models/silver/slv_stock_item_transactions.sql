select
    stock_item_transaction_id,
    stock_item_id,
    transaction_type_id,
    customer_id,
    supplier_id,
    invoice_id,
    purchase_order_id,
    transaction_occurred_when,
    quantity
from {{ source('bronze', 'warehouse_stock_item_transactions') }}
{{ dedupe('stock_item_transaction_id', 'last_edited_when') }}
