import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path('C:/FAT_Studio')
sys.path.insert(0, str(ROOT))
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from integrations.tia_engineering import READ_TOOLS, WRITE_TOOLS, SdkTransport, EngineeringError


async def main():
    output = ROOT / 'evidence/reprises/2026-11-02-windows-extended'
    server = ROOT / '.local/tia-mcp-package-check/tia-mcp.exe'
    env = {**os.environ, 'DOTNET_ROOT': str(ROOT / '.tools/dotnet')}
    result = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'read-only',
              'scope': 'Real pinned NuGet host and official MCP SDK transport/capability listing only; no TIA project operation',
              'profile_installed': False, 'server': str(server)}
    async with Client(StdioServerParameters(command=str(server), args=['--access-mode', 'read-only'], env=env),
                      mode='legacy', read_timeout_seconds=20) as client:
        info = client.server_info.model_dump(mode='json')
        assert info['version'].split('+')[0] in {'4.3.0', '4.3.0.0'}, info
        tools = []
        cursor = None
        while True:
            page = await client.list_tools(cursor=cursor)
            tools.extend(tool.name for tool in page.tools)
            cursor = page.next_cursor
            if not cursor:
                break
        assert READ_TOOLS.issubset(tools), tools
        assert not WRITE_TOOLS.intersection(tools), tools
        assert not {'download', 'run_cpu', 'stop_cpu', 'network_write', 'hmi_write', 'vci_write'}.intersection(tools), tools
        transport = SdkTransport(client, writable=False)
        blocked = []
        for name in sorted(WRITE_TOOLS | {'download', 'run_cpu', 'stop_cpu', 'network_write'}):
            try:
                await transport.call(name, {})
            except EngineeringError:
                blocked.append(name)
            else:
                raise AssertionError('Unexpected allowed write tool: ' + name)
        result.update(server_info=info, tools=tools, blocked_locally_before_call=blocked)
    assert not (server.parent / 'fat-tia-profile.json').exists()
    result.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat())
    (output / 'tia-package-readonly-transport.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


asyncio.run(main())
