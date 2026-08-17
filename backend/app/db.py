from supabase import Client, create_client

from app.config import settings


def get_user_client(token: str) -> Client:
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return client


def fetch_maybe_one(query) -> dict | None:
    # ponytail: this postgrest-py version returns None (not a response with data=None)
    # from .maybe_single().execute() when zero rows match — guard before .data.
    response = query.maybe_single().execute()
    return response.data if response else None
