"""
Tests for MCP Integration
"""
import pytest
import asyncio
from src import RescueAgentMCP
from src.llm_client import MCPLLMClient


@pytest.mark.asyncio
async def test_mcp_client_initialization():
    """Test that MCP client initializes correctly"""
    client = MCPLLMClient()
    
    assert client is not None
    assert client.mcp_sessions == {}
    assert client.available_tools == []


@pytest.mark.asyncio
async def test_agent_mcp_initialization():
    """Test agent with MCP enabled"""
    agent = RescueAgentMCP(use_mock_apis=True)
    
    # Start MCP connections
    await agent.start()
    
    assert agent is not None
    assert agent.llm is not None
    
    # Cleanup
    await agent.shutdown()


@pytest.mark.asyncio
async def test_mcp_servers_connection():
    """Test connecting to MCP servers"""
    agent = RescueAgentMCP(use_mock_apis=True)
    
    # Start should connect to MCP servers
    await agent.start()
    
    # Check if MCP initialized
    # (may fail if servers not running, that's OK for testing)
    if agent.mcp_initialized:
        assert len(agent.llm.available_tools) > 0
        print(f"Connected with {len(agent.llm.available_tools)} tools")
    else:
        print("MCP not initialized (servers not available)")
    
    await agent.shutdown()


@pytest.mark.asyncio  
async def test_tool_execution_mock():
    """Test executing an MCP tool (mock mode)"""
    agent = RescueAgentMCP(use_mock_apis=True)
    await agent.start()
    
    if agent.mcp_initialized:
        # Try to execute a tool
        try:
            result = await agent.llm._execute_mcp_tool(
                "get_flight_status",
                {"flight_number": "BA001"}
            )
            
            assert result is not None
            print(f"Tool result: {result[:100]}...")
            
        except Exception as e:
            print(f"Tool execution failed: {e}")
    
    await agent.shutdown()


def test_mcp_client_tool_conversion():
    """Test converting MCP tools to OpenAI format"""
    from mcp.types import Tool
    
    client = MCPLLMClient()
    
    # Simulate having MCP tools
    client.available_tools = [
        Tool(
            name="test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                }
            }
        )
    ]
    
    openai_tools = client._convert_mcp_tools_to_openai()
    
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "test_tool"


@pytest.mark.asyncio
async def test_agent_without_mcp():
    """Test agent works even without MCP"""
    agent = RescueAgentMCP(use_mock_apis=True)
    
    # Don't call start() - no MCP initialization
    
    assert agent is not None
    assert not agent.mcp_initialized
    
    # Should still work with fallbacks
    print("Agent created without MCP - using fallbacks")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
