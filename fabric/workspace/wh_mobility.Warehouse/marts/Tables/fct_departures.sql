CREATE TABLE [marts].[fct_departures] (
    [departure_id]            VARCHAR (32)  NULL,
    [station_id]              VARCHAR (20)  NULL,
    [line_key]                VARCHAR (32)  NULL,
    [date_key]                INT           NULL,
    [departure_planned_local] DATETIME2 (6) NULL,
    [departure_hour_local]    INT           NULL,
    [destination]             VARCHAR (200) NULL,
    [platform]                VARCHAR (10)  NULL,
    [delay_min]               INT           NULL,
    [has_realtime]            INT           NOT NULL,
    [is_punctual]             INT           NULL
);


GO