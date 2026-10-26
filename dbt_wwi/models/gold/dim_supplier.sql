select
    s.supplier_id                  as supplier_key,
    s.supplier_name,
    sc.supplier_category_name      as supplier_category,
    ci.city_name                   as city,
    sp.state_province_name         as state_province,
    co.country_name                as country,
    s.payment_days,
    dm.delivery_method_name        as delivery_method,
    s.website_url
from {{ ref('slv_suppliers') }} s
left join {{ ref('slv_supplier_categories') }} sc on sc.supplier_category_id = s.supplier_category_id
left join {{ ref('slv_cities') }} ci              on ci.city_id = s.delivery_city_id
left join {{ ref('slv_state_provinces') }} sp     on sp.state_province_id = ci.state_province_id
left join {{ ref('slv_countries') }} co           on co.country_id = sp.country_id
left join {{ ref('slv_delivery_methods') }} dm    on dm.delivery_method_id = s.delivery_method_id
