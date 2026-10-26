-- Grain : une ligne de commande client
select
    ol.order_line_id,
    ol.order_id,
    {{ date_key('o.order_date') }}             as date_key,
    o.order_date,
    o.expected_delivery_date,
    o.customer_id                              as customer_key,
    ol.stock_item_id                           as product_key,
    o.salesperson_person_id                    as salesperson_key,
    ol.quantity                                as ordered_quantity,
    ol.picked_quantity,
    ol.unit_price,
    ol.quantity * ol.unit_price                as order_amount_excl_tax,
    o.backorder_order_id is not null           as has_backorder,
    o.picking_completed_when is not null       as is_picking_completed
from {{ ref('slv_order_lines') }} ol
join {{ ref('slv_orders') }} o on o.order_id = ol.order_id
