-- Grain : un paiement recu d'un client (montant positif)
select
    customer_transaction_id                as payment_id,
    date_key,
    transaction_date                       as payment_date,
    customer_key,
    payment_method,
    abs(transaction_amount)                as payment_amount,
    abs(amount_excluding_tax)              as payment_amount_excl_tax
from {{ ref('fct_customer_transactions') }}
where transaction_type = 'Customer Payment Received'
