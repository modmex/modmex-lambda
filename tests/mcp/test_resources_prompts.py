from __future__ import annotations

from typing import Annotated

from modmex_lambda import Depends
from modmex_lambda.mcp import MCPServer
from tests.mcp.helpers import modern
import asyncio


class Catalog:
    def get(self, item_id: str) -> dict:
        return {"id": item_id, "status": "available"}


def test_resource_template_list_and_read_use_shared_di() -> None:
    server = MCPServer(name="catalog")

    @server.resource(
        "catalog://items/{item_id}",
        name="catalog-item",
        mime_type="application/json",
    )
    def item(
        item_id: str,
        catalog: Annotated[Catalog, Depends()],
    ) -> dict:
        return catalog.get(item_id)

    listed = server.handle(modern("resources/list", request_id=1))
    templates = server.handle(modern("resources/templates/list", request_id=2))
    read = server.handle(modern("resources/read", request_id=3, params={"uri": "catalog://items/A-1"}))

    assert listed is not None and listed.result["resources"] == []
    assert templates is not None and templates.result["resourceTemplates"][0]["uriTemplate"] == "catalog://items/{item_id}"
    assert read is not None
    assert '"id":"A-1"' in read.result["contents"][0]["text"]


def test_prompt_list_and_get_return_mcp_messages() -> None:
    server = MCPServer(name="catalog")

    @server.prompt(description="Prepare a lookup")
    def lookup_prompt(item_id: str) -> list[dict]:
        return [{
            "role": "user",
            "content": {"type": "text", "text": f"Lookup {item_id}"},
        }]

    listed = server.handle(modern("prompts/list", request_id=4))
    result = server.handle(modern("prompts/get", request_id=5, params={"name": "lookup_prompt", "arguments": {"item_id": "A-1"}}))

    assert listed is not None and listed.result["prompts"][0]["name"] == "lookup_prompt"
    assert result is not None
    assert result.result["messages"][0]["content"]["text"] == "Lookup A-1"


def test_async_resources_and_prompts_use_async_handlers() -> None:
    server = MCPServer(name="catalog")

    @server.resource("catalog://async/{item_id}")
    async def item(item_id: str) -> dict:
        return {"id": item_id}

    @server.prompt()
    async def lookup_prompt() -> list[dict]:
        return [{"role": "user", "content": {"type": "text", "text": "async"}}]

    async def run() -> None:
        resource = await server.handle_async(modern("resources/read", params={"uri": "catalog://async/A-1"}))
        prompt = await server.handle_async(modern("prompts/get", params={"name": "lookup_prompt"}))
        assert '"id":"A-1"' in resource.result["contents"][0]["text"]
        assert prompt.result["messages"][0]["content"]["text"] == "async"

    asyncio.run(run())
