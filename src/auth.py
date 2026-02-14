"""
Authentication Module for DataChat
====================================

LEARNING NOTES:
--------------
The Conversational Analytics API supports two authentication approaches:

1. APPLICATION DEFAULT CREDENTIALS (ADC) — What we use here
   - Best for development and server-to-server communication
   - Set up via: gcloud auth application-default login
   - The SDK automatically picks up credentials from the environment
   - No manual token management needed

2. HTTP APPROACH (for direct REST calls)
   - Requires manually getting an access token
   - Token has an expiry (usually 1 hour)
   - Must refresh token before it expires

WHY WE USE THE SDK APPROACH:
- The Python SDK (google-cloud-geminidataanalytics) handles auth automatically
- It uses ADC under the hood
- No need to manage tokens, refresh cycles, or headers
- Cleaner code, fewer auth-related bugs

PREREQUISITES:
1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
2. Run: gcloud auth application-default login
3. Enable required APIs:
   - gcloud services enable geminidataanalytics.googleapis.com
   - gcloud services enable cloudaicompanion.googleapis.com
   - gcloud services enable bigquery.googleapis.com
"""

import logging
from typing import Optional, Tuple

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


def get_credentials() -> Tuple[Optional[Credentials], Optional[str]]:
    """
    Get Google Cloud credentials using Application Default Credentials (ADC).

    Returns:
        Tuple of (credentials, project_id)
        - credentials: Google auth credentials object
        - project_id: The default project from gcloud config

    How ADC works:
    1. Checks GOOGLE_APPLICATION_CREDENTIALS env var (service account JSON)
    2. Checks gcloud auth application-default credentials
    3. Checks GCE/Cloud Run/Cloud Functions metadata server
    """
    try:
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        logger.info(f"Authenticated successfully. Default project: {project}")
        return credentials, project
    except google.auth.exceptions.DefaultCredentialsError as e:
        logger.error(f"Authentication failed: {e}")
        logger.error(
            "Please run 'gcloud auth application-default login' to authenticate."
        )
        return None, None


def validate_credentials(credentials: Optional[Credentials]) -> bool:
    """
    Validate that credentials are present and can be refreshed.

    LEARNING NOTE:
    Credentials can expire. The google-auth library handles refresh
    automatically in most cases, but we validate here to give
    users a clear error message early.
    """
    if credentials is None:
        return False

    try:
        # Attempt to refresh the token to verify it works
        if credentials.expired or not credentials.token:
            credentials.refresh(Request())
        return True
    except Exception as e:
        logger.error(f"Credential validation failed: {e}")
        return False


def get_access_token(credentials: Credentials) -> Optional[str]:
    """
    Get a fresh access token from credentials.

    LEARNING NOTE:
    This is useful if you need to make direct HTTP requests
    instead of using the SDK. The HTTP approach requires you to
    include this token in the Authorization header:
        headers = {"Authorization": f"Bearer {token}"}
    """
    try:
        if credentials.expired or not credentials.token:
            credentials.refresh(Request())
        return credentials.token
    except Exception as e:
        logger.error(f"Failed to get access token: {e}")
        return None


def check_auth_status() -> dict:
    """
    Check authentication status and return a detailed status report.
    Useful for the Streamlit UI to show auth state.
    """
    status = {
        "authenticated": False,
        "project_id": None,
        "error": None,
        "instructions": None,
    }

    credentials, project = get_credentials()

    if credentials is None:
        status["error"] = "No credentials found"
        status["instructions"] = (
            "Run the following commands to authenticate:\n"
            "1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install\n"
            "2. gcloud auth application-default login\n"
            "3. gcloud config set project YOUR_PROJECT_ID"
        )
        return status

    if validate_credentials(credentials):
        status["authenticated"] = True
        status["project_id"] = project
    else:
        status["error"] = "Credentials found but could not be validated"
        status["instructions"] = (
            "Try re-authenticating:\n"
            "gcloud auth application-default login"
        )

    return status
