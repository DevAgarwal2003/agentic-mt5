import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_real_stdio_tools():
    async def check():
        params=StdioServerParameters(command=sys.executable,args=['-m','ta_mcp.server'],env=dict(os.environ))
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as s:
                await s.initialize()
                names={t.name for t in (await s.list_tools()).tools}
                assert {'datasets','analyze_csv','evaluate_csv','analyze_mt5'} <= names
                for name,args in [('datasets',{}),('analyze_csv',{'name':'SYNTHETIC_H1.csv'}),('evaluate_csv',{'name':'SYNTHETIC_H1.csv'})]:
                    result=await s.call_tool(name,args)
                    assert not result.isError, result
                bad=await s.call_tool('analyze_csv',{'name':'../outside.csv'})
                assert bad.isError
    asyncio.run(check())
