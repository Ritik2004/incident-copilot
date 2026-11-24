from mcp.server.mcpserver import MCPServer
from app import agent

mcp = MCPServer("incident-copilot")


@mcp.tool()
def read_logs(service: str) -> str:
    """Read recent ERROR/WARN log lines (last 2 minutes) for a service/container."""
    return agent.read_logs(service)


@mcp.tool()
def get_metrics(service:str) -> str:
    """Get request counts by status code (last 2 minutes) for a service from Prometheus. Use to see if errors or slowness are happening."""
    return agent.get_metrics(service)


@mcp.tool()
def get_service_status() -> str:
    """List all containers and whether each is running or stopped (Up / Exited). Use when a service can't reach a dependency."""
    return agent.get_service_status()



if __name__ == "__main__":
    mcp.run()
