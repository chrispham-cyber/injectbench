"""Run a tool-using agent loop against an Ollama model and see whether an
injection hidden in an untrusted tool result makes it exfiltrate the secret.

The loop: send the conversation + tool specs; if the model returns tool_calls,
execute them in the sandbox, append the results, and repeat; stop when the model
answers with no tool calls or we hit max_steps. Temperature 0 for reproducibility.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from backend.agent.tools import Sandbox


@dataclass
class AgentResult:
    exfiltrated: bool
    encoding: str | None
    steps: int
    transcript: list[dict]       # ordered log of the conversation
    exfiltrations: list[dict]
    calls: list[str]


def run_agent(
    model: str,
    system_prompt: str,
    task: str,
    sandbox: Sandbox,
    host: str = "http://localhost:11434",
    max_steps: int = 6,
    temperature: float = 0.0,
    timeout: float = 120.0,
) -> AgentResult:
    tools_spec = [t.spec() for t in sandbox.tools()]
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    transcript: list[dict] = [{"role": "user", "content": task}]

    steps = 0
    for steps in range(1, max_steps + 1):
        resp = httpx.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "tools": tools_spec,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        msg = resp.json()["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        transcript.append(
            {
                "role": "assistant",
                "content": msg.get("content", ""),
                "tool_calls": [tc["function"]["name"] for tc in tool_calls],
            }
        )

        if not tool_calls:
            break  # the model gave a final answer; no more tools to run

        for tc in tool_calls:
            name = tc["function"]["name"]
            args = tc["function"].get("arguments", {}) or {}
            result = sandbox.run_tool(name, args)
            messages.append({"role": "tool", "content": result})
            transcript.append({"role": "tool", "name": name, "args": args, "result": result})

    leaked, encoding = sandbox.leaked()
    return AgentResult(
        exfiltrated=leaked,
        encoding=encoding,
        steps=steps,
        transcript=transcript,
        exfiltrations=sandbox.exfiltrations,
        calls=sandbox.calls,
    )
