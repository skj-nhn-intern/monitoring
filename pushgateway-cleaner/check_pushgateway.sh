#!/bin/sh
# Run inside pushgateway-cleaner container to see what /metrics returns and test DELETE.
# Usage: docker exec pushgateway-cleaner python3 -c "$(cat pushgateway-cleaner/check_pushgateway.py)"
set -e
python3 -c "
import urllib.request
import re
url = 'http://pushgateway:9091/metrics'
print('Fetching', url)
r = urllib.request.urlopen(url, timeout=5)
body = r.read().decode()
pat = re.compile(r'push_time_seconds\s*\{([^}]*)\}\s+([\d.eE+-]+)')
matches = list(pat.finditer(body))
print('push_time_seconds lines found:', len(matches))
for m in matches:
    print('  ', m.group(0))
if not matches and 'push_time' in body:
    print('Sample of body (first 1500 chars):')
    print(body[:1500])
"
