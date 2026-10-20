// Power Query (M): loads route_diagnosis.csv from the configured output folder.
let
    // OutputFolder is a named cell on the Read Me sheet (default: <repo>\output\weekly\latest\).
    Folder = Excel.CurrentWorkbook(){[Name = "OutputFolder"]}[Content]{0}[Column1],
    FolderPath = if Text.EndsWith(Folder, "\") then Folder else Folder & "\",
    Source = Csv.Document(
        File.Contents(FolderPath & "route_diagnosis.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // en-US culture: the CSV always uses "." decimals and ISO dates, whatever the PC's regional settings.
    Typed = Table.TransformColumnTypes(Promoted, {
        {"route", type text}, {"origin_state", type text}, {"destination_state", type text},
        {"is_interstate", type logical}, {"delivered_orders", Int64.Type}, {"late_orders", Int64.Type},
        {"late_rate", type number}, {"late_rate_vs_overall", type number},
        {"median_delivery_days", type number}, {"product_value", type number},
        {"meets_min_sample", type logical}, {"sample_note", type text}, {"late_rate_rank", Int64.Type},
        {"min_route_sample", Int64.Type},
        {"as_of_date", type date}, {"window_start", type date}, {"window_end", type date}
    }, "en-US")
in
    Typed
