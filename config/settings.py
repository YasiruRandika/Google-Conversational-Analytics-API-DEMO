"""
Settings Module for DataChat Application
=========================================

LEARNING NOTES:
--------------
This module uses Pydantic Settings to manage application configuration.
Key design decisions:
  1. Environment variables with .env file support (12-factor app pattern)
  2. Typed configuration with validation
  3. Centralized settings — one place to configure everything
  4. Default values for quick start with BigQuery public datasets

The Conversational Analytics API uses:
  - GCP_PROJECT_ID: Your billing project (where APIs are enabled)
  - GCP_LOCATION: Always "global" for this API
  - The API endpoint is geminidataanalytics.googleapis.com
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ---------------------------------------------------------------
    # Google Cloud Configuration
    # ---------------------------------------------------------------
    gcp_project_id: str = Field(
        default="",
        description="Google Cloud project ID where Conversational Analytics API is enabled"
    )
    gcp_location: str = Field(
        default="global",
        description="API location — always 'global' for Conversational Analytics API"
    )
    google_application_credentials: Optional[str] = Field(
        default=None,
        description="Path to service account JSON key file (recommended for production)"
    )

    # ---------------------------------------------------------------
    # Agent Configuration
    # ---------------------------------------------------------------
    default_agent_id: str = Field(
        default="datachat_agent",
        description="Default data agent identifier"
    )
    default_conversation_id: Optional[str] = Field(
        default=None,
        description="Default conversation ID (auto-generated if not set)"
    )

    # ---------------------------------------------------------------
    # BigQuery Data Source Configuration
    # ---------------------------------------------------------------
    bq_project_id: str = Field(
        default="bigquery-public-data",
        description="BigQuery project containing the dataset"
    )
    bq_dataset_id: str = Field(
        default="thelook_ecommerce",
        description="BigQuery dataset ID"
    )
    bq_table_ids: str = Field(
        default="orders,order_items,products,users",
        description="Comma-separated BigQuery table IDs"
    )

    # ---------------------------------------------------------------
    # Feature Flags
    # ---------------------------------------------------------------
    enable_python_analysis: bool = Field(
        default=True,
        description="Enable Python-based advanced analysis in the agent"
    )
    enable_chart_rendering: bool = Field(
        default=True,
        description="Enable chart rendering from API chart specs"
    )
    conversation_mode: str = Field(
        default="stateful",
        description="Conversation mode: 'stateful' (recommended, API manages history) or 'stateless' (app manages history)"
    )

    # ---------------------------------------------------------------
    # App Display Settings
    # ---------------------------------------------------------------
    app_title: str = Field(
        default="DataChat",
        description="Application title shown in the UI"
    )
    app_description: str = Field(
        default="Chat with your data using Google Cloud Conversational Analytics API",
        description="Application description"
    )
    max_message_history: int = Field(
        default=50,
        description="Maximum messages to display in chat history"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    # ---------------------------------------------------------------
    # Helper Properties
    # ---------------------------------------------------------------
    @property
    def table_ids_list(self) -> list[str]:
        """Parse comma-separated table IDs into a list."""
        return [t.strip() for t in self.bq_table_ids.split(",") if t.strip()]

    @property
    def agent_resource_name(self) -> str:
        """Full resource name for the data agent."""
        return f"projects/{self.gcp_project_id}/locations/{self.gcp_location}/dataAgents/{self.default_agent_id}"

    @property
    def parent_resource(self) -> str:
        """Parent resource path for API calls."""
        return f"projects/{self.gcp_project_id}/locations/{self.gcp_location}"

    def validate_required(self) -> list[str]:
        """Check if required settings are configured. Returns list of missing items."""
        missing = []
        if not self.gcp_project_id:
            missing.append("GCP_PROJECT_ID")
        return missing


# Singleton instance
settings = Settings()
