# Auth0 Organizations Setup Guide

This guide walks you through setting up Auth0 Organizations integration for Airweave.

## Prerequisites

1. Auth0 account with Organizations feature enabled
2. Existing Auth0 application for Airweave frontend (SPA)

## Setup Steps

### 1. Create Machine-to-Machine Application

1. Go to Auth0 Dashboard → Applications
2. Click "Create Application"
3. Choose "Machine to Machine Applications"
4. Name it "Airweave Management API"
5. Select "Auth0 Management API" as the API
6. Grant the following scopes:
   - `read:organizations`
   - `create:organizations`
   - `update:organizations`
   - `read:organization_members`
   - `create:organization_members`
   - `create:organization_invitations`
   - `read:organization_invitations`

### 2. Environment Configuration

Add these variables to your `.env` file:

```bash
# Enable Auth0
AUTH_ENABLED=true
AUTH0_DOMAIN="your-domain.auth0.com"
AUTH0_AUDIENCE="your-api-audience"
AUTH0_RULE_NAMESPACE="https://airweave.ai/"

# SPA Client (existing)
AUTH0_CLIENT_ID="your-spa-client-id"

# Machine-to-Machine Client (new)
AUTH0_M2M_CLIENT_ID="your-m2m-client-id"
AUTH0_M2M_CLIENT_SECRET="your-m2m-client-secret"
```

### 3. Auth0 Rules (Optional)

For enhanced organization management, you can create Auth0 Rules to automatically assign users to organizations based on email domains or other criteria.

## Features Enabled

With this setup, Airweave gains:

1. **Organization Creation**: New organizations are automatically created in Auth0
2. **User Sync**: User organization memberships are synced from Auth0
3. **Invitation Flow**: Organization invitations are sent via Auth0
4. **Multi-Org Support**: Users can belong to multiple organizations
5. **Graceful Degradation**: If Auth0 API is unavailable, local-only organizations still work

## Testing

1. Create a new organization in Airweave
2. Check Auth0 Dashboard → Organizations to see it was created
3. Invite a user to the organization
4. Verify the invitation was sent via Auth0

## Troubleshooting

### Common Issues

1. **"Auth0 Management API not configured"**
   - Ensure `AUTH0_M2M_CLIENT_ID` and `AUTH0_M2M_CLIENT_SECRET` are set
   - Verify the M2M application has the correct scopes

2. **Organization creation fails**
   - Check logs for Auth0 API errors
   - Verify your Auth0 plan supports Organizations
   - Ensure the M2M application has `create:organizations` scope

3. **Users not syncing organizations**
   - Check that users have valid `auth0_id` values
   - Verify the M2M application has `read:organizations` scope
   - Check logs for Auth0 API rate limiting

### Logs

Monitor these log messages:
- `Successfully created Auth0 organization`
- `Failed to create Auth0 organization, continuing with local-only`
- `Syncing X Auth0 organizations for user`

## Graceful Degradation

The system is designed to work even if Auth0 Organizations is not available:

1. **No M2M Credentials**: Organizations are created locally only
2. **Auth0 API Down**: Falls back to local organization management
3. **Rate Limiting**: Continues with local operations and retries later

This ensures Airweave remains functional even during Auth0 service interruptions.
