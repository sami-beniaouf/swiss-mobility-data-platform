-- Departures enriched with mode and punctuality flags.
-- Punctuality rule follows the Swiss convention: a departure counts as punctual
-- when it leaves less than var('punctuality_threshold_min') minutes late.

with departures as (

    select * from {{ ref('stg_transport__departures') }}

),

categories as (

    select * from {{ ref('transport_categories') }}

)

select
    d.departure_id,
    d.station_id,
    d.category,
    d.line_number,
    d.operator,
    d.destination,
    coalesce(c.transport_mode, 'other')                         as transport_mode,
    d.departure_planned_utc,
    d.departure_planned_local,
    cast(d.departure_planned_local as date)                     as departure_date_local,
    datepart(hour, d.departure_planned_local)                   as departure_hour_local,
    d.delay_min,
    case when d.delay_min is not null then 1 else 0 end         as has_realtime,
    case
        when d.delay_min is null then null
        when d.delay_min < {{ var('punctuality_threshold_min') }} then 1
        else 0
    end                                                         as is_punctual,
    d.platform
from departures d
left join categories c
    on d.category = c.category
