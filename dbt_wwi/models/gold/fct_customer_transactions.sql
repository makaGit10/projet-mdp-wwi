-- Grain : une transaction financiere client (facture, paiement, avoir...)
select
    ct.customer_transaction_id,
    {{ date_key('ct.transaction_date') }}  as date_key,
    ct.transaction_date,
    ct.customer_id                         as customer_key,
    ct.invoice_id,
    tt.transaction_type_name               as transaction_type,
    coalesce(pm.payment_method_name, 'Aucun (facture)') as payment_method,
    ct.amount_excluding_tax,
    ct.tax_amount,
    ct.transaction_amount,
    ct.outstanding_balance,
    ct.is_finalized,
    ct.finalization_date
from {{ ref('slv_customer_transactions') }} ct
left join {{ ref('slv_transaction_types') }} tt on tt.transaction_type_id = ct.transaction_type_id
left join {{ ref('slv_payment_methods') }} pm    on pm.payment_method_id = ct.payment_method_id
