-- Grain : une ligne de facture (vente realisee)
select
    il.invoice_line_id,
    il.invoice_id,
    i.order_id,
    {{ date_key('i.invoice_date') }}  as date_key,
    i.invoice_date,
    i.customer_id                     as customer_key,
    il.stock_item_id                  as product_key,
    i.salesperson_person_id           as salesperson_key,
    dm.delivery_method_name           as delivery_method,
    i.is_credit_note,
    il.quantity,
    il.unit_price,
    il.tax_rate,
    il.amount_excl_tax                as revenue_excl_tax,
    il.tax_amount,
    il.extended_price                 as revenue_incl_tax,
    il.cost_amount,
    il.line_profit                    as profit
from {{ ref('slv_invoice_lines') }} il
join {{ ref('slv_invoices') }} i                on i.invoice_id = il.invoice_id
left join {{ ref('slv_delivery_methods') }} dm  on dm.delivery_method_id = i.delivery_method_id
