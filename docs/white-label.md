# How Airweave White Label Multi-Tenancy Works

Airweave enables **white-labeled multi-tenant integrations** that let your SaaS app sync customer data from various sources (like CRMs, databases, or file systems) while ensuring data isolation and security for each tenant.

---

## What Happens During Setup?

1. **Configure an OAuth2 Integration**:
   - Go to the Airweave dashboard, navigate to **"White Label"**, and click **"Create White Label Integration."**
   - Fill in the following details:
     - **Integration Name**
     - **Source**: Select a data source (e.g., Slack, Google Drive).
     - **Frontend Callback URL**: URL where the OAuth2 provider will redirect after authorization.
     - **Client ID** and **Client Secret**: Credentials from your OAuth2 provider.
   - Save the configuration. Airweave now knows how to communicate with the external service for your tenants.

2. **Set Up OAuth2 Authorization Flow**:
   - Add a "Connect to Service" button in your app.
   - This button redirects users to the external service’s OAuth2 authorization page.
   - After the user grants access, they are redirected to your callback URL with a temporary `code`.

3. **Exchange the Code for a Token**:
   - At the callback URL, Airweave exchanges the `code` with the external service for:
     - **Access Token**: Used to access the user’s data.
     - **Refresh Token**: Used to renew the Access Token when it expires (if supported by the service).

---

## What Does Airweave Do With the Tokens?

1. **Token Storage**:
   - Airweave securely stores the **Access Token** and **Refresh Token** (if applicable).
   - Tokens are linked to the metadata you provide (e.g., user email, organization ID) for tenant isolation.

2. **Token Usage**:
   - When your app requests data, Airweave uses the stored **Access Token** to authenticate API calls to the external service.
   - Your app doesn’t need to handle tokens directly, simplifying implementation.

3. **Token Refresh**:
   - If the Access Token expires, Airweave automatically uses the **Refresh Token** to obtain a new Access Token.
   - This ensures uninterrupted synchronization without user involvement.

---

## How Airweave Handles Data Synchronization

1. **Data Sync Jobs**:
   - After OAuth2 flow completion, Airweave starts syncing data from the source (e.g., Slack) to the destination (e.g., a vector database).
   - Syncs are incremental, fetching only new or updated data to optimize performance.

2. **Metadata Handling**:
   - During the OAuth2 callback, you can include metadata like:
     - **User Details** (e.g., email, ID).
     - **Organization Details** (e.g., name, ID).
   - This metadata helps Airweave manage and isolate data per tenant.

3. **Data Transformation**:
   - Airweave processes the data into smaller **chunks**, applies versioning, and computes hashes.
   - This ensures efficient updates and deduplication.

---

## Key Features of Airweave's White Label Multi-Tenancy

1. **Simplified OAuth2 Integration**:
   - Airweave handles the complexities of OAuth2, including token management and API calls.
2. **Multi-Tenant Isolation**:
   - Each tenant’s data is securely isolated using the metadata you provide.
3. **Automatic Token Management**:
   - Airweave ensures tokens are refreshed automatically to prevent downtime.
4. **Customizable Data Sync**:
   - Control which sources and destinations are synced and enrich data with tenant-specific metadata.
5. **Scalable Synchronization**:
   - Airweave processes large volumes of data asynchronously for efficient operations.

---

## Example Workflow

1. A customer clicks the "Connect to Service" button in your app and authorizes access to their Slack workspace.
2. Airweave receives the temporary `code` and exchanges it for Access and Refresh Tokens.
3. Airweave securely stores the tokens and starts syncing data from Slack to your configured destination (e.g., a vector database).
4. Your app queries Airweave’s API to search or retrieve the synchronized data using the customer’s metadata (e.g., organization ID or user email).

---

This setup allows you to offer robust data-sync features with minimal backend coding, ensuring secure, scalable, and tenant-aware operations.