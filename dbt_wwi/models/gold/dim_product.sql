-- Un article peut appartenir a plusieurs groupes de stock : on retient le premier par ordre alphabetique
with main_group as (
    select sisg.stock_item_id, min(sg.stock_group_name) as stock_group
    from {{ ref('slv_stock_item_stock_groups') }} sisg
    join {{ ref('slv_stock_groups') }} sg on sg.stock_group_id = sisg.stock_group_id
    group by sisg.stock_item_id
)

select
    si.stock_item_id                         as product_key,
    si.stock_item_name                       as product_name,
    coalesce(mg.stock_group, 'Non classe')   as stock_group,
    si.brand,
    si.size,
    coalesce(col.color_name, 'N/A')          as color,
    up.package_type_name                     as unit_package,
    op.package_type_name                     as outer_package,
    s.supplier_name,
    si.is_chiller_stock,
    si.unit_price,
    si.recommended_retail_price,
    si.tax_rate,
    si.lead_time_days,
    si.quantity_per_outer,
    si.typical_weight_per_unit
from {{ ref('slv_stock_items') }} si
left join main_group mg                          on mg.stock_item_id = si.stock_item_id
left join {{ ref('slv_colors') }} col            on col.color_id = si.color_id
left join {{ ref('slv_package_types') }} up      on up.package_type_id = si.unit_package_id
left join {{ ref('slv_package_types') }} op      on op.package_type_id = si.outer_package_id
left join {{ ref('slv_suppliers') }} s           on s.supplier_id = si.supplier_id
