"""Agentic tool-calling loop for the OpenLaw query engine."""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from .tools import TOOL_SCHEMAS, execute_tool

# NOTE: supabase-py uses a synchronous client (blocking I/O). Tool executors call it
# from async functions, which will block the event loop under concurrent load.
# supabase-py's async client support is experimental; migrating is a future task.
# For MVP (low concurrency), this is acceptable.

log = logging.getLogger(__name__)

_MODEL = "claude-3-5-sonnet-20241022"
_MAX_TURNS = 8
_MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are OpenLaw, an AI chief of staff for deal lawyers. You help with:
- Research: finding companies, market trends, investment signals
- Relationship management: identifying stale contacts, drafting outreach
- Automation: setting up recurring scans and monitors

You have tools available. Use them to fulfill requests accurately — don't guess when you can search.
When setting up crons, confirm what you've configured. When saving companies, confirm what was saved.
Be concise and professional. Lawyers are busy."""


def _extract_text(content: list) -> str:
    """Pull the first text block from a message content list."""
    return next((b.text for b in content if hasattr(b, "text")), "")


async def run_agent_loop(
    user_message: str,
    user_id: str,
    supabase_admin: Any,
    brave_api_key: str,
    anthropic_api_key: str,
    user_context: str = "",
) -> dict:
    """Run the agentic loop.

    Returns {"response": str, "tools_used": list[str], "turns": int}.
    """
    client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)

    system = SYSTEM_PROMPT
    if user_context:
        system += f"\n\n## User Context\n{user_context}"

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    tools_used: list[str] = []
    last_response = None  # track last response so max-turns fallback is always safe

    async with client:
        for turn in range(_MAX_TURNS):
            response = await client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=system,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            last_response = response

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return {
                    "response": _extract_text(response.content),
                    "tools_used": tools_used,
                    "turns": turn + 1,
                }

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tools_used.append(block.name)
                    sanitized_input = {
                        k: v for k, v in block.input.items()
                        if k not in {"api_key", "token", "secret", "password"}
                    }
                    log.info(
                        "Tool call: %s input=%s user_id=%s",
                        block.name, sanitized_input, user_id,
                    )

                    try:
                        result = await execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            user_id=user_id,
                            supabase_admin=supabase_admin,
                            brave_api_key=brave_api_key,
                        )
                    except Exception as exc:
                        log.exception("Tool %s failed", block.name)
                        result = {"error": str(exc)}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

                messages.append({"role": "user", "content": tool_results})
                continue  # explicit continue — proceed to next turn

            # stop_reason is "max_tokens" or anything unexpected — surface what we have
            log.warning(
                "Agent loop stopping on stop_reason=%r turn=%d user_id=%s",
                response.stop_reason, turn, user_id,
            )
            return {
                "response": _extract_text(response.content)
                    or "My response was too long — please try a more specific question.",
                "tools_used": tools_used,
                "turns": turn + 1,
            }

    # Exhausted max turns
    log.warning("Agent loop hit max turns (%d) for user_id=%s", _MAX_TURNS, user_id)
    fallback_text = _extract_text(last_response.content) if last_response else ""
    return {
        "response": fallback_text or "I ran into a limit — please try a more specific question.",
        "tools_used": tools_used,
        "turns": _MAX_TURNS,
    }
