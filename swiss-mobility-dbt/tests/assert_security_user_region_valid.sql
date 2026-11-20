-- Singular test on the row-level security mapping: each user and region appears once, and
-- e-mail addresses are in lower case. An upper-case letter would never match
-- LOWER(USERPRINCIPALNAME()) in the semantic model, and the user would see no data.
-- Returns offending rows; the test fails if any are found.

select user_email, language_region, count(*) as row_count
from {{ ref('security_user_region') }}
group by user_email, language_region
having count(*) > 1
    or user_email <> lower(user_email)
