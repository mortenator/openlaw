import httpx
from supabase import create_client, Client
from app.config import settings


def get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def paperclip_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.paperclip_base_url,
        headers={
            "X-Internal-Key": settings.paperclip_internal_key,
            "Content-Type": "application/json",
        },
    )


supabase: Client = get_supabase_client()
