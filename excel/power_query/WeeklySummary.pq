// Power Query (M): loads weekly_summary.csv from the configured output folder.
let
    // OutputFolder is a named cell on the Read Me sheet (default: <repo>\output\weekly\latest\).
    Folder = Excel.CurrentWorkbook(){[Name = "OutputFolder"]}[Content]{0}[Column1],
    FolderPath = if Text.EndsWith(Folder, "\") then Folder else Folder & "\",
    Source = Csv.Document(
        File.Contents(FolderPath & "weekly_summary.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // en-US culture: the CSV always uses "." decimals and ISO dates, whatever the PC's regional settings.
    Typed = Table.TransformColumnTypes(Promoted, {
        {"metric_order", Int64.Type}, {"section", type text}, {"metric", type text},
        {"value", type number}, {"unit", type text}, {"definition", type text},
        {"as_of_date", type date}, {"window_start", type date}, {"window_end", type date}
    }, "en-US"),
    // Text version of value formatted by its unit, for readers; the numeric value column stays for checks.
    Display = Table.AddColumn(Typed, "display_value", each
        if [value] = null then ""
        else if [unit] = "BRL" then "BRL " & Number.ToText([value], "N2", "en-US")
        else if [unit] = "rate" then Number.ToText([value], "P1", "en-US")
        else if [unit] = "days" then Number.ToText([value], "N1", "en-US")
        else Number.ToText([value], "N0", "en-US"),
        type text),
    Reordered = Table.ReorderColumns(Display, {"metric_order", "section", "metric", "display_value", "value",
        "unit", "definition", "as_of_date", "window_start", "window_end"})
in
    Reordered
