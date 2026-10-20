// Power Query (M): loads run_info.csv from the configured output folder.
let
    // OutputFolder is a named cell on the Read Me sheet (default: <repo>\output\weekly\latest\).
    Folder = Excel.CurrentWorkbook(){[Name = "OutputFolder"]}[Content]{0}[Column1],
    FolderPath = if Text.EndsWith(Folder, "\") then Folder else Folder & "\",
    Source = Csv.Document(
        File.Contents(FolderPath & "run_info.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // en-US culture: the CSV always uses "." decimals and ISO dates, whatever the PC's regional settings.
    Typed = Table.TransformColumnTypes(Promoted, {
        {"item", type text}, {"value", type text}
    }, "en-US")
in
    Typed
