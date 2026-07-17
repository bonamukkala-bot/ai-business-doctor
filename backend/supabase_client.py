import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = None
supabase_client_initialized = False
supabase_init_error = None

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    supabase_client_initialized = True
except Exception as exc:
    supabase_init_error = exc


def create_authenticated_client(access_token: str):
    """Create a request-scoped Supabase client authenticated with the user's JWT."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(access_token)
    return client

