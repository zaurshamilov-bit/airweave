# mcp-server-sync-test: A Sync Test MCP Server

## Overview

A Model Context Protocol server for testing Airweave source integrations. This server provides tools to check connection status and run syncs for source integrations.

Please note that mcp-server-sync-test is currently in early development. The functionality and available tools are subject to change and expansion as we continue to develop and improve the server.

### Tools

1. `check_connection`  
   * Checks if a source connection is established  
   * Input:  
         * `short_name` (string): Short name of the source to check  
   * Returns: Connection status and details

2. `run_sync`  
   * Runs a sync for a source integration  
   * Input:  
         * `short_name` (string): Short name of the source to sync  
   * Returns: Sync status and results

## Installation

### Using uv (recommended)

When using uv no specific installation is needed. We will use uvx to directly run _mcp-server-sync-test_.

### Using PIP

Alternatively you can install `mcp-server-sync-test` via pip:

```
pip install mcp-server-sync-test
```

After installation, you can run it as a script using:

```
python -m mcp_server_sync_test
```

## Configuration

### Usage with Claude Desktop

Add this to your `claude_desktop_config.json`:

Using uvx 
```json
"mcpServers": {
  "sync-test": {
    "command": "uvx",
    "args": ["mcp-server-sync-test"]
  }
}
```

Using docker 
```json
"mcpServers": {
  "sync-test": {
    "command": "docker",
    "args": ["run", "--rm", "-i", "--mount", "type=bind,src=/Users/username,dst=/Users/username", "mcp/sync-test"]
  }
}
```

Using pip installation 
```json
"mcpServers": {
  "sync-test": {
    "command": "python",
    "args": ["-m", "mcp_server_sync_test"]
  }
}
```

### Usage with Zed

Add to your Zed settings.json:

Using uvx 
```json
"context_servers": [
  "mcp-server-sync-test": {
    "command": {
      "path": "uvx",
      "args": ["mcp-server-sync-test"]
    }
  }
],
```

Using pip installation 
```json
"context_servers": {
  "mcp-server-sync-test": {
    "command": {
      "path": "python",
      "args": ["-m", "mcp_server_sync_test"]
    }
  }
},
```

## Debugging

You can use the MCP inspector to debug the server. For uvx installations:

```
npx @modelcontextprotocol/inspector uvx mcp-server-sync-test
```

Or if you've installed the package in a specific directory or are developing on it:

```
cd path/to/servers/src/sync-test
npx @modelcontextprotocol/inspector uv run mcp-server-sync-test
```

## Development

If you are doing local development, there are two ways to test your changes:

1. Run the MCP inspector to test your changes. See Debugging for run instructions.
2. Test using the Claude desktop app. Add the following to your `claude_desktop_config.json`:

### Docker

```json
{
  "mcpServers": {
    "sync-test": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--mount", "type=bind,src=/Users/username/Desktop,dst=/projects/Desktop",
        "--mount", "type=bind,src=/path/to/other/allowed/dir,dst=/projects/other/allowed/dir,ro",
        "--mount", "type=bind,src=/path/to/file.txt,dst=/projects/path/to/file.txt",
        "mcp/sync-test"
      ]
    }
  }
}
```

### UVX

```json
{
"mcpServers": {
  "sync-test": {
    "command": "uv",
    "args": [ 
      "--directory",
      "/<path to mcp-servers>/mcp-servers/src/sync-test",
      "run",
      "mcp-server-sync-test"
    ]
  }
}
```

## Build

Docker build:

```
cd src/sync-test
docker build -t mcp/sync-test .
```

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository. 