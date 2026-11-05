CREATE TABLE [marts].[dim_station] (
    [station_id]          VARCHAR (20)    NULL,
    [station_name]        VARCHAR (200)   NULL,
    [municipality_bfs_nr] INT             NULL,
    [canton_code]         VARCHAR (16)    NULL,
    [canton_name]         VARCHAR (100)   NULL,
    [language_region]     VARCHAR (20)    NULL,
    [lv95_e]              DECIMAL (10, 2) NULL,
    [lv95_n]              DECIMAL (10, 2) NULL
);


GO