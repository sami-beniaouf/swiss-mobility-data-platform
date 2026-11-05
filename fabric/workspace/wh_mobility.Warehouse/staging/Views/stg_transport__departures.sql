create view [staging].[stg_transport__departures] as -- One row per unique scheduled departure.
-- The ingestion polls the stationboard every 15 minutes, so a departure is landed several
-- times; keep the latest poll because it carries the most recent delay.
--
-- Key (from notebooks/05_bronze_profiling.ipynb): station + category + line + scheduled time
-- + destination. Without the destination, branches of one line leaving at the same minute
-- (e.g. S21 to Trogen and to Appenzell at St. Gallen) would be merged into one departure.
-- The API sometimes lists one departure twice in the same poll, one copy with the delay and
-- one with the platform: the tie-break keeps the copy with a known delay, so the result is
-- deterministic.

with source as (

    select * from [lh_mobility].[dbo].[transport_stationboard]

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
            partition by station_id, category, line_number, departure_planned_utc, destination
            order by
                ingested_at_utc desc,
                case when delay_min is not null then 0 else 1 end,
                case when platform is not null then 0 else 1 end
        ) as poll_rank
    from typed

)

select
    convert(
        varchar(32),
        hashbytes(
            'MD5',
            concat_ws('|',
                coalesce(cast(station_id as varchar(200)), '_null_'),
                coalesce(cast(category as varchar(200)), '_null_'),
                coalesce(cast(line_number as varchar(200)), '_null_'),
                coalesce(cast(departure_planned_utc as varchar(200)), '_null_'),
                coalesce(cast(destination as varchar(200)), '_null_')
            )
        ),
        2
    ) as departure_id,
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
where poll_rank = 1;

GO