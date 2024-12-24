# Airweave

**Airweave** is an open-core tool that makes **any app searchable** by unifying your apps, APIs, and databases into vector databases with minimal configuration. With Airweave, you can quickly find the needle in any of your application haystacks—and fuel the agent economy with relevant data.

---

## Table of Contents

1. [Overview](#overview)  
2. [Key Features](#key-features)  
3. [Architecture](#architecture)  
4. [Technology Stack](#technology-stack)  
5. [Quick Start](#quick-start)  
6. [Configuration](#configuration)  
7. [Usage](#usage)  
8. [Contributing](#contributing)  
9. [Roadmap](#roadmap)  
10. [License](#license)

---

## Overview

Airweave aims to simplify the process of making any data source searchable. Whether you have structured or unstructured data, Airweave helps you break it into processable chunks, store the data in a vector database, and retrieve it via your own agent or any search mechanism.

### Why Airweave?

- **Simplicity**: Minimal configuration needed to sync data from diverse sources (APIs, databases, and more).
- **Extensibility**: Easily add new integrations via `@chunk_generators`.
- **Open-Core**: Core features are open source, ensuring transparency. Future commercial offerings will bring additional, advanced capabilities.
- **Async-First**: Built to handle large-scale data synchronization asynchronously.

---

## Key Features

- **Chunk Generators**: Each source (like a database, API, or file system) can define a `@chunk_generator` that yields data in a consistent format.
- **Automated Sync**: Schedule data synchronization using a CRON-like system or run on-demand sync jobs.
- **Versioning & Hashing**: Airweave detects changes in your data via hashing, updating only the modified chunks in the vector store.
- **Multi-Source Support**: Plug in multiple data sources and unify them into a single queryable layer.
- **Scalable**: Deploy locally via Docker Compose for development, or scale with Terraform + K8s for production.

---

## Architecture

At a high level, Airweave consists of three main components: **Frontend**, **Backend**, and **Synchronizers**.

           ┌──────────────┐
           │   Your App   │
           └─────┬────────┘
                 │
                 ▼
       ┌───────────────────┐
       │   Airweave API    │  (FastAPI)
       └───────────────────┘
        /        |        \
       /         |         \
      ▼          ▼          ▼
┌────────┐   ┌────────┐   ┌────────┐
│ Source │   │ Source │   │ Source │ ... (Any number of integrations)
└────────┘   └────────┘   └────────┘
            \     |     /
             \    |    /
              ▼   ▼   ▼
       ┌────────────────────┐
       │   Chunk Generators │
       └────────────────────┘
                 │
                 ▼
       ┌───────────────────┐
       │  Synchronizer(s)  │
       └───────────────────┘
                 │
                 ▼
       ┌───────────────────┐
       │ Vector Database(s)│
       └───────────────────┘


### Components

1. **Frontend (React)**  
   - Provides a dashboard for you to configure your sources, destinations, and sync schedules.  
   - Visualizes sync jobs, logs, and chunk details.

2. **Backend (FastAPI)**  
   - Houses the RESTful (and in the future, possibly GraphQL) API endpoints.  
   - Manages data models such as `source`, `destination`, `org`, `user`, `chunk types`, and more.  
   - Orchestrates synchronization tasks and chunk generation logic.

3. **Chunk Generators**  
   - Integration-specific modules or decorators (e.g., `@chunk_generator`) that define how to fetch and transform source data.  
   - Produces “chunks” of data (text, metadata, etc.) that are hashed to detect changes.

4. **Synchronizers**  
   - Continuously or periodically compare generated chunk hashes.  
   - Insert new chunks into the vector DB or mark them for deletion if they’re no longer relevant.  
   - Operate asynchronously, in parallel, to handle large data sets efficiently.

5. **Data Store**  
   - **Postgres** for storing metadata about sources, jobs, users, and schedules.  
   - A **vector database** (currently in the open-core version, it can be anything your Docker Compose config sets up) to store embeddings of your chunks.  
   - Planned **Redis** deployment for caching and queue-based workflows (e.g., background worker tasks).

---

## Technology Stack

- **Frontend**: [React](https://reactjs.org/) (JavaScript/TypeScript)  
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)  
- **Infrastructure**:  
  - Local / Dev: [Docker Compose](https://docs.docker.com/compose/)  
  - Production: [Terraform](https://www.terraform.io/) + (upcoming) [Kubernetes](https://kubernetes.io/)  
- **Databases**:  
  - [PostgreSQL](https://www.postgresql.org/) for relational data  
  - Vector database (your choice, e.g. Pinecone, Weaviate, Milvus, etc.)  + (upcoming batteries-included vector DB)
- **Asynchronous Tasks**: [ARQ](https://arq.readthedocs.io/en/latest/) for background workers

---

## Quick Start

Below is a simple guide to get Airweave up and running locally. For more detailed instructions, refer to the [docs](#).

### Prerequisites

- **Docker** (v20+)  
- **Docker Compose** (v2.0+)

### Steps

1. **Clone the Repository**  
   ```bash
   git clone https://github.com/yourusername/airweave.git
   cd airweave

2. **Set Up Environment Variables**  
   Copy .env.example to .env and update any necessary variables, such as Postgres connection strings or credentials.

3. **Build and Run**  
   ```bash
   docker-compose up --build
   ```

That’s it!

You now have Airweave running locally. You can log in to the dashboard, add new sources, and configure your sync schedules.


---

## Configuration

Airweave is highly configurable. Here are a few key settings and how to change them:
	1.	Database Settings
	    •	Defined in your .env file under variables like POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, etc.
	    •	Make sure to keep your credentials secure, especially in production.
	2.	Vector Database
	    •	By default, Airweave can be pointed to any vector DB of your choice.
	    •	Set environment variables such as VECTORDB_URL, VECTORDB_API_KEY, etc., depending on the vendor.
	3.	Chunk Generators
	    •	Add or customize existing chunk generators in the src/backend/integrations/ directory.
	•	Each generator is annotated with @chunk_generator (or a similar mechanism) and defines how data is fetched from the source.
	4.	Cron-Like Sync Scheduling
	•	In the sync_schedule table, define schedules using cron expressions or any scheduling format you prefer.
	•	The synchronizer picks up these schedules and runs them asynchronously.

---

## Usage

Below are some basic commands and API endpoints that you may find useful.

CLI Commands
	•	Run Tests: (If you have a test suite set up for your own code) docker-compose exec backend pytest
	•	Start in Dev Mode: docker-compose up --build

API Endpoints (FastAPI)
	•	Swagger Documentation: http://localhost:8000/docs
	•	Get All Sources: GET /api/sources

•	**Create a Source: POST /api/sources**

```json
{
  "name": "My Data Source",
  "type": "postgres",
  "connection_info": {...}
}
```

	•	**Trigger a Sync Job: POST /api/sync_jobs**

```json
{
  "source_id": 123,
  "schedule_id": null
}
```

	•	**Get Sync Job Status: GET /api/sync_jobs/{job_id}**

```json
{
  "status": "running",
  "chunks_processed": 100,
  "chunks_total": 200
}
```

### Frontend
	•	Access the React UI at http://localhost:3000.
	•	Navigate to Sources to add new integrations.
	•	Set up or view your sync schedules under Schedules.
	•	Monitor sync jobs in Jobs.

---

## Contributing

We welcome all contributions! Whether you’re fixing a bug, improving documentation, or adding a new feature:
	1.	Fork this repository
	2.	Create a feature branch: git checkout -b feature/new-chunk-generator
	3.	Commit changes: git commit -m "Add new chunk generator for XYZ"
	4.	Push to your fork: git push origin feature/new-chunk-generator
	5.	Create a Pull Request: Submit your PR against this repo’s main branch.

Please follow the existing code style and conventions. See CONTRIBUTING.md for more details.

---

## Roadmap

	•	Additional Integrations: Expand chunk generators for popular SaaS APIs and databases.
	•	Kubernetes Support: Offer easy Helm charts for production-scale deployments.
	•	Redis & Worker Queues: Improved background job processing and caching for large or frequent syncs.
	•	GraphQL Interface: A flexible alternative to the RESTful API.
	•	Commercial Offerings: Enterprise features, extended metrics, and priority support.

---

## License

Airweave is released under an open-core model. The community edition is licensed under MIT License. Additional modules (for enterprise or advanced features) may be licensed separately.

---

## Contact & Community
	•	Discord: Join our Discord channel to get help or discuss features.
	•	GitHub Issues: Report bugs or request new features in GitHub Issues.
	•	Twitter: Follow @airweave_dev for updates.

That’s it! Thanks for checking out Airweave — we're looking forward to seeing what you build. If you have any questions, please don’t hesitate to open an issue or reach out on Discord.

Happy chunking!