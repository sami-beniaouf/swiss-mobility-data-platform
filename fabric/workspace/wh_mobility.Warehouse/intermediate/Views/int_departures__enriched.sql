create view [intermediate].[int_departures__enriched] as -- Departures that have taken place, enriched with mode and punctuality flags.
-- Punctuality rule follows the Swiss convention: a departure counts as punctual
-- when it leaves less than var('punctuality_threshold_min') minutes late.
--
-- Each poll also returns departures still in the future, whose delay is only a forecast
-- (mostly 0 or unknown). A departure is kept once its actual departure time (planned time
-- plus the last known delay) is before the latest poll; later runs add it once it has left.

with all_departures as (

    select * from [wh_mobility].[staging].[stg_transport__departures]

),

departures as (

    select *
    from all_departures
    where dateadd(minute, coalesce(delay_min, 0), departure_planned_utc)
          < (select max(ingested_at_utc) from all_departures)

),

categories as (

    select * from [wh_mobility].[reference].[transport_categories]

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
        when d.delay_min < 3 then 1
        else 0
    end                                                         as is_punctual,
    d.platform
from departures d
left join categories c
    on d.category = c.category;

GO