// Power Query (M): loads reconciliation.csv from the configured output folder.
let
    // OutputFolder is a named cell on the Read Me sheet (default: <repo>\output\weekly\latest\).
    Folder = Excel.CurrentWorkbook(){[Name = "OutputFolder"]}[Content]{0}[Column1],
    FolderPath = if Text.EndsWith(Folder, "\") then Folder else Folder & "\",
    Source = Csv.Document(
        File.Contents(FolderPath & "reconciliation.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // en-US culture: the CSV always uses "." decimals and ISO dates, whatever the PC's regional settings.
    Typed = Table.TransformColumnTypes(Promoted, {
        {"check_order", Int64.Type}, {"check_name", type text}, {"source_a", type text},
        {"value_a", type number}, {"source_b", type text}, {"value_b", type number},
        {"difference", type number}, {"expected_difference", type number}, {"status", type text},
        {"note", type text},
        {"as_of_date", type date}, {"window_start", type date}, {"window_end", type date}
    }, "en-US")
in
    Typed
