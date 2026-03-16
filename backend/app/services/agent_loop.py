"""Agentic tool-calling loop for the OpenLaw query engine."""

import json
import logging
from typing import Any

import anthropic

from .tools import TOOL_SCHEMAS, execute_tool

log = logging.getLogger(__name__)

_MODEL = "claude-3-5-sonnet-20241022"
_MAX_TURNS = 8
_MAX_TOKENS = 2048

SYSTEM_PROMPT = """You are OpenLaw, an AI chief of staff for deal lawyers. You help with:
- Research: finding companies, market trends, investment signals
- Relationship management: identifying stale contacts, drafting outreach
- Automation: setting up recurring scans and monitors

You have tools available. Use them to fulfill requests accurately — don't guess when you can search.
When setting up crons, confirm what you've configured. When saving companies, confirm what was saved.
Be concise and professional. Lawyers are busy."""


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

    async with client:
        for turn in range(_MAX_TURNS):
            response = await client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=system,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                return {
                    "response": text,
                    "tools_used": tools_used,
                    "turns": turn + 1,
                }

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tools_used.append(block.name)
                    log.info(
                        "Tool call: %s input=%s user_id=%s",
                        block.name,
                        block.input,
                        user_id,
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

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

    log.warning("Agent loop hit max turns (%d) for user_id=%s", _MAX_TURNS, user_id)
    last_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            last_text = block.text
            break
    return {
        "response": last_text or "I ran into a limit — please try a more specific question.",
        "tools_used": tools_used,
        "turns": _MAX_TURNS,
    }
