"""
NHN Cloud Custom Prometheus Exporter

- Load Balancer (Pool/Member Health)
- CDN (Distribution Status, Cache, Redirect)
- RDS for MySQL (DB Instance Status, Backup, HA)

Designed for Docker containerization and Grafana dashboard integration.
"""

__version__ = "0.1.0"

from nhncloud_exporter.main import main

__all__ = ["main", "__version__"]
