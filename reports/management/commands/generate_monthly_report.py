from collections import defaultdict
from calendar import monthrange
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)

from marketdata.models import DailyPrice
from scanners.models import ScanRun


class Command(BaseCommand):
    help = "Generate robust Priyan Scanner monthly report"

    def add_arguments(self, parser):
        parser.add_argument(
            "--month",
            type=str,
            help="Report month in YYYY-MM format. Example: 2026-09",
        )

    def parse_month(self, value):
        if not value:
            today = timezone.localdate()
            return today.year, today.month

        try:
            year, month = map(int, value.split("-"))
            if month < 1 or month > 12:
                raise ValueError
            return year, month
        except (ValueError, AttributeError):
            raise ValueError(
                "Invalid month. Use YYYY-MM, for example 2026-09."
            )

    def get_daily_runs(self, scan_type, start_date, end_date):
        runs = (
            ScanRun.objects
            .filter(
                scan_type=scan_type,
                scan_date__gte=start_date,
                scan_date__lte=end_date,
            )
            .prefetch_related("results__stock")
            .order_by("-scan_date", "-created_at")
        )

        latest_by_date = {}

        for run in runs:
            if run.scan_date not in latest_by_date:
                latest_by_date[run.scan_date] = run

        return dict(
            sorted(
                latest_by_date.items(),
                key=lambda item: item[0],
            )
        )

    def percent(self, value):
        return f"{value:.1f}%"

    def result_value(self, value, digits=2):
        if value is None:
            return "-"
        return f"{float(value):.{digits}f}"

    def company_para(self, text, style):
        return Paragraph(
            str(text),
            style,
        )

    def footer(self, canvas, doc):
        canvas.saveState()

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))

        canvas.drawString(
            12 * mm,
            7 * mm,
            "Priyan Scanner | EOD / Positional Market Scanner",
        )

        canvas.drawRightString(
            198 * mm,
            7 * mm,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    def handle(self, *args, **options):

        try:
            year, month = self.parse_month(
                options.get("month")
            )
        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(str(e))
            )
            return

        month_start = date(year, month, 1)

        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        month_end = next_month.fromordinal(
            next_month.toordinal() - 1
        )

        today = timezone.localdate()

        month_label = month_start.strftime("%B %Y")

        scan_types = [
            ("MOMENTUM", "Momentum"),
            ("SWING", "Swing Breakout"),
            ("INVESTMENT", "Investment Breakout"),
        ]

        daily_runs = {}

        for scan_type, label in scan_types:
            daily_runs[scan_type] = self.get_daily_runs(
                scan_type,
                month_start,
                month_end,
            )

        all_eod_dates = (
            DailyPrice.objects
            .filter(
                date__gte=month_start,
                date__lte=month_end,
            )
            .values_list("date", flat=True)
            .distinct()
            .order_by("date")
        )

        eod_dates = list(all_eod_dates)

        latest_eod_date = (
            eod_dates[-1]
            if eod_dates
            else None
        )

        scan_dates = []

        for runs in daily_runs.values():
            scan_dates.extend(runs.keys())

        latest_scan_date = (
            max(scan_dates)
            if scan_dates
            else None
        )

        closed_month = month_end < today

        if closed_month:
            report_status = "FINAL MONTHLY REPORT"
        else:
            report_status = "INTERIM MONTHLY SNAPSHOT"

        output_dir = "reports/generated"

        from pathlib import Path

        Path(output_dir).mkdir(
            parents=True,
            exist_ok=True,
        )

        output_file = (
            Path(output_dir)
            / f"Priyan_Scanner_Report_{year}_{month:02d}.pdf"
        )

        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=A4,
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=14 * mm,
            title=(
                f"Priyan Scanner Monthly Report - "
                f"{month_label}"
            ),
            author="Priyan Scanner",
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=20,
            leading=24,
            spaceAfter=5,
            textColor=colors.HexColor("#0f172a"),
        )

        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=8,
        )

        status_style = ParagraphStyle(
            "Status",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=9,
            leading=12,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#2563eb"),
            spaceAfter=12,
        )

        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=15,
            leading=18,
            spaceBefore=8,
            spaceAfter=7,
            textColor=colors.HexColor("#0f172a"),
        )

        subsection_style = ParagraphStyle(
            "Subsection",
            parent=styles["Heading3"],
            fontSize=11,
            leading=14,
            spaceBefore=6,
            spaceAfter=5,
            textColor=colors.HexColor("#334155"),
        )

        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )

        small_style = ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontSize=7.2,
            leading=9,
            textColor=colors.HexColor("#475569"),
        )

        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontSize=6.6,
            leading=8,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_CENTER,
        )

        table_text_style = ParagraphStyle(
            "TableText",
            parent=styles["Normal"],
            fontSize=6.4,
            leading=8,
            textColor=colors.HexColor("#334155"),
        )

        table_text_left_style = ParagraphStyle(
            "TableTextLeft",
            parent=table_text_style,
            alignment=TA_LEFT,
        )

        story = []

        story.append(
            Paragraph(
                "PRIYAN SCANNER",
                title_style,
            )
        )

        story.append(
            Paragraph(
                f"{month_label} — Monthly Stock Market Report",
                subtitle_style,
            )
        )

        story.append(
            Paragraph(
                report_status,
                status_style,
            )
        )

        overview_data = [
            [
                Paragraph("Report Period", table_header_style),
                Paragraph(
                    f"{month_start.strftime('%d %b %Y')} "
                    f"to {month_end.strftime('%d %b %Y')}",
                    table_text_style,
                ),
            ],
            [
                Paragraph("EOD Data Through", table_header_style),
                Paragraph(
                    latest_eod_date.strftime("%d %b %Y")
                    if latest_eod_date
                    else "No EOD data",
                    table_text_style,
                ),
            ],
            [
                Paragraph("Latest Scanner Run", table_header_style),
                Paragraph(
                    latest_scan_date.strftime("%d %b %Y")
                    if latest_scan_date
                    else "No scanner run",
                    table_text_style,
                ),
            ],
            [
                Paragraph("EOD Trading Days", table_header_style),
                Paragraph(
                    str(len(eod_dates)),
                    table_text_style,
                ),
            ],
        ]

        overview_table = Table(
            overview_data,
            colWidths=[45 * mm, 125 * mm],
        )

        overview_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, -1),
                        colors.HexColor("#f1f5f9"),
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.4,
                        colors.HexColor("#cbd5e1"),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                ]
            )
        )

        story.append(overview_table)
        story.append(Spacer(1, 10))

        story.append(
            Paragraph(
                "How to read this report",
                section_style,
            )
        )

        story.append(
            Paragraph(
                "The <b>Latest Signal</b> section shows the most recent "
                "stored result for each scanner. The <b>Monthly "
                "Persistence</b> section measures how repeatedly a stock "
                "appeared during the month. The <b>Multi-Scanner "
                "Overlap</b> section shows stocks that appeared in more "
                "than one scanner during the month. This prevents a "
                "single-day signal from being treated the same as a "
                "repeated signal.",
                body_style,
            )
        )

        if (
            latest_eod_date
            and latest_scan_date
            and latest_scan_date > latest_eod_date
        ):
            story.append(Spacer(1, 5))
            story.append(
                Paragraph(
                    f"<b>Data timing note:</b> the latest scanner run "
                    f"is dated {latest_scan_date.strftime('%d %b %Y')}, "
                    f"while the latest stored NSE EOD data is "
                    f"{latest_eod_date.strftime('%d %b %Y')}. "
                    f"Therefore, scanner calculations currently use "
                    f"the latest EOD data available in the database, "
                    f"not intraday prices.",
                    body_style,
                )
            )

        for scan_type, label in scan_types:

            runs = daily_runs[scan_type]

            story.append(
                Paragraph(
                    f"{label} — Latest Signal",
                    section_style,
                )
            )

            if not runs:
                story.append(
                    Paragraph(
                        "No scanner runs were recorded for this "
                        "scanner during the report month.",
                        body_style,
                    )
                )
                continue

            latest_date = max(runs.keys())
            latest_run = runs[latest_date]

            results = list(
                latest_run.results
                .select_related("stock")
                .order_by("rank")
            )

            table_data = [
                [
                    Paragraph("Rank", table_header_style),
                    Paragraph("Symbol", table_header_style),
                    Paragraph("Company", table_header_style),
                    Paragraph("Score", table_header_style),
                    Paragraph("Close", table_header_style),
                    Paragraph("Breakout %", table_header_style),
                    Paragraph("RelVol", table_header_style),
                    Paragraph("RSI", table_header_style),
                    Paragraph("20D %", table_header_style),
                    Paragraph("120D %", table_header_style),
                    Paragraph("200D %", table_header_style),
                ]
            ]

            for result in results[:15]:

                table_data.append(
                    [
                        str(result.rank),
                        result.stock.symbol,
                        self.company_para(
                            result.stock.company_name,
                            table_text_left_style,
                        ),
                        self.result_value(result.score),
                        self.result_value(result.close),
                        self.result_value(
                            result.breakout_percent
                        ),
                        self.result_value(
                            result.relative_volume
                        ),
                        self.result_value(result.rsi),
                        self.result_value(result.return_20),
                        self.result_value(result.return_120),
                        self.result_value(result.return_200),
                    ]
                )

            latest_table = Table(
                table_data,
                repeatRows=1,
                colWidths=[
                    9 * mm,
                    21 * mm,
                    37 * mm,
                    13 * mm,
                    16 * mm,
                    18 * mm,
                    14 * mm,
                    14 * mm,
                    14 * mm,
                    14 * mm,
                    14 * mm,
                ],
            )

            latest_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor("#e2e8f0"),
                        ),
                        (
                            "GRID",
                            (0, 0),
                            (-1, -1),
                            0.35,
                            colors.HexColor("#cbd5e1"),
                        ),
                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "MIDDLE",
                        ),
                        (
                            "ALIGN",
                            (0, 0),
                            (-1, -1),
                            "CENTER",
                        ),
                        (
                            "ALIGN",
                            (2, 1),
                            (2, -1),
                            "LEFT",
                        ),
                        (
                            "FONTSIZE",
                            (0, 0),
                            (-1, -1),
                            6,
                        ),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [
                                colors.white,
                                colors.HexColor("#f8fafc"),
                            ],
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            3,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            3,
                        ),
                    ]
                )
            )

            story.append(
                Paragraph(
                    f"Latest scan date: "
                    f"{latest_date.strftime('%d %b %Y')} | "
                    f"Daily scan dates recorded: {len(runs)}",
                    small_style,
                )
            )

            story.append(Spacer(1, 4))
            story.append(latest_table)
            story.append(Spacer(1, 8))

            story.append(
                Paragraph(
                    f"{label} — Monthly Persistence",
                    subsection_style,
                )
            )

            stats = {}

            for run_date, run in runs.items():

                for result in (
                    run.results
                    .select_related("stock")
                    .order_by("rank")
                ):

                    symbol = result.stock.symbol

                    if symbol not in stats:
                        stats[symbol] = {
                            "symbol": symbol,
                            "company": result.stock.company_name,
                            "appearances": 0,
                            "ranks": [],
                            "first_seen": run_date,
                            "last_seen": run_date,
                        }

                    item = stats[symbol]

                    item["appearances"] += 1
                    item["ranks"].append(result.rank)

                    if run_date < item["first_seen"]:
                        item["first_seen"] = run_date

                    if run_date > item["last_seen"]:
                        item["last_seen"] = run_date

            latest_results = {
                result.stock.symbol: result
                for result in (
                    latest_run.results
                    .select_related("stock")
                    .order_by("rank")
                )
            }

            rows = []

            for item in stats.values():

                last_result = latest_results.get(
                    item["symbol"]
                )

                average_rank = (
                    sum(item["ranks"])
                    / len(item["ranks"])
                )

                latest_rank = (
                    last_result.rank
                    if last_result
                    else None
                )

                latest_score = (
                    last_result.score
                    if last_result
                    else None
                )

                appearance_rate = (
                    item["appearances"]
                    / len(runs)
                    * 100
                )

                rows.append(
                    {
                        **item,
                        "average_rank": average_rank,
                        "best_rank": min(item["ranks"]),
                        "latest_rank": latest_rank,
                        "latest_score": latest_score,
                        "appearance_rate": appearance_rate,
                    }
                )

            rows.sort(
                key=lambda x: (
                    -x["appearances"],
                    x["average_rank"],
                    x["symbol"],
                )
            )

            persistence_data = [
                [
                    Paragraph("Symbol", table_header_style),
                    Paragraph("Company", table_header_style),
                    Paragraph("Appear", table_header_style),
                    Paragraph("Rate", table_header_style),
                    Paragraph("Avg Rank", table_header_style),
                    Paragraph("Best", table_header_style),
                    Paragraph("Last", table_header_style),
                    Paragraph("Last Score", table_header_style),
                ]
            ]

            for item in rows[:15]:

                persistence_data.append(
                    [
                        item["symbol"],
                        self.company_para(
                            item["company"],
                            table_text_left_style,
                        ),
                        str(item["appearances"]),
                        self.percent(
                            item["appearance_rate"]
                        ),
                        f"{item['average_rank']:.1f}",
                        str(item["best_rank"]),
                        (
                            str(item["latest_rank"])
                            if item["latest_rank"] is not None
                            else "-"
                        ),
                        self.result_value(
                            item["latest_score"]
                        ),
                    ]
                )

            persistence_table = Table(
                persistence_data,
                repeatRows=1,
                colWidths=[
                    22 * mm,
                    51 * mm,
                    15 * mm,
                    16 * mm,
                    18 * mm,
                    15 * mm,
                    15 * mm,
                    20 * mm,
                ],
            )

            persistence_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor("#e2e8f0"),
                        ),
                        (
                            "GRID",
                            (0, 0),
                            (-1, -1),
                            0.35,
                            colors.HexColor("#cbd5e1"),
                        ),
                        (
                            "VALIGN",
                            (0, 0),
                            (-1, -1),
                            "MIDDLE",
                        ),
                        (
                            "ALIGN",
                            (2, 1),
                            (-1, -1),
                            "CENTER",
                        ),
                        (
                            "ALIGN",
                            (0, 1),
                            (1, -1),
                            "LEFT",
                        ),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [
                                colors.white,
                                colors.HexColor("#f8fafc"),
                            ],
                        ),
                        (
                            "TOPPADDING",
                            (0, 0),
                            (-1, -1),
                            4,
                        ),
                        (
                            "BOTTOMPADDING",
                            (0, 0),
                            (-1, -1),
                            4,
                        ),
                    ]
                )
            )

            story.append(
                Paragraph(
                    "Sorted by number of scan appearances, then average rank.",
                    small_style,
                )
            )

            story.append(Spacer(1, 4))
            story.append(persistence_table)

            story.append(PageBreak())

        story.append(
            Paragraph(
                "Multi-Scanner Overlap — Monthly",
                section_style,
            )
        )

        combined = {}

        for scan_type, label in scan_types:

            runs = daily_runs[scan_type]

            for run in runs.values():

                for result in (
                    run.results
                    .select_related("stock")
                    .order_by("rank")
                ):

                    symbol = result.stock.symbol

                    if symbol not in combined:
                        combined[symbol] = {
                            "symbol": symbol,
                            "company": result.stock.company_name,
                            "scanners": set(),
                            "appearances": 0,
                        }

                    combined[symbol]["scanners"].add(
                        label
                    )

                    combined[symbol]["appearances"] += 1

        overlap_rows = [
            item
            for item in combined.values()
            if len(item["scanners"]) >= 2
        ]

        overlap_rows.sort(
            key=lambda x: (
                -len(x["scanners"]),
                -x["appearances"],
                x["symbol"],
            )
        )

        overlap_data = [
            [
                Paragraph("Symbol", table_header_style),
                Paragraph("Company", table_header_style),
                Paragraph("Scanner Count", table_header_style),
                Paragraph("Scanners", table_header_style),
                Paragraph("Total Appearances", table_header_style),
            ]
        ]

        for item in overlap_rows[:20]:

            overlap_data.append(
                [
                    item["symbol"],
                    self.company_para(
                        item["company"],
                        table_text_left_style,
                    ),
                    str(len(item["scanners"])),
                    self.company_para(
                        ", ".join(
                            sorted(item["scanners"])
                        ),
                        table_text_left_style,
                    ),
                    str(item["appearances"]),
                ]
            )

        if len(overlap_data) == 1:
            overlap_data.append(
                [
                    "-",
                    "No multi-scanner overlap recorded",
                    "-",
                    "-",
                    "-",
                ]
            )

        overlap_table = Table(
            overlap_data,
            repeatRows=1,
            colWidths=[
                25 * mm,
                50 * mm,
                25 * mm,
                55 * mm,
                25 * mm,
            ],
        )

        overlap_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#e2e8f0"),
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.35,
                        colors.HexColor("#cbd5e1"),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "ALIGN",
                        (2, 1),
                        (2, -1),
                        "CENTER",
                    ),
                    (
                        "ALIGN",
                        (4, 1),
                        (4, -1),
                        "CENTER",
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor("#f8fafc"),
                        ],
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        4,
                    ),
                ]
            )
        )

        story.append(
            Paragraph(
                "This section identifies stocks that appeared in at "
                "least two different scanner categories during the "
                "month. It is a descriptive cross-check, not a "
                "buy/sell recommendation.",
                body_style,
            )
        )

        story.append(Spacer(1, 6))
        story.append(overlap_table)

        story.append(Spacer(1, 12))

        story.append(
            Paragraph(
                "Report Methodology",
                section_style,
            )
        )

        methodology = [
            "Market data: NSE daily EOD data stored in Priyan Scanner.",
            "Scanner categories: Momentum, Swing Breakout and Investment Breakout.",
            "One scanner run per date is used for monthly persistence; if a scanner was run multiple times on the same date, the latest run is used.",
            "Latest Signal shows the most recent stored scanner result for the selected month.",
            "Monthly Persistence counts how many distinct scanner dates contained the stock.",
            "Appearance Rate = appearance dates divided by scanner run dates for that scanner.",
            "Multi-Scanner Overlap counts distinct scanner categories in which the stock appeared during the month.",
            "The system is designed for EOD / positional analysis, not intraday trading.",
        ]

        for line in methodology:
            story.append(
                Paragraph(
                    f"• {line}",
                    body_style,
                )
            )
            story.append(Spacer(1, 2))

        story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                "Important: scanner results are quantitative outputs "
                "from the rules implemented in Priyan Scanner. They "
                "are not personalized investment advice or a guarantee "
                "of future performance. Review the underlying stock, "
                "market conditions, risk, liquidity and your own "
                "objectives independently.",
                small_style,
            )
        )

        story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                f"Generated: {today.strftime('%d %B %Y')}",
                small_style,
            )
        )

        doc.build(
            story,
            onFirstPage=self.footer,
            onLaterPages=self.footer,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"ROBUST MONTHLY PDF CREATED: {output_file}"
            )
        )

        self.stdout.write(
            f"Report period: {month_label}"
        )

        self.stdout.write(
            f"EOD data through: "
            f"{latest_eod_date or 'None'}"
        )

        self.stdout.write(
            f"Latest scanner run: "
            f"{latest_scan_date or 'None'}"
        )
