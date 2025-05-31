<img width="1673" alt="airweave-lettermark" style="padding-bottom: 12px;" src="frontend/public/logo-and-lettermark.svg"/>

<div align="center">

<div align="center">

[![Ruff](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml)
[![ESLint](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml)
[![Backend Tests](https://github.com/airweave-ai/airweave/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/airweave-ai/airweave/actions/workflows/tests.yml)
[![Codecov](https://codecov.io/gh/airweave-ai/airweave/branch/main/graph/badge.svg)](https://codecov.io/gh/airweave-ai/airweave)
[![Discord](https://img.shields.io/discord/1323415085011701870?label=Discord&logo=discord&logoColor=white&style=flat-square)](https://discord.com/invite/484HY9Ehxt)
<br>
<div style="padding-top: 16px;">
<a href="https://trendshift.io/repositories/13748" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13748" alt="airweave-ai%2Fairweave | Trendshift" style="width: 250px; height: 55px; margin-right: 30px;" width="250" height="55"/></a>&nbsp;&nbsp;<a href="https://www.ycombinator.com/launches/NX7-airweave-let-agents-search-any-app" target="_blank"><img src="https://www.ycombinator.com/launches/NX7-airweave-let-agents-search-any-app/upvote_embed.svg" alt="Launch YC: Airweave - Let Agents Search Any App" style="margin-left: 12px;"/></a>
</div>
</div>

### Make any app searchable for your AI agents

[**Start Now**](https://app.airweave.ai) &nbsp;&nbsp;&nbsp; [**Docs**](https://docs.airweave.ai) &nbsp;&nbsp;&nbsp; [**Discord**](https://discord.com/invite/484HY9Ehxt)

</div>

## What is Airweave?

Airweave is an open-source platform that connects to your apps, databases, and documents, transforming them into searchable knowledge bases accessible through REST APIs or MCP servers. Built for developers who need their AI agents to access and semantically search across multiple data sources seamlessly.

## Quick Start

### ☁️ **Cloud**
Go to **[app.airweave.ai](https://app.airweave.ai)**

### 🐳 **Self-Hosted**
```bash
git clone https://github.com/airweave-ai/airweave.git
cd airweave
./start.sh
```
**Access at http://localhost:8080**

## How it works

### 1️⃣ Create your collection

```python
from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")

collection = client.collections.create_collection(
    name="My First Collection"
)
```

### 2️⃣ Add data source(s) to your collection

```python
stripe_connection = client.source_connections.create_source_connection(
    name="My Stripe Connection",
    short_name="stripe",
    collection=collection.readable_id,
    auth_fields={
        "api_key": "sk_test_your_stripe_key"
    },
    sync_immediately=True # Start syncing your data immediately
)
```

### 3️⃣ Search your collection

```python
results = client.collections.search_collection(
    readable_id=collection.readable_id,
    query="What are the main features?",
    response_type="completion"
)
```

<details>
<summary><b>📦 Node.js SDK</b></summary>

```typescript
import { AirweaveSDKClient, ResponseType } from "@airweave/sdk";

const client = new AirweaveSDKClient({ apiKey: "YOUR_API_KEY" });
```
</details>

<details>
<summary><b>🤖 MCP Server</b></summary>
```json
{
  "mcpServers": {
    "airweave-search": {
      "command": "npx",
      "args": ["-y", "airweave-mcp-search"],
      "env": {
        "AIRWEAVE_API_KEY": "your-api-key",
        "AIRWEAVE_COLLECTION": "your-collection-id"
      }
    }
  }
}
```
</details>

<details>
<summary><b>🌐 REST API</b></summary>
```bash
# Create collection
curl -X POST 'https://api.airweave.ai/collections' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"name": "My First Collection"}'
```
</details>

## 🔌 26 Supported Integrations

<div align="center">
  <img src="frontend/src/components/icons/apps/notion.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/github.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/google_drive.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/slack.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/stripe.svg" width="50" height="50" style="margin: 8px;" />
  <br>
  <img src="frontend/src/components/icons/apps/jira.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/linear.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/hubspot.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/gmail.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/confluence.svg" width="50" height="50" style="margin: 8px;" />
  <br>
  <img src="frontend/src/components/icons/apps/dropbox.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/asana.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/clickup.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/monday.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/google_calendar.svg" width="50" height="50" style="margin: 8px;" />
  <br>
  <img src="frontend/src/components/icons/apps/outlook_mail.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/outlook_calendar.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/onedrive.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/todoist.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/intercom.svg" width="50" height="50" style="margin: 8px;" />
  <br>
  <img src="frontend/src/components/icons/apps/postgresql.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/mysql.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/sql_server.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/oracle.svg" width="50" height="50" style="margin: 8px;" />
  <img src="frontend/src/components/icons/apps/elasticsearch.svg" width="50" height="50" style="margin: 8px;" />
  <br>

  <br><br>
  **Need another integration?** [Let us know](https://github.com/airweave-ai/airweave/issues) or [build your own](https://docs.airweave.ai/add-new-source)!
</div>

## 🤝 Join the Community

We're building Airweave in the open and would love your help!

- **[Discord](https://discord.com/invite/484HY9Ehxt)** - Get help, share ideas, meet other developers
- **[GitHub Issues](https://github.com/airweave-ai/airweave/issues)** - Report bugs, request features
- **[Contributing Guide](CONTRIBUTING.md)** - Submit PRs, add connectors, improve docs

### Ways to Contribute
- 🔌 Add new connectors
- 📖 Improve documentation
- 🐛 Report and fix bugs
- 💡 Suggest features
- ⭐ Star us on GitHub!

## 📚 Resources

- **[Documentation](https://docs.airweave.ai)** - Complete guides and API reference
- **[Quickstart Tutorial](https://docs.airweave.ai/quickstart)** - Detailed walkthrough
- **[API Reference](https://docs.airweave.ai/api-reference)** - Full API documentation
- **[MCP Setup](https://docs.airweave.ai/mcp-server)** - Connect to Claude and Cursor

## 📄 License

Airweave is open source under the [MIT License](LICENSE).

---

<div align="center">

Built with ❤️ by the [Airweave team](https://airweave.ai) and contributors worldwide

**[Get Started →](https://app.airweave.ai)**

</div>
