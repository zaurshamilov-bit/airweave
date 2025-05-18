"""Configuration classes for platform components."""

from pydantic import Field

from airweave.platform.configs._base import BaseConfig


class SourceConfig(BaseConfig):
    """Source config schema."""

    pass


class AsanaConfig(SourceConfig):
    """Asana configuration schema."""

    exclude_path: str = Field(
        title="Exclude Path",
        description="Path's in the Asana Repository, you want to exclude from Airweave's scope",
    )


class ClickUpConfig(SourceConfig):
    """ClickUp configuration schema."""

    pass


class ConfluenceConfig(SourceConfig):
    """Confluence configuration schema."""

    pass


class DropboxConfig(SourceConfig):
    """Dropbox configuration schema."""

    exclude_path: str = Field(
        title="Exclude Path",
        description="Path's in the Dropbox Repository, you want to exclude from Airweave's scope",
    )


class ElasticsearchConfig(SourceConfig):
    """Elasticsearch configuration schema."""

    pass


class GithubConfig(SourceConfig):
    """Github configuration schema."""

    exclude_path: str = Field(
        title="Exclude Path",
        description="Path's in the Github Repository, you want to exclude from Airweave's scope",
    )


class GmailConfig(SourceConfig):
    """Gmail configuration schema."""

    pass


class GoogleCalendarConfig(SourceConfig):
    """Google Calendar configuration schema."""

    pass


class GoogleDriveConfig(SourceConfig):
    """Google Drive configuration schema."""

    pass


class HubspotConfig(SourceConfig):
    """Hubspot configuration schema."""

    pass


class IntercomConfig(SourceConfig):
    """Intercom configuration schema."""

    pass


class JiraConfig(SourceConfig):
    """Jira configuration schema."""

    pass


class LinearConfig(SourceConfig):
    """Linear configuration schema."""

    exclude_path: str = Field(
        title="Exclude Path",
        description="Path's in the Linear Repository, you want to exclude from Airweave's scope",
    )


class MondayConfig(SourceConfig):
    """Monday configuration schema."""

    pass


class MySQLConfig(SourceConfig):
    """MySQL configuration schema."""

    pass


class NotionConfig(SourceConfig):
    """Notion configuration schema."""

    pass


class OneDriveConfig(SourceConfig):
    """OneDrive configuration schema."""

    pass


class OracleConfig(SourceConfig):
    """Oracle configuration schema."""

    pass


class OutlookCalendarConfig(SourceConfig):
    """Outlook Calendar configuration schema."""

    pass


class OutlookMailConfig(SourceConfig):
    """Outlook Mail configuration schema."""

    pass


class PostgresConfig(SourceConfig):
    """Postgres configuration schema."""

    pass


class SlackConfig(SourceConfig):
    """Slack configuration schema."""

    pass


class SqlServerConfig(SourceConfig):
    """SQL Server configuration schema."""

    pass


class SqliteConfig(SourceConfig):
    """Sqlite configuration schema."""

    pass


class StripeConfig(SourceConfig):
    """Stripe configuration schema."""

    pass


class TodoistConfig(SourceConfig):
    """Todoist configuration schema."""

    pass


class TrelloConfig(SourceConfig):
    """Trello configuration schema."""

    pass


class ZenDeskConfig(SourceConfig):
    """ZenDesk configuration schema."""

    pass
