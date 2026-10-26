select
    c.customer_id                                  as customer_key,
    c.customer_name,
    bill_to.customer_name                          as bill_to_customer_name,
    c.is_head_office,
    cat.customer_category_name                     as customer_category,
    coalesce(bg.buying_group_name, 'Independant')  as buying_group,
    ci.city_name                                   as city,
    sp.state_province_name                         as state_province,
    sp.sales_territory,
    co.country_name                                as country,
    co.continent,
    c.credit_limit,
    c.payment_days,
    c.standard_discount_percentage,
    c.is_on_credit_hold,
    c.account_opened_date,
    dm.delivery_method_name                        as delivery_method
from {{ ref('slv_customers') }} c
left join {{ ref('slv_customers') }} bill_to        on bill_to.customer_id = c.bill_to_customer_id
left join {{ ref('slv_customer_categories') }} cat  on cat.customer_category_id = c.customer_category_id
left join {{ ref('slv_buying_groups') }} bg         on bg.buying_group_id = c.buying_group_id
left join {{ ref('slv_cities') }} ci                on ci.city_id = c.delivery_city_id
left join {{ ref('slv_state_provinces') }} sp       on sp.state_province_id = ci.state_province_id
left join {{ ref('slv_countries') }} co             on co.country_id = sp.country_id
left join {{ ref('slv_delivery_methods') }} dm      on dm.delivery_method_id = c.delivery_method_id
