from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import FileResponse, Http404
from django.utils import timezone


@login_required
def monthly_report(request):
    today = timezone.localdate()
    month_text = today.strftime("%Y-%m")

    # Generate/rebuild the current month's report first.
    call_command(
        "generate_monthly_report",
        month=month_text,
    )

    filename = (
        f"Priyan_Scanner_Report_{today.strftime('%Y_%m')}.pdf"
    )

    pdf_path = (
        Path(settings.BASE_DIR)
        / "reports"
        / "generated"
        / filename
    )

    if not pdf_path.exists():
        raise Http404(
            f"Monthly report not found: {filename}"
        )

    return FileResponse(
        open(pdf_path, "rb"),
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )
