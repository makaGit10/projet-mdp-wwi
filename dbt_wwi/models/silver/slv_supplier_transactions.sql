select
    supplier_transaction_id,
    supplier_id,
    transaction_type_id,
    purchase_order_id,
    payment_method_id,
    transaction_date,
    amount_excluding_tax,
    tax_amount,
    transaction_amount,
    outstanding_balance,
    coalesce(is_finalized, false) as is_finalized
from {{ source('bronze', 'purchasing_supplier_transactions') }}
{{ dedupe('supplier_transaction_id', 'last_edited_when') }}
