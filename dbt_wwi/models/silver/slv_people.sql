select
    person_id,
    {{ clean_text('full_name') }}            as full_name,
    {{ clean_text('preferred_name') }}       as preferred_name,
    lower({{ clean_text('email_address') }}) as email_address,
    {{ clean_text('phone_number') }}         as phone_number,
    coalesce(is_employee, false)             as is_employee,
    coalesce(is_salesperson, false)          as is_salesperson
from {{ source('bronze', 'application_people') }}
where person_id <> 1   -- compte technique "Data Conversion Only", pas une vraie personne
{{ dedupe('person_id', 'valid_from') }}
