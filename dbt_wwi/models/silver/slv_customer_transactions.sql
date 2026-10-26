select
    customer_transaction_id,
    customer_id,
    transaction_type_id,
    invoice_id,
    payment_method_id,
    transaction_date,
    amount_excluding_tax,
    tax_amount,
    transaction_amount,
    outstanding_balance,
    finalization_date,
    coalesce(is_finalized, false) as is_finalized
from {{ source('bronze', 'sales_customer_transactions') }}
{{ dedupe('customer_transaction_id', 'last_edited_when') }}
