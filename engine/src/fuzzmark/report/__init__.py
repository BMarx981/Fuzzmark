"""Generate the reviewable run report with diffs, verdicts, and errors."""

from .models import NO_BASELINE, Report, ReportEntry
from .render import render_report

__all__ = ["render_report", "Report", "ReportEntry", "NO_BASELINE"]
