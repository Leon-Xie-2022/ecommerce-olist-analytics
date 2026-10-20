# Builds excel/olist_weekly_ops.xlsx with Excel desktop (COM automation, Windows only).
#
# The workbook gets real Power Query queries (excel/power_query/*.pq), tables loaded from them, a pivot
# table on the Exceptions query and a named parameter cell OutputFolder. No macros are stored in the
# workbook: after this one-off build, the user only needs Data > Refresh All.
#
# Run from the project root after src/weekly_report.py has published output/weekly/latest/:
#   powershell -ExecutionPolicy Bypass -File excel/build_workbook.ps1
# Re-running it rebuilds the workbook from scratch (any manual edits to the .xlsx are lost).

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $here "olist_weekly_ops.xlsx"
$queryDir = Join-Path $here "power_query"
$missing = [Type]::Missing
function Step($text) { Write-Output ("{0:HH:mm:ss}  {1}" -f (Get-Date), $text) }

# Sheet name, query name, table name, header row of the table
$tables = @(
    @{ Sheet = "Weekly Summary";  Query = "WeeklySummary";  Table = "tblWeeklySummary";  Row = 4 },
    @{ Sheet = "Route Diagnosis"; Query = "RouteDiagnosis"; Table = "tblRouteDiagnosis"; Row = 4 },
    @{ Sheet = "Exceptions";      Query = "Exceptions";     Table = "tblExceptions";     Row = 4 },
    @{ Sheet = "Reconciliation";  Query = "Reconciliation"; Table = "tblReconciliation"; Row = 4 },
    @{ Sheet = "Run Info";        Query = "RunInfo";        Table = "tblRunInfo";        Row = 4 }
)
$notes = @{
    "Weekly Summary"  = "One row per metric. Sections A-D use different populations; see the definition column and the Read Me sheet."
    "Route Diagnosis" = "Deliveries completed in the window by seller state -> customer state. Routes below the minimum sample are shown but not ranked."
    "Exceptions"      = "Follow-up list at the cut-off, one row per order. Actions are suggestions; no owner or outcome is recorded. Use the filter buttons."
    "Reconciliation"  = "Each row compares two independently computed numbers. The run is only published when every status is PASS."
    "Run Info"        = "Parameters, code version and input checksums of the loaded run."
}

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Add()
    while ($wb.Worksheets.Count -lt 7) { [void]$wb.Worksheets.Add([Type]::Missing, $wb.Worksheets.Item($wb.Worksheets.Count)) }
    $names = @("Read Me", "Weekly Summary", "Route Diagnosis", "Exceptions", "Exception Pivot", "Reconciliation", "Run Info")
    for ($i = 0; $i -lt $names.Count; $i++) { $wb.Worksheets.Item($i + 1).Name = $names[$i] }

    Step "sheets created"
    # ---- Read Me -------------------------------------------------------------------------------
    $rm = $wb.Worksheets.Item("Read Me")
    $rows = @(
        @("Olist weekly delivery operations report", ""),
        @("Independent practice project on public historical data (2016-2018). Simulated requirements: no real client, users or go-live.", ""),
        @("", ""),
        @("Parameters", ""),
        @("Setting", "Value"),
        @("Output folder (Power Query source)", ""),
        @("", "Default = <project>\output\weekly\latest\ next to this workbook's excel\ folder. To use another folder, type its full path over the formula."),
        @("Loaded cut-off date", ""),
        @("Loaded window", ""),
        @("Loaded run ID", ""),
        @("Reconciliation", ""),
        @("", ""),
        @("How to refresh", ""),
        @("1", "In the project folder run:  python src/weekly_report.py --as-of YYYY-MM-DD   (publishes output\weekly\latest\ only if all checks pass)"),
        @("2", "In Excel: Data > Refresh All. All tables and the pivot reload from the latest CSVs; check that 'Loaded cut-off date' above changed."),
        @("3", "Open the Reconciliation sheet: every status should be PASS. Numbers equal the CSV/SQL output of the same run."),
        @("", ""),
        @("Definitions", ""),
        @("Cut-off", "End of the cut-off day: only events timestamped before the next day 00:00 are used. Order status is never used (the data keep only the status at extraction)."),
        @("Window", "The window_days calendar days ending on the cut-off date, both ends inclusive (dataset-local dates, no time-zone conversion)."),
        @("Deliveries completed", "Orders delivered in the window. Late = delivered on a later calendar day than the estimated date."),
        @("Open orders", "Purchased by the cut-off with no delivery recorded. 'Not yet due' orders have an unknown outcome and are never counted as on time."),
        @("Exceptions", "Overdue rules R1-R3 (priority P1-P3 by days overdue) and early-warning rule R4 (P4). Suggested actions only."),
        @("Money", "product_value = item prices, freight_value, payment_value (BRL). None of them is company revenue."),
        @("Limits", "Cancellation dates are not in the data, so a listed order may already have been cancelled at the cut-off. Historical replay, not a live system."),
        @("", ""),
        @("Sheets", ""),
        @("Weekly Summary", "Headline metrics of the loaded week"),
        @("Route Diagnosis", "Late rate by route with sample-size flag"),
        @("Exceptions", "Ranked follow-up list with evidence and suggested action"),
        @("Exception Pivot", "Pivot table of exceptions by priority and rule (refreshes with the query)"),
        @("Reconciliation", "Checks against the existing data mart and between grains"),
        @("Run Info", "Parameters, code version and input checksums")
    )
    for ($r = 0; $r -lt $rows.Count; $r++) {
        $rm.Cells.Item($r + 1, 1).Value2 = $rows[$r][0]
        $rm.Cells.Item($r + 1, 2).Value2 = $rows[$r][1]
    }
    $rm.Range("A1").Font.Size = 16; $rm.Range("A1").Font.Bold = $true
    $rm.Range("A2").Font.Italic = $true
    foreach ($a in @("A4", "A13", "A18", "A27")) { $rm.Range($a).Font.Bold = $true; $rm.Range($a).Font.Size = 12 }
    $rm.Range("A5:B5").Font.Bold = $true
    $rm.Range("A5:B5").Interior.Color = 0xEFE2D9   # light blue (BGR)
    $rm.Range("B6").Formula = '=LEFT(CELL("filename",A1),FIND("[",CELL("filename",A1))-1)&"..\output\weekly\latest\"'
    $rm.Range("B6").Interior.Color = 0xCCF2FF      # light yellow: editable parameter
    $rm.Range("B7").Font.Italic = $true; $rm.Range("B7").Font.Size = 9
    [void]$wb.Names.Add("OutputFolder", "='Read Me'!`$B`$6")
    $rm.Columns.Item(1).ColumnWidth = 34
    $rm.Columns.Item(2).ColumnWidth = 120
    $rm.Range("B1:B40").WrapText = $true
    $rm.Range("A1:B40").VerticalAlignment = -4160   # top

    Step "Read Me written"
    $wb.SaveAs($target, 51)   # xlOpenXMLWorkbook; saving first lets CELL("filename") resolve
    $xl.CalculateFull()

    Step "saved"
    # ---- Queries and tables --------------------------------------------------------------------
    foreach ($t in $tables) {
        $formula = Get-Content -Raw -Encoding UTF8 (Join-Path $queryDir ($t.Query + ".pq"))
        [void]$wb.Queries.Add($t.Query, $formula)
        $ws = $wb.Worksheets.Item($t.Sheet)
        $ws.Cells.Item(1, 1).Value2 = $t.Sheet
        $ws.Cells.Item(1, 1).Font.Size = 14; $ws.Cells.Item(1, 1).Font.Bold = $true
        $ws.Cells.Item(2, 1).Value2 = $notes[$t.Sheet]
        $ws.Cells.Item(2, 1).Font.Italic = $true
        $conn = "OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=`$Workbook`$;Location=$($t.Query);Extended Properties="""""
        $lo = $ws.ListObjects.Add(0, $conn, $missing, 1, $ws.Cells.Item($t.Row, 1))
        $qt = $lo.QueryTable
        $qt.CommandType = 2          # xlCmdSql
        $qt.CommandText = "SELECT * FROM [$($t.Query)]"
        $qt.BackgroundQuery = $false # Refresh All waits for each query, so the pivot refreshes after its data
        $qt.PreserveFormatting = $true
        $qt.RefreshStyle = 1         # xlInsertDeleteCells
        $qt.AdjustColumnWidth = $true
        $qt.WorkbookConnection.Name = "Query - $($t.Query)"
        $lo.Name = $t.Table
        $lo.TableStyle = "TableStyleMedium2"
        Step "refreshing $($t.Query)"
        [void]$qt.Refresh($false)
        $qt.AdjustColumnWidth = $false
    }

    function Set-Format($sheet, $table, $columns, $format) {
        $lo = $wb.Worksheets.Item($sheet).ListObjects.Item($table)
        foreach ($c in $columns) { $lo.ListColumns.Item($c).Range.NumberFormat = $format }
    }
    $money = "#,##0.00"; $pct = "0.0%"; $int = "#,##0"; $day = "yyyy-mm-dd"; $pp = "+0.0%;-0.0%;0.0%"
    $dates = @("as_of_date", "window_start", "window_end")
    Set-Format "Weekly Summary" "tblWeeklySummary" @("value") "General"
    Set-Format "Weekly Summary" "tblWeeklySummary" $dates $day
    Set-Format "Route Diagnosis" "tblRouteDiagnosis" @("delivered_orders", "late_orders") $int
    Set-Format "Route Diagnosis" "tblRouteDiagnosis" @("late_rate") $pct
    Set-Format "Route Diagnosis" "tblRouteDiagnosis" @("late_rate_vs_overall") $pp
    Set-Format "Route Diagnosis" "tblRouteDiagnosis" @("product_value") $money
    Set-Format "Route Diagnosis" "tblRouteDiagnosis" $dates $day
    Set-Format "Exceptions" "tblExceptions" @("purchase_date", "estimated_delivery_date", "ship_by_date", "carrier_handover_date") $day
    Set-Format "Exceptions" "tblExceptions" @("product_value", "freight_value", "payment_value") $money
    Set-Format "Exceptions" "tblExceptions" $dates $day
    Set-Format "Reconciliation" "tblReconciliation" @("value_a", "value_b", "difference", "expected_difference") "#,##0.00"
    Set-Format "Reconciliation" "tblReconciliation" $dates $day

    # Readable widths for long text columns
    $ex = $wb.Worksheets.Item("Exceptions").ListObjects.Item("tblExceptions")
    foreach ($c in @("rule_reason", "evidence", "suggested_action")) { $ex.ListColumns.Item($c).Range.ColumnWidth = 48 }
    foreach ($c in @("order_id", "seller_id")) { $ex.ListColumns.Item($c).Range.ColumnWidth = 34 }
    $ws = $wb.Worksheets.Item("Weekly Summary").ListObjects.Item("tblWeeklySummary")
    $ws.ListColumns.Item("definition").Range.ColumnWidth = 70
    $ws.ListColumns.Item("display_value").Range.HorizontalAlignment = -4152   # right
    $ws.ListColumns.Item("display_value").Range.ColumnWidth = 18
    $ws.ListColumns.Item("section").Range.ColumnWidth = 32

    # PASS/FAIL colouring on Reconciliation (conditional format on the whole status column)
    $st = $wb.Worksheets.Item("Reconciliation").ListObjects.Item("tblReconciliation").ListColumns.Item("status").DataBodyRange
    $fc = $st.FormatConditions.Add(1, 3, '="PASS"'); $fc.Interior.Color = 0xCEEFC6
    $fc = $st.FormatConditions.Add(1, 4, '="PASS"'); $fc.Interior.Color = 0xCEC7FF

    foreach ($t in $tables) {
        $ws = $wb.Worksheets.Item($t.Sheet)
        $ws.Activate()
        $xl.ActiveWindow.FreezePanes = $false
        [void]$ws.Cells.Item($t.Row + 1, 1).Select()
        $xl.ActiveWindow.FreezePanes = $true
    }

    Step "tables formatted"
    # Loaded-run cells on Read Me (structured references need the tables to exist first)
    $rm.Range("B8").Formula = '=IFERROR(INDEX(tblRunInfo[value],MATCH("Cut-off date (as_of_date)",tblRunInfo[item],0)),"(not loaded - Refresh All)")'
    $rm.Range("B9").Formula = '=IFERROR(INDEX(tblRunInfo[value],MATCH("Window start (inclusive)",tblRunInfo[item],0))&" to "&INDEX(tblRunInfo[value],MATCH("Window end (inclusive)",tblRunInfo[item],0))&" (both inclusive)","")'
    $rm.Range("B10").Formula = '=IFERROR(INDEX(tblRunInfo[value],MATCH("Run ID",tblRunInfo[item],0)),"")'
    $rm.Range("B11").Formula = '=IFERROR(COUNTIF(tblReconciliation[status],"PASS")&" of "&ROWS(tblReconciliation[status])&" checks PASS","")'
    # ---- Pivot table on the Exceptions query ---------------------------------------------------
    $pv = $wb.Worksheets.Item("Exception Pivot")
    $pv.Cells.Item(1, 1).Value2 = "Exception Pivot"
    $pv.Cells.Item(1, 1).Font.Size = 14; $pv.Cells.Item(1, 1).Font.Bold = $true
    $pv.Cells.Item(2, 1).Value2 = "Exceptions by priority and rule. Built on the Exceptions query connection, so Refresh All updates it."
    $pv.Cells.Item(2, 1).Font.Italic = $true
    $cache = $wb.PivotCaches().Create(2, $wb.Connections.Item("Query - Exceptions"), 6)   # xlExternal
    $pt = $cache.CreatePivotTable($pv.Range("A4"), "ptExceptions")
    $pt.PivotFields("priority").Orientation = 1     # row
    $pt.PivotFields("priority").Position = 1
    $pt.PivotFields("rule_id").Orientation = 1
    $pt.PivotFields("rule_id").Position = 2
    $f = $pt.AddDataField($pt.PivotFields("order_id"), "Orders", -4112)              # xlCount
    $f = $pt.AddDataField($pt.PivotFields("product_value"), "Product value (BRL)", -4157)  # xlSum
    $f.NumberFormat = $money
    $pt.DataPivotField.Orientation = 2              # values as columns
    $pt.RowAxisLayout(1)                            # tabular
    $pt.PivotCache().RefreshOnFileOpen = $false
    $wb.Connections.Item("Query - Exceptions").OLEDBConnection.BackgroundQuery = $false

    $wb.Worksheets.Item("Read Me").Activate()
    $wb.Save()
    Write-Output "built $target"
}
finally {
    if ($wb) { $wb.Close($true) }
    $xl.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
