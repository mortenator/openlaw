from supabase import create_client, Client
from app.config import settings


def get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


supabase: Client = get_supabase_client()

# Alias for clarity — the default client already uses the service role key.
supabase_admin: Client = supabase
