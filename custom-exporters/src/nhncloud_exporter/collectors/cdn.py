"""
CDN collector.

NHN Cloud CDN v2.0 API: distribution status, cache config, redirect, statistics.
"""

import logging
from datetime import datetime, timedelta, timezone

from nhncloud_exporter import config
from nhncloud_exporter.utils import api_get
from nhncloud_exporter.metrics import (
    exporter_scrape_errors,
    cdn_allow_delete,
    cdn_allow_post,
    cdn_allow_put,
    cdn_callback_configured,
    cdn_cert_expire_days,
    cdn_cert_status,
    cdn_distribution_cache_type,
    cdn_distribution_default_max_age,
    cdn_distribution_status,
    cdn_http_2xx,
    cdn_http_3xx,
    cdn_http_4xx,
    cdn_http_5xx,
    cdn_large_file_optimization,
    cdn_origin_http_downgrade,
    cdn_referrer_type,
    cdn_root_path_redirect_enabled,
    cdn_root_path_redirect_status_code,
    cdn_stat_bandwidth,
    cdn_stat_hit_ratio,
    cdn_stat_request_bypass,
    cdn_stat_request_hit,
    cdn_stat_request_miss,
    cdn_stat_transfer,
    cdn_use_origin_cache_control,
)

logger = logging.getLogger("nhncloud-exporter")


class CDNCollector:
    """Collects CDN distribution, cache, redirect and statistics metrics."""

    STATUS_MAP = {"OPEN": 1, "OPENING": 2, "SUSPEND": 3, "CLOSING": 4, "CLOSED": 5, "ERROR": 6}
    CACHE_TYPE_MAP = {"NO_STORE": 1, "BYPASS": 2, "ORIGIN": 3}
    REF_TYPE_MAP = {"BLACKLIST": 1, "WHITELIST": 2}

    def collect(self) -> None:
        if not config.NHN_CDN_APPKEY:
            logger.debug("CDN collector skipped: no appkey")
            return

        headers = {
            "Authorization": config.NHN_CDN_SECRETKEY,
            "Content-Type": "application/json",
        }
        base = config.NHN_CDN_API_BASE.rstrip("/")

        try:
            self._collect_distributions(base, headers)
            self._collect_statistics(base, headers)
            self._collect_certificates(base, headers)
        except Exception as e:
            logger.error("CDN collector error: %s", e)
            exporter_scrape_errors.labels(collector="cdn").inc()

    def _collect_distributions(self, base: str, headers: dict) -> None:
        dist_data = api_get(
            f"{base}/v2.0/appKeys/{config.NHN_CDN_APPKEY}/distributions",
            headers,
        )
        distributions = dist_data.get("distributions", [])

        for d in distributions:
            domain = d.get("domain", "unknown")
            region = d.get("region", "")
            desc = d.get("description", "")
            status_val = self.STATUS_MAP.get(d.get("status", "").upper(), 0)

            cdn_distribution_status.labels(
                domain=domain, region=region, description=desc
            ).set(status_val)
            cdn_distribution_cache_type.labels(domain=domain).set(
                self.CACHE_TYPE_MAP.get(d.get("cacheType", "").upper(), 0)
            )
            cdn_distribution_default_max_age.labels(domain=domain).set(
                d.get("defaultMaxAge", 0)
            )
            cdn_use_origin_cache_control.labels(domain=domain).set(
                1 if d.get("useOriginCacheControl", False) else 0
            )
            cdn_origin_http_downgrade.labels(domain=domain).set(
                1 if d.get("useOriginHttpProtocolDowngrade", False) else 0
            )
            cdn_large_file_optimization.labels(domain=domain).set(
                1 if d.get("useLargeFileOptimization", False) else 0
            )

            rp = d.get("rootPathAccessControl", {})
            rp_enabled = 1 if rp.get("enable", False) else 0
            cdn_root_path_redirect_enabled.labels(domain=domain).set(rp_enabled)
            if rp_enabled:
                cdn_root_path_redirect_status_code.labels(
                    domain=domain,
                    redirect_path=rp.get("redirectPath", ""),
                ).set(rp.get("redirectStatusCode", 0))

            cb = d.get("callback", {})
            cdn_callback_configured.labels(domain=domain).set(
                1 if cb and cb.get("url") else 0
            )

            ref_type = d.get("referrerType", "")
            cdn_referrer_type.labels(domain=domain).set(
                self.REF_TYPE_MAP.get(ref_type.upper(), 0)
            )

            cdn_allow_post.labels(domain=domain).set(
                1 if d.get("isAllowPost", False) else 0
            )
            cdn_allow_put.labels(domain=domain).set(
                1 if d.get("isAllowPut", False) else 0
            )
            cdn_allow_delete.labels(domain=domain).set(
                1 if d.get("isAllowDelete", False) else 0
            )

        self._distributions = distributions

    def _collect_statistics(self, base: str, headers: dict) -> None:
        now = datetime.now(timezone.utc)
        from_dt = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_dt = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        distributions = getattr(self, "_distributions", [])

        for d in distributions:
            domain = d.get("domain", "")
            if not domain:
                continue

            try:
                traffic_url = (
                    f"{base}/v2.0/appKeys/{config.NHN_CDN_APPKEY}/statistics/traffic"
                    f"?domain={domain}&fromDate={from_dt}&toDate={to_dt}"
                )
                traffic = api_get(traffic_url, headers)
                stats = traffic.get("statistics", [])
                if stats:
                    latest = stats[-1] if isinstance(stats, list) else stats
                    cdn_stat_bandwidth.labels(domain=domain).set(
                        latest.get("bandwidth", 0)
                    )
                    cdn_stat_transfer.labels(domain=domain).set(
                        latest.get("dataTransferred", 0)
                    )
                    hit = latest.get("successHits", latest.get("cacheHits", 0))
                    miss = latest.get("cacheMisses", 0)
                    bypass = latest.get("cacheBypass", 0)
                    total_req = hit + miss + bypass
                    cdn_stat_request_hit.labels(domain=domain).set(hit)
                    cdn_stat_request_miss.labels(domain=domain).set(miss)
                    cdn_stat_request_bypass.labels(domain=domain).set(bypass)
                    cdn_stat_hit_ratio.labels(domain=domain).set(
                        hit / total_req if total_req > 0 else 0
                    )
            except Exception as e:
                if "404" in str(e):
                    logger.warning(
                        "CDN traffic 404 for %s. Check API/domain or NHN_DISABLE_COLLECTORS=cdn",
                        domain,
                    )
                else:
                    logger.warning("CDN traffic stats error for %s: %s", domain, e)

            try:
                httpcode_url = (
                    f"{base}/v2.0/appKeys/{config.NHN_CDN_APPKEY}/statistics/httpstatuscode"
                    f"?domain={domain}&fromDate={from_dt}&toDate={to_dt}"
                )
                httpcode = api_get(httpcode_url, headers)
                code_stats = httpcode.get("statistics", [])
                total_2xx = total_3xx = total_4xx = total_5xx = 0
                for cs in code_stats:
                    total_2xx += cs.get("successHits", cs.get("2xxCount", 0))
                    total_3xx += cs.get("3xxCount", cs.get("redirectHits", 0))
                    total_4xx += cs.get("4xxCount", 0)
                    total_5xx += cs.get("5xxCount", 0)
                cdn_http_2xx.labels(domain=domain).set(total_2xx)
                cdn_http_3xx.labels(domain=domain).set(total_3xx)
                cdn_http_4xx.labels(domain=domain).set(total_4xx)
                cdn_http_5xx.labels(domain=domain).set(total_5xx)
            except Exception as e:
                if "404" in str(e):
                    logger.warning(
                        "CDN HTTP stats 404 for %s. Check API/domain or NHN_DISABLE_COLLECTORS=cdn",
                        domain,
                    )
                else:
                    logger.warning("CDN HTTP stats error for %s: %s", domain, e)

    def _collect_certificates(self, base: str, headers: dict) -> None:
        try:
            cert_url = f"{base}/v2.0/appKeys/{config.NHN_CDN_APPKEY}/certificates"
            cert_data = api_get(cert_url, headers)
            cert_status_map = {
                "PENDING_NEW": 1,
                "DOMAIN_VALIDATION": 2,
                "ISSUE_REQUESTED": 3,
                "PENDING_COMPLETE": 4,
                "ACTIVE": 5,
                "FAILED": 6,
                "EXPIRED": 7,
            }
            for cert in cert_data.get("certificates", []):
                dns_name = cert.get("dnsName", "")
                dns_status = cert.get("dnsStatus", "")
                cdn_cert_status.labels(domain=dns_name, dns_name=dns_name).set(
                    cert_status_map.get(dns_status.upper(), 0)
                )
                renewal_end = cert.get("renewalEndDate")
                if renewal_end:
                    try:
                        end_dt = datetime.fromisoformat(
                            renewal_end.replace("Z", "+00:00")
                        )
                        days = (end_dt - datetime.now(timezone.utc)).days
                        cdn_cert_expire_days.labels(
                            domain=dns_name, dns_name=dns_name
                        ).set(days)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("CDN cert check: %s", e)
