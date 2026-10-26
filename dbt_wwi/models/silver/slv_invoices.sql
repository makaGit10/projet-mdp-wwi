select
    invoice_id,
    customer_id,
    bill_to_customer_id,
    order_id,
    delivery_method_id,
    salesperson_person_id,
    invoice_date,
    coalesce(is_credit_note, false) as is_credit_note,
    total_dry_items,
    total_chiller_items,
    confirmed_delivery_time
from {{ source('bronze', 'sales_invoices') }}
{{ dedupe('invoice_id', 'last_edited_when') }}
