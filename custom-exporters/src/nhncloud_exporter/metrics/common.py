"""Exporter self-metrics (scrape duration, errors, up)."""

from prometheus_client import Counter, Gauge, Summary

exporter_scrape_duration = Summary(
    "nhncloud_exporter_scrape_duration_seconds",
    "Time spent scraping",
    ["collector"],
)
exporter_scrape_errors = Counter(
    "nhncloud_exporter_scrape_errors_total",
    "Scrape errors total",
    ["collector"],
)
exporter_up = Gauge("nhncloud_exporter_up", "Exporter health (1=up)")
