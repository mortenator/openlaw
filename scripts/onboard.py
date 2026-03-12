#!/usr/bin/env python3
"""Admin onboarding CLI.

Usage:
    python onboard.py --email EMAIL --password PASS
    python onboard.py --email EMAIL --password PASS --companies companies.csv --contacts contacts.csv

companies.csv columns: name, industry, tags, is_watchlist
contacts.csv  columns: name, company_name, role, email, tier, last_contacted_at
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
import urllib.error


def _load_env() -> tuple[str, str]:
    """Load SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from env or .env file."""
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
        sys.exit('ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in env or .env file')
    return url, key


def _post(url: str, payload: dict, headers: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f'HTTP {e.code} from {url}: {body}')


def _admin_headers(service_key: str) -> dict:
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {service_key}',
        'apikey': service_key,
    }


def create_user(supabase_url: str, service_key: str, email: str, password: str) -> str:
    url = f'{supabase_url}/auth/v1/admin/users'
    payload = {'email': email, 'password': password, 'email_confirm': True}
    result = _post(url, payload, _admin_headers(service_key))
    return result['id']


def provision_defaults(supabase_url: str, service_key: str, user_id: str) -> None:
    url = f'{supabase_url}/rest/v1/rpc/provision_user_defaults'
    _post(url, {'user_uuid': user_id}, _admin_headers(service_key))


def _rest_post(supabase_url: str, service_key: str, table: str, rows: list[dict]) -> list[dict]:
    url = f'{supabase_url}/rest/v1/{table}'
    headers = {**_admin_headers(service_key), 'Prefer': 'return=representation'}
    data = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        sys.exit(f'HTTP {e.code} inserting into {table}: {body}')


def import_companies(
    supabase_url: str, service_key: str, user_id: str, csv_path: str
) -> dict[str, str]:
    """Insert companies and return name->id map."""
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            tags_raw = row.get('tags', '')
            tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
            is_watchlist = row.get('is_watchlist', '').lower() in ('true', '1', 'yes')
            rows.append({
                'user_id': user_id,
                'name': row['name'],
                'industry': row.get('industry') or None,
                'tags': tags,
                'is_watchlist': is_watchlist,
            })

    if not rows:
        return {}

    inserted = _rest_post(supabase_url, service_key, 'companies', rows)
    return {r['name']: r['id'] for r in inserted}


def import_contacts(
    supabase_url: str,
    service_key: str,
    user_id: str,
    csv_path: str,
    company_map: dict[str, str],
) -> int:
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            company_name = row.get('company_name', '')
            company_id = company_map.get(company_name) if company_name else None
            last_contacted = row.get('last_contacted_at') or None
            rows.append({
                'user_id': user_id,
                'company_id': company_id,
                'name': row['name'],
                'role': row.get('role') or None,
                'email': row.get('email') or None,
                'tier': int(row.get('tier', 2)),
                'last_contacted_at': last_contacted,
            })

    if not rows:
        return 0

    _rest_post(supabase_url, service_key, 'contacts', rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description='OpenLaw admin onboarding')
    parser.add_argument('--email', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--companies', help='Path to companies.csv')
    parser.add_argument('--contacts', help='Path to contacts.csv')
    args = parser.parse_args()

    supabase_url, service_key = _load_env()

    print(f'Creating user {args.email}...')
    user_id = create_user(supabase_url, service_key, args.email, args.password)
    print(f'  User created: {user_id}')

    print('Provisioning default configs...')
    provision_defaults(supabase_url, service_key, user_id)
    print('  Done.')

    company_map: dict[str, str] = {}
    n_companies = 0
    if args.companies:
        print(f'Importing companies from {args.companies}...')
        company_map = import_companies(supabase_url, service_key, user_id, args.companies)
        n_companies = len(company_map)
        print(f'  {n_companies} companies imported.')

    n_contacts = 0
    if args.contacts:
        print(f'Importing contacts from {args.contacts}...')
        n_contacts = import_contacts(
            supabase_url, service_key, user_id, args.contacts, company_map
        )
        print(f'  {n_contacts} contacts imported.')

    print()
    print('Onboarding complete:')
    print(f'  User: {args.email} ({user_id})')
    print(f'  Companies imported: {n_companies}')
    print(f'  Contacts imported: {n_contacts}')


if __name__ == '__main__':
    main()
