CREATE TABLE [marts].[dim_date] (
    [date_key]      INT  NULL,
    [calendar_date] DATE NULL,
    [year]          INT  NULL,
    [month]         INT  NULL,
    [day_of_month]  INT  NULL,
    [iso_week]      INT  NULL,
    [iso_weekday]   INT  NULL,
    [is_weekend]    INT  NOT NULL
);


GO