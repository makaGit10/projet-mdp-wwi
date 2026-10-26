select
    customer_id,
    {{ clean_text('customer_name') }}         as customer_name,
    bill_to_customer_id,
    customer_category_id,
    buying_group_id,
    primary_contact_person_id,
    delivery_method_id,
    delivery_city_id,
    coalesce(credit_limit, 0)                 as credit_limit,
    account_opened_date,
    coalesce(standard_discount_percentage, 0) as standard_discount_percentage,
    coalesce(is_on_credit_hold, false)        as is_on_credit_hold,
    payment_days,
    customer_id = bill_to_customer_id         as is_head_office,
    {{ clean_text('delivery_postal_code') }}  as delivery_postal_code
from {{ source('bronze', 'sales_customers') }}
{{ dedupe('customer_id', 'valid_from') }}
