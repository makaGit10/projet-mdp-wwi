-- Calendrier couvrant toute la periode d'activite de Wide World Importers (2013-2016)
with spine as (
{% if target.type == 'snowflake' %}
    select dateadd(day, seq4(), '2013-01-01'::date) as d
    from table(generator(rowcount => 1461))
{% else %}
    select cast(unnest(generate_series(date '2013-01-01', date '2016-12-31', interval 1 day)) as date) as d
{% endif %}
),

base as (
    select
        d,
        {% if target.type == 'snowflake' %}dayofweekiso(d){% else %}isodow(d){% endif %} as dow
    from spine
)

select
    {{ date_key('d') }}                                 as date_key,
    d                                                   as full_date,
    year(d)                                             as year,
    quarter(d)                                          as quarter,
    'T' || quarter(d) || '-' || year(d)                 as quarter_label,
    month(d)                                            as month,
    case month(d)
        when 1 then 'Janvier' when 2 then 'Fevrier' when 3 then 'Mars' when 4 then 'Avril'
        when 5 then 'Mai' when 6 then 'Juin' when 7 then 'Juillet' when 8 then 'Aout'
        when 9 then 'Septembre' when 10 then 'Octobre' when 11 then 'Novembre' else 'Decembre'
    end                                                 as month_name,
    year(d) || '-' || lpad(cast(month(d) as varchar), 2, '0') as year_month,
    weekofyear(d)                                       as week_of_year,
    day(d)                                              as day_of_month,
    dow                                                 as day_of_week,
    case dow
        when 1 then 'Lundi' when 2 then 'Mardi' when 3 then 'Mercredi' when 4 then 'Jeudi'
        when 5 then 'Vendredi' when 6 then 'Samedi' else 'Dimanche'
    end                                                 as day_name,
    dow in (6, 7)                                       as is_weekend
from base
