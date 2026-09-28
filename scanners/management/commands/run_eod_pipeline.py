from django.core.management import call_command
from django.core.management.base import BaseCommand

from marketdata.models import DailyPrice
from scanners.models import ScanRun


class Command(BaseCommand):
    help = "Run the complete Priyan Scanner EOD pipeline"

    SCANNERS = [
        ("MOMENTUM", "scan_momentum"),
        ("SWING", "scan_swing"),
        ("INVESTMENT", "scan_investment"),
    ]

    def handle(self, *args, **options):

        self.stdout.write("=== PRIYAN SCANNER EOD PIPELINE ===")

        self.stdout.write("1. Importing latest NSE EOD data...")
        call_command("import_nse")

        latest_eod_date = (
            DailyPrice.objects
            .order_by("-date")
            .values_list("date", flat=True)
            .first()
        )

        if not latest_eod_date:
            self.stdout.write(
                self.style.ERROR(
                    "No EOD market data found. Pipeline stopped."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Latest NSE EOD date: {latest_eod_date}"
            )
        )

        for scan_type, command_name in self.SCANNERS:

            already_exists = (
                ScanRun.objects
                .filter(
                    scan_type=scan_type,
                    scan_date=latest_eod_date,
                )
                .exists()
            )

            if already_exists:
                self.stdout.write(
                    f"{scan_type}: already scanned for "
                    f"{latest_eod_date} — skipping."
                )
                continue

            self.stdout.write(
                f"{scan_type}: running for {latest_eod_date}..."
            )

            call_command(
                command_name,
                date=latest_eod_date.strftime("%Y-%m-%d"),
            )

        self.stdout.write(
            "Generating current monthly report..."
        )

        call_command("generate_monthly_report")

        self.stdout.write(
            self.style.SUCCESS(
                "=== EOD PIPELINE COMPLETED ==="
            )
        )
