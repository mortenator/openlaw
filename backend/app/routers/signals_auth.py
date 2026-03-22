"""Token-based signals endpoints."""
import logging
from typing import Optional

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.database import supabase
from app.deps import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
async def list_signals(
    company_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    current_user=Depends(get_current_user),
) -> list[dict]:
    query = (
        supabase.table("signals")
        .select("*")
        .eq("user_id", current_user.id)
    )
    if company_id is not None:
        query = query.eq("company_id", company_id)
    result = query.order("created_at", desc=True).limit(limit).execute()
    return result.data or []


class SignalCreate(BaseModel):
    company_id: Optional[str] = None
    source: str = "general_news"
    headline: str
    summary: Optional[str] = None
    url: Optional[str] = None
    relevance_score: Optional[float] = None


@router.post("/{signal_id}/enrich")
async def enrich_signal(
    signal_id: str,
    current_user=Depends(get_current_user),
) -> dict:
    """Fetch article content and enrich the signal with full body + key points via Claude."""
    # Load signal
    result = (
        supabase.table("signals")
        .select("*")
        .eq("id", signal_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Signal not found")

    sig = result.data[0]

    # Return cached enrichment if already done
    raw = sig.get("raw_data") or {}
    if raw.get("enriched"):
        return {**sig, "raw_data": raw}

    url = sig.get("url")
    headline = sig.get("headline", "")
    existing_summary = sig.get("summary", "")

    article_text = ""

    # Attempt to fetch article text
    if url:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    content = resp.text
                    # Strip HTML tags simply
                    import re
                    text = re.sub(r"<style[^>]*>.*?</style>", " ", content, flags=re.DOTALL)
                    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL)
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    article_text = text[:8000]  # cap for Claude context
        except Exception:
            log.warning("Failed to fetch article for signal %s url=%s", signal_id, url)

    # Build Claude prompt
    prompt_parts = [f"Headline: {headline}"]
    if existing_summary:
        prompt_parts.append(f"Summary: {existing_summary}")
    if article_text:
        prompt_parts.append(f"Article text:\n{article_text}")
    else:
        prompt_parts.append("(No article text available — use your knowledge of this topic)")
    if url:
        prompt_parts.append(f"Source URL: {url}")

    prompt = "\n\n".join(prompt_parts) + """

Based on the above, provide a structured analysis in this exact JSON format:
{
  "full_summary": "3-5 sentence detailed summary of what happened and why it matters for deal lawyers",
  "article_body": "A detailed 4-6 paragraph journalistic write-up of the full story. Cover: what happened, who is involved, deal terms or investment size if known, strategic rationale, market context, and any reactions. Write as if for a legal industry newsletter. Be specific and substantive.",
  "key_points": ["point 1", "point 2", "point 3", "point 4"],
  "why_it_matters": "1-2 sentences on the BD / legal implication — who might need counsel, what transactions this could trigger",
  "sources": [{"title": "source title or domain", "url": "the url"}]
}

Respond with only valid JSON, no markdown fences."""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        enriched = json.loads(msg.content[0].text.strip())
    except Exception as exc:
        log.exception("Claude enrichment failed for signal %s", signal_id)
        # Graceful fallback
        enriched = {
            "full_summary": existing_summary or headline,
            "key_points": [],
            "why_it_matters": "",
            "sources": [{"title": url.split("/")[2] if url else "Source", "url": url}] if url else [],
        }

    raw_data = {**raw, "enriched": True, **enriched}

    # Cache in DB
    supabase.table("signals").update({"raw_data": raw_data}).eq("id", signal_id).execute()

    return {**sig, "raw_data": raw_data}


@router.delete("/{signal_id}", status_code=204)
async def delete_signal(
    signal_id: str,
    current_user=Depends(get_current_user),
) -> None:
    supabase.table("signals").delete().eq("id", signal_id).eq("user_id", current_user.id).execute()


@router.post("", status_code=201)
async def create_signal(
    payload: SignalCreate,
    current_user=Depends(get_current_user),
) -> dict:
    """Manually insert a signal (used for seeding and testing)."""
    data = payload.model_dump(exclude_none=True)
    data["user_id"] = str(current_user.id)
    result = supabase.table("signals").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Failed to create signal")
    return result.data[0]
