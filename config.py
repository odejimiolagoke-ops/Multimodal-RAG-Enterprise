import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = (
    os.getenv("SUPABASE_URL")
    or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    or "https://YOUR_PROJECT_URL.supabase.co"
)
SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or "YOUR_API_KEY"
)
KB_TABLE = "knowledge_base"
EMBEDDING_DIM = 384


def is_supabase_configured() -> bool:
    return bool(
        SUPABASE_URL
        and "YOUR_PROJECT_URL" not in SUPABASE_URL
        and SUPABASE_KEY
        and "YOUR_API_KEY" not in SUPABASE_KEY
    )


def get_supabase_config() -> dict:
    return {"url": SUPABASE_URL, "key": SUPABASE_KEY, "table": KB_TABLE}
