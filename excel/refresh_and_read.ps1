# Opens excel/olist_weekly_ops.xlsx in Excel desktop, runs Data > Refresh All (Workbook.RefreshAll),
# saves, and prints what the workbook now shows as JSON. Used by src/verify_excel_refresh.py; the
# workbook itself contains no macros.
#   powershell -ExecutionPolicy Bypass -File excel/refresh_and_read.ps1 [-ScreenshotDir reports/figures]
param([string]$ScreenshotDir = "")

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$path = Join-Path $here "olist_weekly_ops.xlsx"

function Export-RangePicture($wb, $sheetName, $address, $file) {
    $ws = $wb.Worksheets.Item($sheetName)
    $ws.Activate()
    $rng = $ws.Range($address)
    [void]$rng.CopyPicture(1, 2)   # xlScreen, xlBitmap
    $co = $ws.ChartObjects().Add(0, 0, $rng.Width, $rng.Height)
    $co.Activate()
    [void]$co.Chart.Paste()
    [void]$co.Chart.Export($file)
    $co.Delete()
}

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($path)
    $started = Get-Date
    $wb.RefreshAll()
    $xl.CalculateUntilAsyncQueriesDone()
    $xl.CalculateFull()
    $seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)

    $result = [ordered]@{ refresh_seconds = $seconds }
    $rm = $wb.Worksheets.Item("Read Me")
    $result.output_folder = $rm.Range("B6").Text
    $result.loaded_cutoff = $rm.Range("B8").Text
    $result.loaded_window = $rm.Range("B9").Text
    $result.reconciliation_text = $rm.Range("B11").Text

    $sum = $wb.Worksheets.Item("Weekly Summary").ListObjects.Item("tblWeeklySummary")
    $metrics = [ordered]@{}
    foreach ($row in $sum.ListRows) {
        $metrics[[string]$row.Range.Cells.Item(1, 3).Value2] = $row.Range.Cells.Item(1, 5).Value2
    }
    $result.summary = $metrics
    $result.summary_display_late_rate = ($sum.ListRows | Where-Object { $_.Range.Cells.Item(1, 3).Value2 -eq "Late rate" } |
        ForEach-Object { $_.Range.Cells.Item(1, 4).Text })

    $ex = $wb.Worksheets.Item("Exceptions").ListObjects.Item("tblExceptions")
    $result.exceptions_rows = $ex.ListRows.Count
    $result.exceptions_product_value = $xl.WorksheetFunction.Sum($ex.ListColumns.Item("product_value").DataBodyRange)
    $result.exceptions_first_order = $ex.ListColumns.Item("order_id").DataBodyRange.Cells.Item(1, 1).Value2
    $result.exceptions_as_of = $ex.ListColumns.Item("as_of_date").DataBodyRange.Cells.Item(1, 1).Text

    $rd = $wb.Worksheets.Item("Route Diagnosis").ListObjects.Item("tblRouteDiagnosis")
    $result.route_rows = $rd.ListRows.Count
    $result.route_delivered_total = $xl.WorksheetFunction.Sum($rd.ListColumns.Item("delivered_orders").DataBodyRange)
    $result.route_ranked = $xl.WorksheetFunction.Count($rd.ListColumns.Item("late_rate_rank").DataBodyRange)

    $rc = $wb.Worksheets.Item("Reconciliation").ListObjects.Item("tblReconciliation")
    $result.reconciliation_rows = $rc.ListRows.Count
    $result.reconciliation_pass = $xl.WorksheetFunction.CountIf($rc.ListColumns.Item("status").DataBodyRange, "PASS")

    $pt = $wb.Worksheets.Item("Exception Pivot").PivotTables("ptExceptions")
    $result.pivot_orders_total = $pt.GetPivotData("Orders").Value2
    $result.pivot_product_value_total = $pt.GetPivotData("Product value (BRL)").Value2
    $result.pivot_refreshed = $pt.RefreshDate.ToString("s")

    if ($ScreenshotDir) {
        $dir = (Resolve-Path $ScreenshotDir).Path
        Export-RangePicture $wb "Weekly Summary" "A1:G27" (Join-Path $dir "excel_weekly_summary.png")
        Export-RangePicture $wb "Exception Pivot" "A1:D22" (Join-Path $dir "excel_exception_pivot.png")
        Export-RangePicture $wb "Exceptions" "A1:L16" (Join-Path $dir "excel_exceptions.png")
        Export-RangePicture $wb "Reconciliation" "A1:I20" (Join-Path $dir "excel_reconciliation.png")
        $result.screenshots = $dir
    }
    $wb.RemovePersonalInformation = $true   # no Office user name in author / pivot metadata
    $wb.Worksheets.Item("Read Me").Activate()
    $wb.Save()
    $result | ConvertTo-Json -Depth 4
}
finally {
    if ($wb) { $wb.Close($false) }
    $xl.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
}
