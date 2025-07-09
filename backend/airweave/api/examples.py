"""Reusable API response examples for consistent documentation."""

# SourceConnectionJob examples for different states
SOURCE_CONNECTION_JOB_EXAMPLES = {
    "completed": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-15T14:00:00Z",
        "modified_at": "2024-01-15T14:05:22Z",
        "status": "completed",
        "entities_inserted": 45,
        "entities_updated": 12,
        "entities_deleted": 3,
        "entities_kept": 234,
        "entities_skipped": 8,
        "entities_encountered": {
            "issues": 67,
            "pull_requests": 23,
            "commits": 156,
            "releases": 12,
            "readme_files": 8,
        },
        "started_at": "2024-01-15T14:00:15Z",
        "completed_at": "2024-01-15T14:05:22Z",
        "failed_at": None,
        "error": None,
    },
    "pending": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-15T16:30:00Z",
        "modified_at": "2024-01-15T16:30:00Z",
        "status": "pending",
        "entities_inserted": 0,
        "entities_updated": 0,
        "entities_deleted": 0,
        "entities_kept": 0,
        "entities_skipped": 0,
        "entities_encountered": {},
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "error": None,
    },
    "cancelled": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "987fcdeb-51a2-43d7-8f3e-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-15T14:00:00Z",
        "modified_at": "2024-01-15T14:02:30Z",
        "status": "cancelled",
        "entities_inserted": 12,
        "entities_updated": 3,
        "entities_deleted": 0,
        "entities_kept": 89,
        "entities_skipped": 2,
        "entities_encountered": {
            "issues": 23,
            "pull_requests": 8,
            "commits": 67,
        },
        "started_at": "2024-01-15T14:00:15Z",
        "completed_at": None,
        "failed_at": "2024-01-15T14:02:30Z",
        "error": "Job cancelled by user",
    },
    "failed": {
        "source_connection_id": "550e8400-e29b-41d4-a716-446655440000",
        "id": "abc12345-67ef-89ab-cdef-1234567890ab",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "engineering@company.com",
        "modified_by_email": "engineering@company.com",
        "created_at": "2024-01-14T08:00:00Z",
        "modified_at": "2024-01-14T08:02:30Z",
        "status": "failed",
        "entities_inserted": 0,
        "entities_updated": 0,
        "entities_deleted": 0,
        "entities_kept": 0,
        "entities_skipped": 0,
        "entities_encountered": {},
        "started_at": "2024-01-14T08:00:15Z",
        "completed_at": None,
        "failed_at": "2024-01-14T08:02:30Z",
        "error": "Authentication failed: GitHub personal access token is invalid or expired",
    },
}

# SourceConnectionListItem examples for different scenarios
SOURCE_CONNECTION_LIST_EXAMPLES = {
    "engineering_docs": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "GitHub - Engineering Documentation",
        "description": "Sync technical documentation and code from our engineering repos",
        "short_name": "github",
        "status": "active",
        "created_at": "2024-01-15T09:30:00Z",
        "modified_at": "2024-01-15T14:22:15Z",
        "sync_id": "123e4567-e89b-12d3-a456-426614174000",
        "collection": "engineering-docs-ab123",
        "white_label_id": None,
    },
    "white_label_slack": {
        "id": "white123-4567-89ab-cdef-012345678901",
        "name": "Customer Slack Workspace",
        "description": (
            "Team communications and project discussions from customer's Slack workspace"
        ),
        "short_name": "slack",
        "status": "active",
        "created_at": "2024-01-16T10:15:00Z",
        "modified_at": "2024-01-16T10:15:00Z",
        "sync_id": "wl456789-abcd-ef01-2345-67890abcdef1",
        "collection": "customer-communications-xy789",
        "white_label_id": "wl123456-789a-bcde-f012-345678901234",
    },
}

# Source examples for different source types
SOURCE_EXAMPLES = {
    "github": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "GitHub",
        "description": (
            "Connect to GitHub repositories for code, issues, pull requests, and documentation"
        ),
        "auth_type": "config_class",
        "auth_config_class": "GitHubAuthConfig",
        "config_class": "GitHubConfig",
        "short_name": "github",
        "class_name": "GitHubSource",
        "output_entity_definition_ids": [
            "def12345-6789-abcd-ef01-234567890abc",
            "def67890-abcd-ef01-2345-67890abcdef1",
        ],
        "organization_id": None,
        "labels": ["code"],
        "created_at": "2024-01-01T00:00:00Z",
        "modified_at": "2024-01-01T00:00:00Z",
        "auth_fields": {
            "fields": [
                {
                    "name": "personal_access_token",
                    "title": "Personal Access Token",
                    "description": "GitHub Personal Access Token with repository read permissions",
                    "type": "string",
                    "secret": True,
                },
                {
                    "name": "repo_name",
                    "title": "Repository Name",
                    "description": "Full repository name in format 'owner/repo'",
                    "type": "string",
                },
            ]
        },
    },
}

# Collection examples for different scenarios
COLLECTION_EXAMPLES = {
    "finance_data": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Finance Data",
        "readable_id": "finance-data-ab123",
        "created_at": "2024-01-15T09:30:00Z",
        "modified_at": "2024-01-15T14:22:15Z",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_by_email": "admin@company.com",
        "modified_by_email": "finance@company.com",
        "status": "ACTIVE",
    },
}

# White label examples for different source types
WHITE_LABEL_EXAMPLES = {
    "github_integration": {
        "id": "white789-0abc-def0-1234-567890abcdef",
        "name": "Support Team GitHub Integration",
        "source_short_name": "github",
        "redirect_url": "https://support.yoursite.com/integrations/github/callback",
        "client_id": "Iv1.a1b2c3d4e5f6g7h8",
        "client_secret": "1234567890abcdef1234567890abcdef12345678",
        "allowed_origins": "https://support.yoursite.com,https://internal.yoursite.com",
        "organization_id": "org12345-6789-abcd-ef01-234567890abc",
        "created_at": "2024-01-05T16:45:00Z",
        "modified_at": "2024-01-14T10:20:00Z",
        "created_by_email": "support@company.com",
        "modified_by_email": "admin@company.com",
    },
}


# Helper functions to generate response examples
def create_single_job_response(status: str, summary: str):
    """Create a single job response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        f"{status}_job": {
                            "summary": summary,
                            "value": SOURCE_CONNECTION_JOB_EXAMPLES[status],
                        }
                    }
                }
            },
        }
    }


def create_job_list_response(job_statuses: list, summary: str):
    """Create a job list response example with multiple jobs."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "sync_job_history": {
                            "summary": summary,
                            "value": [
                                SOURCE_CONNECTION_JOB_EXAMPLES[status] for status in job_statuses
                            ],
                        }
                    }
                }
            },
        }
    }


def create_source_connection_list_response(connection_types: list, summary: str):
    """Create a source connection list response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "source_connections_list": {
                            "summary": summary,
                            "value": [
                                SOURCE_CONNECTION_LIST_EXAMPLES[conn_type]
                                for conn_type in connection_types
                            ],
                        }
                    }
                }
            },
        }
    }


def create_single_source_response(source_type: str, summary: str):
    """Create a single source response example."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        f"{source_type}_source": {
                            "summary": summary,
                            "value": SOURCE_EXAMPLES[source_type],
                        }
                    }
                }
            },
        }
    }


def create_source_list_response(source_types: list, summary: str):
    """Create a source list response example with multiple sources."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "available_sources": {
                            "summary": summary,
                            "value": [SOURCE_EXAMPLES[source_type] for source_type in source_types],
                        }
                    }
                }
            },
        }
    }


def create_collection_list_response(collection_types: list, summary: str):
    """Create a collection list response example with multiple collections."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "collections_list": {
                            "summary": summary,
                            "value": [
                                COLLECTION_EXAMPLES[collection_type]
                                for collection_type in collection_types
                            ],
                        }
                    }
                }
            },
        }
    }


def create_white_label_list_response(white_label_types: list, summary: str):
    """Create a white label list response example with multiple white label integrations."""
    return {
        "200": {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "examples": {
                        "white_labels_list": {
                            "summary": summary,
                            "value": [
                                WHITE_LABEL_EXAMPLES[white_label_type]
                                for white_label_type in white_label_types
                            ],
                        }
                    }
                }
            },
        }
    }
