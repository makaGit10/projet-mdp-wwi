-- Grain : une ligne de bon de commande fournisseur
select
    pol.purchase_order_line_id,
    pol.purchase_order_id,
    {{ date_key('po.order_date') }}                              as date_key,
    po.order_date,
    po.expected_delivery_date,
    pol.last_receipt_date,
    po.supplier_id                                               as supplier_key,
    pol.stock_item_id                                            as product_key,
    pol.ordered_outers,
    pol.received_outers,
    pol.expected_unit_price_per_outer,
    pol.ordered_outers * pol.expected_unit_price_per_outer       as purchase_amount,
    pol.is_order_line_finalized                                  as is_finalized
from {{ ref('slv_purchase_order_lines') }} pol
join {{ ref('slv_purchase_orders') }} po on po.purchase_order_id = pol.purchase_order_id
