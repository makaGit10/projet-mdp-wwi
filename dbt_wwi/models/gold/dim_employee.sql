select
    person_id       as employee_key,
    full_name       as employee_name,
    preferred_name,
    email_address,
    is_salesperson
from {{ ref('slv_people') }}
where is_employee
