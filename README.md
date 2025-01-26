<img width="1673" alt="airweave-lettermark" src="https://github.com/user-attachments/assets/e79a9af7-2e93-4888-9cf4-0f700f19fe05" />



[![Ruff](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml) [![ESLint](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml) [![Discord](https://img.shields.io/discord/1323415085011701870?label=Discord&logo=discord&logoColor=white&style=flat-square)](https://discord.gg/r2cF7V6s)


**Airweave** is an open-source tool that makes **any app searchable** for your agent by syncing your users' app data, APIs, databases and websites into your vector database with minimal configuration. 


<p align="center">
  <img src="https://github.com/user-attachments/assets/8113122a-111e-477e-ade8-2f8a79b70c72" alt="airweave-demo" />
  <em>Airweave demo - choose source, vector database, and sync.</em>
</p>


## Table of Contents

1. [Overview](#overview)  
2. [Quick Start](#quick-start)  
3. [Usage](#usage)  
4. [Key Features](#key-features)  
5. [Technology Stack](#technology-stack)  
6. [Configuration](#configuration)  
7. [Contributing](#contributing)  
8. [Roadmap](#roadmap)  
9. [License](#license)

---

## Overview

Airweave simplifies the process of making your data searchable. Whether you have structured or unstructured data, Airweave helps you break it into processable chunks, store the data in a vector database, and retrieve it via your own **agent** or any **search mechanism**. 


## Quick Start

Below is a simple guide to get Airweave up and running locally. For more detailed instructions, refer to the [docs](https://docs.airweave.ai).

### Prerequisites

- **Docker** (v20+)  
- **Docker Compose** (v2.0+)

### Steps

1. **Clone the Repository**  
   ```bash
   git clone https://github.com/airweave-ai/airweave/airweave.git
   cd airweave

2. **Set Up Environment Variables**  
   Copy .env.example to .env and update any necessary variables, such as Postgres connection strings or credentials.

3. **Build and Run**  
   ```bash
   docker-compose up --build
   ```

That's it!

You now have Airweave running locally. You can log in to the dashboard, add new sources, and configure your sync schedules.


## Usage

To use Airweave, you can either use the frontend or the API.


### Frontend
- Access the React UI at `http://localhost:8080`.
- Navigate to Sources to add new integrations.
- Set up or view your sync schedules under Schedules.
- Monitor sync jobs in Jobs.

### API Endpoints (FastAPI)
- **Swagger Documentation:** `http://localhost:8001/docs`
- **Get All Sources:** `GET /sources`
- **Connect a Source:** `POST /connections/{short_name}`


### Why Airweave?
- **Over 120 integrations**: Airweave is your one-stop shop for building any application that requires semantic search.
- **Simplicity**: Minimal configuration needed to sync data from diverse sources (APIs, databases, and more).
- **Extensibility**: Easily add new integrations via `sources` , `destinations` and `embedders`.
- **Open-Core**: Core features are open source, ensuring transparency. Future commercial offerings will bring additional, advanced capabilities.
- **Async-First**: Built to handle large-scale data synchronization asynchronously (upcoming: managed Redis workers for production scale)

---

## Key Features
- **No code reqired, but extensible**: Users that prefer not to touch any code can make their app searchable in a few clicks
- **White-Labeled Multi-Tenant Support**: Ideal for SaaS builders, Airweave provides a streamlined OAuth2-based platform for syncing data across multiple tenants while maintaining privacy and security.
- **Chunk Generators**: Each source (like a database, API, or file system) defines a `async def generate_chunks()` that yields data in a consistent format. You can also define your own.
- **Automated Sync**: Schedule data synchronization or run on-demand sync jobs.
- **Versioning & Hashing**: Airweave detects changes in your data via hashing, updating only the modified chunks in the vector store.
- **Multi-Source Support**: Plug in multiple data sources and unify them into a single queryable layer.
- **Scalable**: Deploy locally via Docker Compose for development (upcoming: deploy with Kubernetes for production scale)


### Components

1. **Frontend (React)**  
   - Provides a dashboard for you to configure your sources, destinations, and sync schedules.  
   - Visualizes sync jobs, logs, and chunk details.

2. **Backend (FastAPI)**  
   - Houses the RESTful endpoints.  
   - Manages data models such as `source`, `destination`, `org`, `user`, `chunk types`, and more.  
   - Allows for automatic synchronization tasks and chunk generation logic.

3. **Chunk Generators**  
   - Integration-specific modules or decorators (e.g., `@chunk_generator`) that define how to fetch and transform source data.  
   - Produces "chunks" of data (text, metadata, etc.) that are hashed to detect changes.

4. **Synchronizers**  
   - Compare generated chunk hashes., 
   - Insert new chunks into the vector DB or mark them for deletion if they're no longer relevant.  
   - Upcoming: run asynchronously, in parallel, to handle large data sets efficiently.

5. **Data Store**  
   - **Postgres** for storing metadata about sources, jobs, users, and schedules.  
   - A **vector database** (currently in the open-core version, it can be anything your Docker Compose config sets up) to store embeddings of your chunks.  
   - Upcoming: **Redis** deployment for caching and queue-based workflows (e.g., background worker tasks).

---

## Technology Stack

- **Frontend**: [React](https://reactjs.org/) (JavaScript/TypeScript)  
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)  
- **Infrastructure**:  
  - Local / Dev: [Docker Compose](https://docs.docker.com/compose/)  
  - Production: (upcoming) [Kubernetes](https://kubernetes.io/)  
- **Databases**:  
  - [PostgreSQL](https://www.postgresql.org/) for relational data  
  - Vector database (your choice, e.g. Chroma, Milvus, Pinecone, Qdrant, Weaviate, etc.)  + (upcoming batteries-included vector DB)
- **Asynchronous Tasks**: [ARQ](https://arq-docs.helpmanual.io/) for background workers

---


## Configuration (Upcoming)

Airweave provides flexibility through environment variables, allowing you to customize key aspects of your deployment. Below are the primary configuration options:


### 1. Bring your own database

You can configure Airweave to use your own PostgreSQL database to store sources, schedules, and metadata. Update the following variables in your `.env` file:

```env
POSTGRES_USER=<your-database-username>
POSTGRES_PASSWORD=<your-database-password>
POSTGRES_DB=<your-database-name>
POSTGRES_HOST=<your-database-host>
POSTGRES_PORT=<your-database-port>\
```

This configuration will create a number of tables within the airweave schema in your specified database. More on this [later](docs.airweave.ai).

### 2. Specify logging destination

You can specify the logging destination. Currently we support Datadog and Sentry.

```env
# Datadog
LOG_DESTINATION=datadog
DATADOG_API_KEY=<your-datadog-api-key>
DATADOG_HOST=<your-datadog-host>
DATADOG_PORT=<your-datadog-port>

# Sentry
LOG_DESTINATION=sentry
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=development
SENTRY_RELEASE=<your-release-name>
```

### 3. Specify SMTP settings

You can specify the SMTP settings in your `.env` file. This is used for sending email notifications.

```env
SMTP_HOST=<your-smtp-host>
SMTP_PORT=<your-smtp-port>
SMTP_USER=<your-smtp-user>
SMTP_PASSWORD=<your-smtp-password>
SMTP_FROM_EMAIL=<your-from-email>
```


## Contributing

We welcome all contributions! Whether you're fixing a bug, improving documentation, or adding a new feature:
1. Fork this repository
2. Create a feature branch: `git checkout -b feature/new-chunk-generator`
3. Commit changes: `git commit -m "Add new chunk generator for XYZ"`
4. Push to your fork: `git push origin feature/new-chunk-generator`
5. Create a Pull Request: Submit your PR against this repo's main branch.

Please follow the existing code style and conventions. See `CONTRIBUTING.md` for more details.

---

## Roadmap

- **Additional Integrations**: Expand chunk generators for popular SaaS APIs and databases.
- **Redis & Worker Queues**: Improved background job processing and caching for large or frequent syncs.
- **Webhooks**: Trigger syncs on external events (e.g. new data in a database)
- **Kubernetes Support**: Offer easy Helm charts for production-scale deployments.
- **Commercial Offerings**: Enterprise features, extended metrics, and priority support.

---

## License

Airweave is released under an open-core model. The community edition is licensed under MIT License. Additional modules (for enterprise or advanced features) may be licensed separately.

---

## Contact & Community
- **Discord**: Join our Discord channel [here](https://discord.gg/r2cF7V6s) to get help or discuss features.
- **GitHub Issues**: Report bugs or request new features in GitHub Issues.
- **Twitter**: Follow @airweave_dev for updates.

That's it! We're looking forward to seeing what you build. If you have any questions, please don't hesitate to open an issue or reach out on Discord.

## Further Documentation

- [White Label Multi-Tenancy](./docs/white-label.md) - Learn how Airweave's white label feature works with multi-tenant integrations
