import json
import os
import uuid
import urllib.request
import urllib.error

# Load environment variables from .env
env = {}
with open('.env', 'r', encoding='utf-8') as f:
    for line in f:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        key, value = stripped.split('=', 1)
        env[key] = value

SUPABASE_URL = env.get('SUPABASE_URL')
SUPABASE_KEY = env.get('SUPABASE_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit('Missing SUPABASE_URL or SUPABASE_KEY in .env')

email = f'testonboarding{uuid.uuid4().hex[:8]}@gmail.com'
password = 'TestPassword123!'
print('Testing signup for', email)

from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
print('Signing up via supabase.auth.sign_up()')
try:
    signup_result = supabase.auth.sign_up({
        'email': email,
        'password': password
    })
    signup_resp = signup_result
    print('Signup response keys:', list(signup_resp.keys()))
except Exception as exc:
    print('Signup failed:', exc)
    raise

access_token = signup_resp.get('access_token') or signup_resp.get('data', {}).get('access_token')
if not access_token:
    raise SystemExit(f'Signup did not return access_token: {signup_resp}')
print('Got access token length', len(access_token))

complete_payload = json.dumps({'shop_name': 'Test Shop', 'business_type': 'Retail'}).encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8000/auth/complete-profile',
    data=complete_payload,
    headers={
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    },
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode('utf-8')
        print('Complete-profile status:', resp.status)
        print('Complete-profile response:', body)
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print('Complete-profile failed:', e.code, body)
    raise
