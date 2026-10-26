select
    invoice_line_id,
    invoice_id,
    stock_item_id,
    package_type_id,
    quantity,
    unit_price,
    tax_rate,
    tax_amount,
    extended_price,                                   -- montant TTC
    extended_price - tax_amount               as amount_excl_tax,
    line_profit,
    extended_price - tax_amount - line_profit as cost_amount
from {{ source('bronze', 'sales_invoice_lines') }}
{{ dedupe('invoice_line_id', 'last_edited_when') }}
