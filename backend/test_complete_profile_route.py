import os
import sys

# Ensure backend package is importable from this script location
sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
import auth
from main import app
from main import CompleteProfileRequest

class DummyTable:
    def __init__(self):
        self._data = None

    def upsert(self, data):
        self._data = data
        return self

    def execute(self):
        return {'data': self._data}

class DummySupabase:
    def table(self, name):
        if name != 'profiles':
            raise ValueError(f'Unexpected table: {name}')
        return DummyTable()

class DummyUser(auth.AuthenticatedSupabaseUser):
    def __init__(self):
        super().__init__(id='dummy-user-id', email='dummy@example.com', supabase_client=DummySupabase())

app.dependency_overrides[auth.get_current_user] = lambda: DummyUser()
client = TestClient(app)

response = client.post('/auth/complete-profile', json={
    'shop_name': 'Dummy Shop',
    'business_type': 'Retail'
})
print('Status code:', response.status_code)
print('Response JSON:', response.json())
if response.status_code != 200:
    raise SystemExit('Test failed: non-200 response')
print('Complete-profile route returned 200 successfully.')
