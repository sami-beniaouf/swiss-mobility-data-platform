-- One row per unique scheduled departure.
-- The notebook polls the stationboard repeatedly, so a departure is landed several
-- times; keep the latest poll because it carries the most recent delay.

with source as (

    select * from {{ source('bronze_transport', 'transport_stationboard') }}

),

typed as (

    select
        cast(station_id as varchar(20))                     as station_id,
        upper(trim(cast(category as varchar(10))))          as category,
        trim(cast(line_number as varchar(20)))              as line_number,
        trim(cast(operator as varchar(50)))                 as operator,
        trim(cast(destination as varchar(200)))             as destination,
        cast(departure_planned_utc as datetime2(6))         as departure_planned_utc,
        cast(delay_min as int)                              as delay_min,
        trim(cast(platform as varchar(10)))                 as platform,
        cast(_ingested_at as datetime2(6))                  as ingested_at_utc,
        _batch_id                                           as batch_id
    from source
    where station_id is not null
      and departure_planned_utc is not null

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by station_id, category, line_number, departure_planned_utc
            order by ingested_at_utc desc
        ) as poll_rank
    from typed

)

select
    {{ surrogate_key(['station_id', 'category', 'line_number', 'departure_planned_utc']) }} as departure_id,
    station_id,
    category,
    line_number,
    operator,
    destination,
    departure_planned_utc,
    -- Swiss local time for reporting (CET/CEST handled by the time zone rule)
    cast(
        departure_planned_utc at time zone 'UTC' at time zone 'W. Europe Standard Time'
        as datetime2(6)
    )                                                       as departure_planned_local,
    delay_min,
    platform,
    ingested_at_utc,
    batch_id
from deduplicated
where poll_rank = 1
