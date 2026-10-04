select
    upper(trim(cast(canton_code as varchar(2))))    as canton_code,
    trim(cast(canton_name as varchar(100)))         as canton_name,
    trim(cast(language_region as varchar(20)))      as language_region
from {{ source('bronze_oracle', 'oracle_cantons') }}
