# 🔌 MCP Integration Guide

**Complete guide to Model Context Protocol integration in Rescue Agent**

---

## 📚 Table of Contents

1. [What is MCP?](#what-is-mcp)
2. [Why Use MCP?](#why-use-mcp)
3. [Architecture Deep Dive](#architecture-deep-dive)
4. [Creating MCP Servers](#creating-mcp-servers)
5. [LLM Integration](#llm-integration)
6. [Real API Integration](#real-api-integration)
7. [Best Practices](#best-practices)
8. [Advanced Topics](#advanced-topics)

---

## 🎯 What is MCP?

**Model Context Protocol (MCP)** is a standard way to connect LLMs to external data sources and tools.

### **Traditional Approach (v1.0):**

```
User: "My flight BA001 is delayed"
  ↓
LLM: "Based on typical patterns, I suggest..."
  ↓
❌ LLM is GUESSING - doesn't know actual status
```

### **MCP Approach (v2.0):**

```
User: "My flight BA001 is delayed"
  ↓
LLM: "Let me check the current status..."
  ↓
MCP Tool Call: get_flight_status("BA001")
  ↓
MCP Server: Calls FlightAware API
  ↓
Returns: {"status": "delayed", "delay": 180, ...}
  ↓
LLM: "BA001 is confirmed delayed 180 minutes..."
  ↓
✅ LLM has REAL DATA
```

---

## 💡 Why Use MCP?

### **Without MCP:**

```python
# Agent makes assumptions
def find_alternatives(flight_number):
    # Return hardcoded options
    return [
        "Try UA123",  # But is it available?
        "Try AA456"   # But what's the price?
    ]
```

**Problems:**
- ❌ Outdated information
- ❌ Suggests unavailable flights
- ❌ Wrong pricing
- ❌ Can't adapt to real conditions

### **With MCP:**

```python
# LLM asks MCP server
LLM: "search_alternative_flights(JFK, LHR, 2026-03-15)"
  ↓
MCP Server calls Amadeus API
  ↓
Returns actual flights with:
- ✅ Real availability (8 seats left)
- ✅ Current price ($523)
- ✅ Flight status (on-time)
- ✅ Aircraft type, amenities, etc.
```

**Benefits:**
- ✅ Always current
- ✅ Verified data
- ✅ Accurate recommendations
- ✅ Higher success rate

---

## 🏗️ Architecture Deep Dive

### **Component Interaction:**

```
┌─────────────────────────────────────────────────┐
│  1. USER                                        │
│     "Flight BA001 delayed - help!"              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  2. RESCUE AGENT (agent.py)                     │
│     Receives disruption event                   │
│     Creates context for LLM                     │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  3. MCP LLM CLIENT (llm_client.py)              │
│                                                 │
│     Sends to GPT-4:                            │
│     "Analyze this disruption using tools"       │
│                                                 │
│     Available tools: [                         │
│       get_flight_status,                       │
│       search_alternative_flights,              │
│       check_weather                            │
│     ]                                          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  4. GPT-4 (OpenAI)                             │
│                                                 │
│     Thinks: "I need current status"            │
│     Decides: "Call get_flight_status tool"     │
│                                                 │
│     Returns tool_call:                         │
│     {                                          │
│       "name": "get_flight_status",            │
│       "arguments": {"flight_number": "BA001"}  │
│     }                                          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  5. MCP CLIENT (llm_client.py)                  │
│     Receives tool call from GPT-4              │
│     Routes to appropriate MCP server           │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  6. FLIGHT MCP SERVER (flight_server.py)        │
│                                                 │
│     @server.call_tool()                        │
│     def get_flight_status(flight_number):      │
│         # Call FlightAware API                 │
│         status = flightaware.get(flight_number)│
│         return status                          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  7. REAL API (FlightAware/Amadeus/etc.)        │
│     Returns actual flight data                 │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼ (data flows back up)
┌─────────────────────────────────────────────────┐
│  8. GPT-4                                       │
│     Receives: {"status": "delayed", ...}       │
│     Now has FACTS                              │
│     Generates data-driven solution             │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  9. USER                                        │
│     Sees: "BA001 confirmed delayed 180min.     │
│            Alternative UA123 departs 14:00      │
│            with 8 seats at $523"               │
└─────────────────────────────────────────────────┘
```

---

## 🛠️ Creating MCP Servers

### **Step 1: Define the Server**

```python
from mcp.server import Server
from mcp.types import Tool, TextContent

# Create server instance
server = Server("my-data-server")
```

### **Step 2: Define Available Tools**

```python
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    This tells the LLM what tools are available
    """
    return [
        Tool(
            name="get_data",
            description="Fetches data from source",  # LLM sees this!
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for"
                    }
                },
                "required": ["query"]
            }
        )
    ]
```

**The LLM sees:**
```
Tool: get_data
Description: Fetches data from source
Parameters: 
  - query (string, required): What to search for
```

### **Step 3: Implement Tool Logic**

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Executes when LLM calls a tool
    """
    if name == "get_data":
        query = arguments["query"]
        
        # Your logic here - call APIs, databases, etc.
        result = await fetch_from_api(query)
        
        # Return as JSON string
        return [TextContent(
            type="text",
            text=json.dumps(result)
        )]
```

### **Step 4: Run the Server**

```python
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(...)
        )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔗 LLM Integration

### **Connecting to MCP Servers**

In `llm_client.py`:

```python
class MCPLLMClient:
    async def initialize_mcp_servers(self):
        servers = [
            {
                "name": "flight-data",
                "command": "python",
                "args": ["-m", "mcp_servers.flight_server"]
            }
        ]
        
        for config in servers:
            # Start MCP server as subprocess
            server_params = StdioServerParameters(
                command=config["command"],
                args=config["args"]
            )
            
            # Connect via stdio
            read, write = await stdio_client(server_params)
            session = ClientSession(read, write)
            
            # Get available tools
            tools = await session.list_tools()
            
            # Store for later use
            self.mcp_sessions[config["name"]] = session
            self.available_tools.extend(tools.tools)
```

### **Converting Tools for OpenAI**

```python
def _convert_mcp_tools_to_openai(self) -> List[Dict]:
    """
    MCP tools → OpenAI function format
    """
    openai_tools = []
    
    for tool in self.available_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        })
    
    return openai_tools
```

### **Calling LLM with Tools**

```python
# Send to GPT-4 with tools available
response = await self.openai_client.chat.completions.create(
    model="gpt-4-turbo-preview",
    messages=[
        {"role": "system", "content": "Use tools to get real data"},
        {"role": "user", "content": "Check flight BA001"}
    ],
    tools=self._convert_mcp_tools_to_openai()  # ← MCP tools!
)

# Check if LLM wants to call tools
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        # Execute MCP tool
        result = await self._execute_mcp_tool(
            tool_call.function.name,
            json.loads(tool_call.function.arguments)
        )
        
        # Send result back to LLM
        # ... (see full code in llm_client.py)
```

---

## 🌐 Real API Integration

### **Flight Data (FlightAware)**

```python
# In mcp_servers/flight_server.py

async def get_flight_status(args: dict) -> list[TextContent]:
    flight_number = args["flight_number"]
    
    if os.getenv("FLIGHTAWARE_API_KEY"):
        # Production: Real API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://aeroapi.flightaware.com/aeroapi/flights/{flight_number}",
                headers={
                    "x-apikey": os.getenv("FLIGHTAWARE_API_KEY")
                }
            )
            data = response.json()
            
            result = {
                "flight_number": flight_number,
                "status": data["status"],
                "departure_delay": data["departure_delay"],
                "arrival_delay": data["arrival_delay"],
                "gate": data["gate_origin"],
                "aircraft": data["aircraft_type"],
                "data_source": "flightaware_live"
            }
    else:
        # Development: Mock data
        result = {
            "flight_number": flight_number,
            "status": "delayed",
            "departure_delay": 180,
            "data_source": "mock"
        }
    
    return [TextContent(type="text", text=json.dumps(result))]
```

### **Weather Data (OpenWeather)**

```python
# In mcp_servers/weather_server.py

async def get_weather_forecast(args: dict) -> list[TextContent]:
    location = args["location"]
    
    if os.getenv("OPENWEATHER_API_KEY"):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={
                    "q": location,
                    "appid": os.getenv("OPENWEATHER_API_KEY"),
                    "units": "imperial"
                }
            )
            weather_data = response.json()
            
            result = {
                "location": location,
                "current_temp": weather_data["list"][0]["main"]["temp"],
                "conditions": weather_data["list"][0]["weather"][0]["description"],
                "forecast": weather_data["list"][:8],  # Next 24 hours
                "data_source": "openweather_live"
            }
    else:
        result = {
            "location": location,
            "current_temp": 72,
            "conditions": "partly cloudy",
            "data_source": "mock"
        }
    
    return [TextContent(type="text", text=json.dumps(result))]
```

---

## ✅ Best Practices

### **1. Graceful Degradation**

Always provide fallback:

```python
try:
    # Try real API
    result = await real_api_call()
except Exception:
    # Fall back to mock
    result = mock_data()
```

### **2. Clear Tool Descriptions**

LLM needs to understand when to use each tool:

```python
# ❌ Bad
Tool(name="get_data", description="Gets data")

# ✅ Good
Tool(
    name="get_flight_status",
    description="Get REAL-TIME flight status including delays, gate info, and cancellations. Use when user asks about a specific flight or when you need current status to make recommendations."
)
```

### **3. Validate Tool Arguments**

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    # Validate required fields
    if "flight_number" not in arguments:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "flight_number required"})
        )]
    
    # Validate format
    if not re.match(r"^[A-Z]{2}\d+$", arguments["flight_number"]):
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Invalid flight number format"})
        )]
    
    # Process...
```

### **4. Structure Tool Responses**

Return consistent JSON:

```python
# Always include these fields
result = {
    "success": True,
    "data": {...},
    "timestamp": datetime.now().isoformat(),
    "source": "flightaware_api"
}
```

### **5. Error Handling**

```python
try:
    result = await api_call()
except httpx.TimeoutError:
    return [TextContent(text=json.dumps({
        "success": False,
        "error": "API timeout - please try again"
    }))]
except Exception as e:
    logger.error(f"API error: {e}")
    return [TextContent(text=json.dumps({
        "success": False,
        "error": "Service temporarily unavailable"
    }))]
```

---

## 🚀 Advanced Topics

### **Caching MCP Results**

```python
from cachetools import TTLCache

class FlightMCPServer:
    def __init__(self):
        self.cache = TTLCache(maxsize=1000, ttl=300)  # 5 min cache
    
    async def get_flight_status(self, args):
        cache_key = f"status:{args['flight_number']}"
        
        if cache_key in self.cache:
            logger.info(f"Cache hit for {cache_key}")
            return self.cache[cache_key]
        
        result = await self._fetch_real_status(args)
        self.cache[cache_key] = result
        
        return result
```

### **Rate Limiting**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_api(url, params):
    async with httpx.AsyncClient() as client:
        return await client.get(url, params=params)
```

### **Parallel Tool Calls**

```python
# LLM can request multiple tools at once
tool_calls = [
    ("get_flight_status", {"flight_number": "BA001"}),
    ("check_weather", {"location": "LHR"}),
    ("search_alternatives", {"origin": "JFK", "dest": "LHR"})
]

# Execute in parallel
results = await asyncio.gather(*[
    execute_tool(name, args) for name, args in tool_calls
])
```

### **Tool Call Logging**

```python
# Track all tool usage
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    logger.info(f"Tool called: {name} with {arguments}")
    
    start_time = time.time()
    result = await execute_tool_logic(name, arguments)
    duration = time.time() - start_time
    
    logger.info(f"Tool {name} completed in {duration:.2f}s")
    
    # Could send to monitoring system
    metrics.record_tool_call(name, duration, success=True)
    
    return result
```

---

## 📊 Performance Considerations

### **Tool Call Overhead**

```
Traditional:
- LLM processes: 2 seconds
- Total: 2 seconds

With MCP:
- LLM processes: 1 second
- Tool calls (3): 1.5 seconds
- LLM final response: 1.5 seconds
- Total: 4 seconds
```

**Trade-off**: +2 seconds for verified accuracy ✅

### **Optimization Strategies**

1. **Cache aggressively** - Don't refetch same data
2. **Batch operations** - Combine related tool calls
3. **Parallel execution** - Run independent tools simultaneously
4. **Timeout quickly** - Don't wait forever for APIs
5. **Fallback fast** - Switch to mocks if API slow

---

## 🎓 When to Use MCP

### **Use MCP When:**

✅ You need current, real-time data  
✅ Data changes frequently (flight status, weather)  
✅ Accuracy is critical (booking confirmations)  
✅ You want to connect multiple data sources  
✅ Building production systems

### **Skip MCP When:**

❌ Static data is sufficient  
❌ Speed more important than accuracy  
❌ Building quick prototypes  
❌ No real APIs available  
❌ Offline operation required

---

## 🎯 Summary

**MCP transforms your agent from:**
- 🎲 **Guessing** → ✅ **Knowing**
- 📚 **Outdated** → ✅ **Current**  
- 🤷 **Maybe** → ✅ **Verified**
- 🐌 **Static** → ✅ **Dynamic**

**The result:** Professional-grade AI that makes decisions based on FACTS, not assumptions!

---

**Next:** Read the main README.md and try the demo! 🚀
