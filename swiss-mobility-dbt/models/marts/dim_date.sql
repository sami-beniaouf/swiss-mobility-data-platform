-- Calendar dimension. Fabric Warehouse has no recursive CTEs or generate_series,
-- so the number sequence is built by cross-joining digits (0..9999).

with digits as (

    select n from (values (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) as v(n)

),

numbers as (

    select d1.n + d2.n * 10 + d3.n * 100 + d4.n * 1000 as n
    from digits d1
    cross join digits d2
    cross join digits d3
    cross join digits d4

),

dates as (

    select dateadd(day, n, cast('{{ var("date_spine_start") }}' as date)) as calendar_date
    from numbers
    where n < {{ var('date_spine_days') }}

)

select
    cast(convert(varchar(8), calendar_date, 112) as int)        as date_key,
    calendar_date,
    year(calendar_date)                                         as year,
    month(calendar_date)                                        as month,
    day(calendar_date)                                          as day_of_month,
    datepart(iso_week, calendar_date)                           as iso_week,
    -- 1900-01-01 was a Monday, so this gives Monday = 1 regardless of DATEFIRST
    (datediff(day, cast('1900-01-01' as date), calendar_date) % 7) + 1 as iso_weekday,
    case
        when (datediff(day, cast('1900-01-01' as date), calendar_date) % 7) >= 5 then 1
        else 0
    end                                                         as is_weekend
from dates
