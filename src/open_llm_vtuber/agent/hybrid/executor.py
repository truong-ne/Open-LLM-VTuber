import asyncio
import json
from pydantic import ValidationError

from ...mcpp.tool_executor import ToolExecutor
from .runtime import TOOL


class HybridExecutor(ToolExecutor):
    """Reuse the existing provider result formats without logging private inputs."""

    def __init__(self, runtime, delegate, manager):
        super().__init__(None, manager)
        self.runtime, self.delegate = runtime, delegate

    async def run_single_tool(self, tool_name, tool_id, tool_input):
        if tool_name != TOOL["name"]:
            if (
                tool_name not in self.runtime.config.external_read_tools
                or not self.delegate
            ):
                return (
                    True,
                    "Tool is outside the operator's external read-tool allowlist",
                    {},
                    [],
                )
            result = await self.delegate.run_single_tool(tool_name, tool_id, tool_input)
            return (
                result[0],
                "[UNTRUSTED TOOL DATA]\n" + result[1],
                result[2],
                result[3],
            )
        try:
            result = await self.runtime.dispatch(
                tool_input["operation"], tool_input.get("data", {})
            )
            image = result.pop("_image", None)
            blocks = (
                [{"type": "image", "mimeType": "image/png", "data": image}]
                if image
                else []
            )
            return (
                False,
                "[UNTRUSTED TOOL DATA]\n" + json.dumps(result, ensure_ascii=False),
                {
                    "confirmation": result.get("request_id")
                    or next(
                        (
                            p.get("request_id")
                            for p in result.get("pending_network", [])
                        ),
                        None,
                    )
                },
                blocks,
            )
        except Exception as error:
            try:
                await asyncio.to_thread(
                    self.runtime.store.event,
                    "tool_error",
                    {"error_type": type(error).__name__},
                )
            except Exception:
                pass
            if isinstance(error, ValidationError):
                message = json.dumps(
                    error.errors(
                        include_input=False, include_context=False, include_url=False
                    )
                )
            elif isinstance(error, (PermissionError, ValueError)):
                message = str(error)
            else:
                message = (
                    "Tool unavailable; the operation was not confirmed as successful."
                )
            return True, f"{type(error).__name__}: {message}", {}, []

    async def execute_tools(self, tool_calls, caller_mode):
        results = []
        for call in tool_calls[:4]:
            name, tool_id, args, error, content, invalid = self.parse_tool_call(call)
            blocks = []
            metadata = {}
            if not invalid:
                error, content, metadata, blocks = await self.run_single_tool(
                    name, tool_id, args
                )
            yield {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": name,
                "status": "error" if error else "completed",
                "content": (
                    "Waiting for operator approval: " + metadata["confirmation"]
                    if metadata.get("confirmation")
                    else "Guarded tool completed"
                )
                if not error
                else content,
            }
            result = self.format_tool_result(caller_mode, tool_id, content, error)
            if blocks:
                if caller_mode == "OpenAI":
                    result["_images"] = [
                        f"data:image/png;base64,{b['data']}" for b in blocks
                    ]
                elif caller_mode == "Claude":
                    result["content"] = [
                        {"type": "text", "text": content},
                        *[
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b["data"],
                                },
                            }
                            for b in blocks
                        ],
                    ]
                else:
                    result["content"] += (
                        "\nVision image transport requires native tool support."
                    )
            results.append(result)
        # Return a result even for excess IDs to keep provider tool protocols valid.
        for call in tool_calls[4:]:
            _, tool_id, *_ = self.parse_tool_call(call)
            results.append(
                self.format_tool_result(
                    caller_mode, tool_id, "Per-round tool budget exceeded", True
                )
            )
        yield {"type": "final_tool_results", "results": results}
