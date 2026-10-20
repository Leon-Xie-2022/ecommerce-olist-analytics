// Power Query (M): loads exceptions.csv from the configured output folder.
let
    // OutputFolder is a named cell on the Read Me sheet (default: <repo>\output\weekly\latest\).
    Folder = Excel.CurrentWorkbook(){[Name = "OutputFolder"]}[Content]{0}[Column1],
    FolderPath = if Text.EndsWith(Folder, "\") then Folder else Folder & "\",
    Source = Csv.Document(
        File.Contents(FolderPath & "exceptions.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    // en-US culture: the CSV always uses "." decimals and ISO dates, whatever the PC's regional settings.
    Typed = Table.TransformColumnTypes(Promoted, {
        {"priority_rank", Int64.Type}, {"priority", type text}, {"exception_type", type text},
        {"rule_id", type text}, {"rule_reason", type text}, {"order_id", type text},
        {"purchase_date", type date}, {"estimated_delivery_date", type date}, {"days_overdue", Int64.Type},
        {"ship_by_date", type date}, {"approved_by_cutoff", type logical},
        {"carrier_handover_date", type date}, {"became_overdue_this_window", type logical},
        {"n_items", Int64.Type}, {"n_sellers", Int64.Type}, {"seller_id", type text},
        {"seller_attribution", type text}, {"origin_states", type text}, {"customer_state", type text},
        {"product_value", type number}, {"freight_value", type number}, {"payment_value", type number},
        {"evidence", type text}, {"suggested_action", type text},
        {"as_of_date", type date}, {"window_start", type date}, {"window_end", type date}
    }, "en-US")
in
    Typed
