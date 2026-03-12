#!/usr/bin/env python3
"""Standalone script to recalculate health scores for all contacts.

Uses exponential decay formula:
    score = 100 * exp(-days_since_contact / DECAY[tier])

DECAY constants: {1: 14, 2: 30, 3: 60}

Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY env vars (or .env file).
"""

import json
import math
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


DECAY: dict[int, float] = {1: 14.0, 2: 30.0, 3: 60.0}


def _load_env() -> tuple[str, str]:
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        sys.exit('ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set')
    return url, key


def _headers(service_key: str) -> dict:
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
    }


def _get(url: str, service_key: str) -> list[dict]:
    req = urllib.request.Request(url, headers=_headers(service_key))
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _patch(url: str, payload: dict, service_key: str) -> None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={**_headers(service_key), 'Prefer': 'return=minimal'},
        method='PATCH',
    )
    urllib.request.urlopen(req).close()


def compute_score(last_contacted_at: str | None, tier: int) -> float:
    if not last_contacted_at:
        return 0.0
    try:
        last = datetime.fromisoformat(last_contacted_at.replace('Z', '+00:00'))
    except ValueError:
        return 0.0
    now = datetime.now(timezone.utc)
    days = max((now - last).total_seconds() / 86400, 0.0)
    decay = DECAY.get(tier, DECAY[2])
    return round(100.0 * math.exp(-days / decay), 2)


def main() -> None:
    supabase_url, service_key = _load_env()

    contacts_url = f'{supabase_url}/rest/v1/contacts?select=id,last_contacted_at,tier'
    contacts = _get(contacts_url, service_key)
    print(f'Fetched {len(contacts)} contacts.')

    updated = 0
    for contact in contacts:
        score = compute_score(contact.get('last_contacted_at'), contact.get('tier', 2))
        patch_url = f'{supabase_url}/rest/v1/contacts?id=eq.{contact["id"]}'
        _patch(patch_url, {'health_score': score}, service_key)
        updated += 1

    print(f'Updated {updated} contacts.')


if __name__ == '__main__':
    main()
