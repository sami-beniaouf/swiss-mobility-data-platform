-- Current station list: the latest daily snapshot exported from the Oracle hub.

with source as (

    select * from {{ source('bronze_oracle', 'oracle_stations') }}

),

latest as (

    select * from source
    where _batch_id = (select max(_batch_id) from source)

)

select
    cast(station_id as varchar(20))               as station_id,
    trim(cast(station_name as varchar(200)))      as station_name,
    cast(municipality_bfs_nr as int)              as municipality_bfs_nr,
    upper(trim(cast(canton_code as varchar(2))))  as canton_code,
    cast(lv95_e as decimal(10, 2))                as lv95_e,
    cast(lv95_n as decimal(10, 2))                as lv95_n
from latest
