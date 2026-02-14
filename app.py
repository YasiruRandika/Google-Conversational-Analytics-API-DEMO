"""
DataChat — Main Streamlit Application
=======================================

LEARNING NOTES:
--------------
This is the entry point for the DataChat application. It brings together:
1. Authentication (src/auth.py)
2. Agent Management (src/agent_manager.py)
3. Chat Handling (src/chat_handler.py)
4. Visualization (src/visualization.py)

ARCHITECTURE:
                    ┌─────────────────────────────┐
                    │     STREAMLIT UI (app.py)    │
                    │  ┌─────────┐  ┌───────────┐ │
                    │  │  Chat   │  │  Sidebar  │ │
                    │  │  Panel  │  │  Config   │ │
                    │  └────┬────┘  └─────┬─────┘ │
                    └───────┼─────────────┼───────┘
                            │             │
                    ┌───────▼─────────────▼───────┐
                    │     BACKEND MODULES          │
                    │  auth → agent_mgr → chat     │
                    │           → visualization    │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │  CONVERSATIONAL ANALYTICS API │
                    │  geminidataanalytics.google   │
                    │  apis.com                     │
                    └──────────────────────────────┘

RUN WITH:
    streamlit run app.py

    OR from the DataChat directory:
    python -m streamlit run app.py
"""

import sys
import os
import logging
from pathlib import Path

# Load .env BEFORE any Google Cloud imports
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd

# Add project root to path for imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings

# Set GOOGLE_APPLICATION_CREDENTIALS if configured in settings
# This tells the Google Cloud SDK to use the service account key file
if settings.google_application_credentials:
    key_path = Path(settings.google_application_credentials)
    if not key_path.is_absolute():
        key_path = project_root / key_path
    if key_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(key_path)
        logging.info(f"Using service account: {key_path}")
    else:
        logging.warning(f"Service account key not found: {key_path}")
from src.auth import check_auth_status, get_credentials
from src.agent_manager import AgentManager
from src.chat_handler import ChatHandler, ChatMessage
from src.visualization import (
    render_chart_from_spec,
    create_chart_from_data,
    data_to_dataframe,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title=settings.app_title,
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a modern, clean look
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a73e8;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #5f6368;
        margin-bottom: 1.5rem;
    }

    /* Chat message styling */
    .stChatMessage {
        padding: 0.75rem 1rem;
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .status-success {
        background-color: #e6f4ea;
        color: #137333;
    }
    .status-error {
        background-color: #fce8e6;
        color: #c5221f;
    }
    .status-warning {
        background-color: #fef7e0;
        color: #b05a00;
    }

    /* Reasoning expander */
    .reasoning-text {
        font-size: 0.85rem;
        color: #5f6368;
        font-style: italic;
    }

    /* SQL display */
    .sql-display {
        background-color: #f8f9fa;
        border-left: 3px solid #4285f4;
        padding: 0.75rem;
        border-radius: 0 4px 4px 0;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1.25rem;
        color: white;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """
    Initialize Streamlit session state variables.

    LEARNING NOTE:
    Streamlit re-runs the entire script on every interaction.
    Session state persists data across re-runs. We use it for:
    - Chat history (messages displayed in the UI)
    - API client instances (avoid re-creating on every interaction)
    - Conversation references (to maintain stateful chat)
    - UI state (sidebar selections, toggles)
    """
    defaults = {
        "messages": [],  # Chat messages for display
        "agent_manager": None,  # AgentManager instance
        "chat_handler": None,  # ChatHandler instance
        "conversation_name": None,  # Current conversation resource name
        "agent_id": settings.default_agent_id,  # Current agent ID
        "agent_created": False,  # Whether the agent has been created
        "authenticated": False,  # Auth status
        "show_reasoning": False,  # Toggle for reasoning steps
        "show_sql": True,  # Toggle for SQL display
        "setup_complete": False,  # Whether initial setup is done
        "project_id": settings.gcp_project_id,  # GCP project ID (editable)
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    """Render the sidebar with configuration and status."""

    with st.sidebar:
        st.markdown("## ⚙️ Configuration")

        # -----------------------------------------------------------
        # Authentication Status
        # -----------------------------------------------------------
        st.markdown("### Authentication")

        if st.button("🔑 Check Auth Status", use_container_width=True):
            with st.spinner("Checking authentication..."):
                auth_status = check_auth_status()
                if auth_status["authenticated"]:
                    st.session_state.authenticated = True
                    if auth_status["project_id"]:
                        st.session_state.project_id = auth_status["project_id"]
                    st.success(f"Authenticated! Project: {auth_status['project_id']}")
                else:
                    st.session_state.authenticated = False
                    st.error(auth_status.get("error", "Not authenticated"))
                    if auth_status.get("instructions"):
                        st.code(auth_status["instructions"], language="bash")

        # Show auth status indicator
        if st.session_state.authenticated:
            st.markdown('<span class="status-badge status-success">Authenticated</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-badge status-warning">Not verified</span>', unsafe_allow_html=True)

        st.divider()

        # -----------------------------------------------------------
        # Project Configuration
        # -----------------------------------------------------------
        st.markdown("### Project Settings")

        project_id = st.text_input(
            "GCP Project ID",
            value=st.session_state.project_id,
            help="Your Google Cloud project where the Conversational Analytics API is enabled",
        )
        if project_id != st.session_state.project_id:
            st.session_state.project_id = project_id
            settings.gcp_project_id = project_id
            # Reset clients when project changes
            st.session_state.agent_manager = None
            st.session_state.chat_handler = None
            st.session_state.setup_complete = False

        agent_id = st.text_input(
            "Agent ID",
            value=st.session_state.agent_id,
            help="Unique identifier for the data agent",
        )
        if agent_id != st.session_state.agent_id:
            st.session_state.agent_id = agent_id

        st.divider()

        # -----------------------------------------------------------
        # Agent Management
        # -----------------------------------------------------------
        st.markdown("### Agent Management")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🚀 Create Agent", use_container_width=True):
                create_agent()

        with col2:
            if st.button("🗑️ Delete Agent", use_container_width=True):
                delete_agent()

        if st.button("📋 List Agents", use_container_width=True):
            list_agents()

        # Agent status
        if st.session_state.agent_created:
            st.markdown('<span class="status-badge status-success">Agent active</span>', unsafe_allow_html=True)

        st.divider()

        # -----------------------------------------------------------
        # Chat Mode & Conversation Management
        # -----------------------------------------------------------
        st.markdown("### Chat Mode")

        mode = st.radio(
            "Conversation Mode",
            options=["stateful", "stateless"],
            index=0 if settings.conversation_mode == "stateful" else 1,
            help="**Stateful** (recommended): API manages conversation history across turns. "
                 "**Stateless**: App sends full history with each request (good for simple use cases).",
            horizontal=True,
        )
        if mode != settings.conversation_mode:
            settings.conversation_mode = mode
            st.session_state.messages = []
            st.rerun()

        if settings.conversation_mode == "stateful":
            if st.button("🔄 New Conversation", use_container_width=True):
                start_new_conversation()

            if st.session_state.conversation_name:
                conv_id = st.session_state.conversation_name.split("/")[-1]
                st.caption(f"Current: `{conv_id}`")
        else:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        st.divider()

        # -----------------------------------------------------------
        # Display Options
        # -----------------------------------------------------------
        st.markdown("### Display Options")

        st.session_state.show_sql = st.toggle(
            "Show Generated SQL",
            value=st.session_state.show_sql,
            help="Display the SQL queries generated by the agent",
        )

        st.session_state.show_reasoning = st.toggle(
            "Show Reasoning Steps",
            value=st.session_state.show_reasoning,
            help="Show the agent's reasoning process",
        )

        st.divider()

        # -----------------------------------------------------------
        # Data Source Info
        # -----------------------------------------------------------
        st.markdown("### Data Source")
        st.caption(f"**Project**: `{settings.bq_project_id}`")
        st.caption(f"**Dataset**: `{settings.bq_dataset_id}`")
        st.caption(f"**Tables**: {', '.join(settings.table_ids_list)}")

        st.divider()

        # -----------------------------------------------------------
        # Quick Info
        # -----------------------------------------------------------
        st.markdown("### About")
        st.caption(
            "Built with [Conversational Analytics API]"
            "(https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/overview) "
            "from Google Cloud Gemini."
        )
        st.caption("Status: **Pre-GA Preview** (Feb 2026)")


# =============================================================================
# AGENT & CONVERSATION OPERATIONS
# =============================================================================

def get_agent_manager() -> AgentManager:
    """Get or create the AgentManager singleton."""
    if st.session_state.agent_manager is None:
        settings.gcp_project_id = st.session_state.project_id
        st.session_state.agent_manager = AgentManager()
    return st.session_state.agent_manager


def get_chat_handler() -> ChatHandler:
    """Get or create the ChatHandler singleton."""
    if st.session_state.chat_handler is None:
        settings.gcp_project_id = st.session_state.project_id
        st.session_state.chat_handler = ChatHandler()
    return st.session_state.chat_handler


def create_agent():
    """Create a new data agent."""
    if not st.session_state.project_id:
        st.sidebar.error("Please set a GCP Project ID first.")
        return

    try:
        with st.spinner("Creating data agent..."):
            mgr = get_agent_manager()
            mgr.create_agent(agent_id=st.session_state.agent_id)
            st.session_state.agent_created = True
            st.sidebar.success(f"Agent `{st.session_state.agent_id}` created!")
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "ALREADY_EXISTS" in error_msg:
            st.session_state.agent_created = True
            st.sidebar.info(f"Agent `{st.session_state.agent_id}` already exists. Using it.")
        else:
            st.sidebar.error(f"Failed to create agent: {error_msg}")


def delete_agent():
    """Delete the current data agent."""
    try:
        mgr = get_agent_manager()
        if mgr.delete_agent(st.session_state.agent_id):
            st.session_state.agent_created = False
            st.session_state.conversation_name = None
            st.session_state.messages = []
            st.sidebar.success(f"Agent `{st.session_state.agent_id}` deleted.")
        else:
            st.sidebar.error("Failed to delete agent.")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")


def list_agents():
    """List all agents and display in sidebar."""
    try:
        mgr = get_agent_manager()
        agents = mgr.list_agents()
        if agents:
            st.sidebar.markdown("**Found agents:**")
            for agent in agents:
                name = agent.name.split("/")[-1]
                desc = agent.description or "No description"
                st.sidebar.caption(f"• `{name}` — {desc}")
        else:
            st.sidebar.info("No agents found in this project.")
    except Exception as e:
        st.sidebar.error(f"Error listing agents: {e}")


def start_new_conversation():
    """Create a new conversation and reset chat."""
    if not st.session_state.agent_created:
        st.sidebar.warning("Please create an agent first.")
        return

    try:
        handler = get_chat_handler()
        conv_name = handler.create_conversation(
            agent_id=st.session_state.agent_id,
        )
        st.session_state.conversation_name = conv_name
        st.session_state.messages = []
        st.sidebar.success("New conversation started!")
    except Exception as e:
        st.sidebar.error(f"Failed to create conversation: {e}")


def ensure_conversation() -> bool:
    """Ensure a conversation exists, creating one if needed."""
    if st.session_state.conversation_name:
        return True

    if not st.session_state.agent_created:
        # Try to create the agent first
        create_agent()
        if not st.session_state.agent_created:
            return False

    try:
        handler = get_chat_handler()
        conv_name = handler.create_conversation(
            agent_id=st.session_state.agent_id,
        )
        st.session_state.conversation_name = conv_name
        return True
    except Exception as e:
        st.error(f"Failed to create conversation: {e}")
        return False


# =============================================================================
# CHAT RENDERING
# =============================================================================

def render_message(msg: ChatMessage, has_api_chart: bool = False):
    """
    Render a single chat message with appropriate formatting.

    LEARNING NOTE:
    Different message types get different renderings:
    - text: Plain text with markdown support
    - data: Interactive table + optional chart
    - chart: Altair chart rendered natively
    - sql: Syntax-highlighted SQL code block
    - reasoning: Collapsible section showing agent's thought process
    - error: Red error banner

    Args:
        msg: The chat message to render
        has_api_chart: If True, skip fallback chart for data messages
            (API already provided a dedicated chart visualization)
    """
    if msg.role == "user":
        with st.chat_message("user"):
            st.markdown(msg.content)
        return

    # Assistant messages
    with st.chat_message("assistant", avatar="🤖"):
        # Render based on message type
        if msg.message_type == "error":
            st.error(msg.content)

        elif msg.message_type == "reasoning" and st.session_state.show_reasoning:
            with st.expander("🧠 Reasoning", expanded=False):
                st.markdown(f'<p class="reasoning-text">{msg.content}</p>', unsafe_allow_html=True)

        elif msg.message_type == "sql" and st.session_state.show_sql:
            with st.expander("📝 Generated SQL", expanded=False):
                sql_text = msg.sql_query or msg.content
                # Clean SQL code block markers
                sql_clean = sql_text.replace("```sql", "").replace("```", "").strip()
                st.code(sql_clean, language="sql")

        elif msg.message_type == "chart":
            # Render chart from Vega-Lite spec or image
            if msg.chart_spec:
                # Use st.vega_lite_chart() for direct Vega-Lite rendering
                # This bypasses Altair serialization which can lose data
                from src.visualization import _clean_vega_spec
                cleaned_spec = _clean_vega_spec(msg.chart_spec)
                data_section = cleaned_spec.get("data", {})
                has_data = (
                    data_section.get("values")       # inline data
                    or data_section.get("name")       # named dataset
                    or data_section.get("url")        # URL data
                    or "datasets" in cleaned_spec     # Altair-style datasets
                )
                if has_data:
                    st.vega_lite_chart(cleaned_spec, width="stretch")
                else:
                    # Fallback to Altair which can handle more formats
                    chart = render_chart_from_spec(msg.chart_spec)
                    if chart:
                        st.altair_chart(chart, width="stretch")
            elif msg.chart_image:
                st.image(msg.chart_image, width="stretch")
            if msg.content:
                st.markdown(msg.content)

        elif msg.message_type == "data" and msg.data:
            # Render data table
            df = data_to_dataframe(msg.data)
            if df is not None and not df.empty:
                st.dataframe(df, width="stretch", hide_index=True)

                # Only create fallback chart if API didn't provide a dedicated chart
                if not has_api_chart and settings.enable_chart_rendering and len(df) > 1:
                    chart = create_chart_from_data(msg.data)
                    if chart:
                        st.altair_chart(chart, width="stretch")

                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name="datachat_results.csv",
                    mime="text/csv",
                    key=f"download_{id(msg)}",
                )

            if msg.content:
                st.markdown(msg.content)

        elif msg.message_type == "text" and msg.content:
            st.markdown(msg.content)

        # Show SQL if available on any message type
        if msg.sql_query and msg.message_type != "sql" and st.session_state.show_sql:
            with st.expander("📝 SQL Query", expanded=False):
                st.code(msg.sql_query, language="sql")


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def render_welcome():
    """Render the welcome screen with setup instructions and example questions."""

    st.markdown('<p class="main-header">💬 DataChat</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Chat with your data using Google Cloud Conversational Analytics API</p>',
        unsafe_allow_html=True,
    )

    # Setup checklist
    if not st.session_state.setup_complete:
        st.markdown("### Quick Setup")
        st.markdown(
            """
            Complete these steps to get started:

            1. **Set your GCP Project ID** in the sidebar
            2. **Check Authentication** — click the button in sidebar
            3. **Create Agent** — click to create your data agent
            4. **Start chatting!** — ask questions about your data
            """
        )

        st.info(
            "**First time?** Make sure you've run:\n"
            "```bash\n"
            "gcloud auth application-default login\n"
            "gcloud services enable geminidataanalytics.googleapis.com\n"
            "gcloud services enable cloudaicompanion.googleapis.com\n"
            "gcloud services enable bigquery.googleapis.com\n"
            "```"
        )

    # Example questions
    st.markdown("### 💡 Example Questions")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            **Sales & Revenue:**
            - What are the top 10 product categories by revenue?
            - Show me the monthly revenue trend for 2024
            - Which brand has the highest average order value?

            **Customer Analysis:**
            - How many customers signed up each month in 2024?
            - What is the customer distribution by country?
            - What traffic source brings the most valuable customers?
            """
        )

    with col2:
        st.markdown(
            """
            **Product Analysis:**
            - What products have the highest profit margin?
            - Compare Men's vs Women's department sales
            - Which category has the most returns?

            **Advanced:**
            - What is the average order value by traffic source?
            - Show me the order status distribution
            - What is the month-over-month growth rate?
            """
        )


def main():
    """Main application entry point."""

    # Render sidebar
    render_sidebar()

    # Main content area
    if not st.session_state.messages:
        render_welcome()

    # Display chat history
    # Check if any stored messages have API chart specs (to avoid duplicate charts)
    stored_has_api_chart = any(
        m.message_type == "chart" and m.chart_spec
        for m in st.session_state.messages
    )
    for msg in st.session_state.messages:
        render_message(msg, has_api_chart=stored_has_api_chart)

    # Chat input
    if prompt := st.chat_input("Ask a question about your data..."):
        handle_user_input(prompt)


def handle_user_input(prompt: str):
    """
    Handle user chat input.

    LEARNING NOTE:
    The flow is:
    1. User types a question
    2. We ensure agent + conversation exist
    3. We send the message to the Conversational Analytics API
    4. We stream and display the response
    5. All messages are stored in session state for persistence
    """
    # Validate project ID
    if not st.session_state.project_id:
        st.error("Please set your GCP Project ID in the sidebar first.")
        return

    # Add user message to history and display it
    user_msg = ChatMessage(role="user", content=prompt)
    st.session_state.messages.append(user_msg)

    with st.chat_message("user"):
        st.markdown(prompt)

    # Ensure we have an agent (and conversation if stateful mode)
    if settings.conversation_mode == "stateful":
        if not ensure_conversation():
            error_msg = ChatMessage(
                role="assistant",
                content="Could not create an agent or conversation. Please check your configuration in the sidebar.",
                message_type="error",
            )
            st.session_state.messages.append(error_msg)
            render_message(error_msg)
            return
    else:
        # Stateless mode — just need the agent
        if not st.session_state.agent_created:
            create_agent()
            if not st.session_state.agent_created:
                error_msg = ChatMessage(
                    role="assistant",
                    content="Could not create or find the data agent. Please check your configuration in the sidebar.",
                    message_type="error",
                )
                st.session_state.messages.append(error_msg)
                render_message(error_msg)
                return

    # Send message to API
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Analyzing your data..."):
            try:
                handler = get_chat_handler()

                if settings.conversation_mode == "stateful":
                    response_messages = handler.chat_stateful(
                        conversation_name=st.session_state.conversation_name,
                        user_message=prompt,
                    )
                else:
                    # Stateless mode — pass history for multi-turn context
                    history = [m for m in st.session_state.messages if m.role in ("user", "assistant")]
                    response_messages = handler.chat_stateless(
                        agent_id=st.session_state.agent_id,
                        user_message=prompt,
                        history=history[:-1],  # Exclude the current user message
                    )

                # Process and display response messages
                # Check if API provided a chart spec (skip fallback chart if so)
                has_api_chart = any(
                    m.message_type == "chart" and m.chart_spec
                    for m in response_messages
                )

                for msg in response_messages:
                    st.session_state.messages.append(msg)

                    # Render each message part
                    if msg.message_type == "error":
                        st.error(msg.content)
                    elif msg.message_type == "reasoning" and st.session_state.show_reasoning:
                        with st.expander("🧠 Reasoning", expanded=False):
                            st.markdown(msg.content)
                    elif msg.message_type == "sql" and st.session_state.show_sql:
                        with st.expander("📝 Generated SQL", expanded=False):
                            sql_clean = (msg.sql_query or msg.content).replace("```sql", "").replace("```", "").strip()
                            st.code(sql_clean, language="sql")
                    elif msg.message_type == "chart":
                        if msg.chart_spec:
                            # Use st.vega_lite_chart() for direct Vega-Lite rendering
                            from src.visualization import _clean_vega_spec
                            cleaned_spec = _clean_vega_spec(msg.chart_spec)
                            data_section = cleaned_spec.get("data", {})
                            has_data = (
                                data_section.get("values")       # inline data
                                or data_section.get("name")       # named dataset
                                or data_section.get("url")        # URL data
                                or "datasets" in cleaned_spec     # Altair-style datasets
                            )
                            if has_data:
                                st.vega_lite_chart(cleaned_spec, width="stretch")
                            else:
                                # Fallback to Altair which can handle more formats
                                chart = render_chart_from_spec(msg.chart_spec)
                                if chart:
                                    st.altair_chart(chart, width="stretch")
                        elif msg.chart_image:
                            st.image(msg.chart_image, width="stretch")
                        if msg.content:
                            st.markdown(msg.content)
                    elif msg.message_type == "data" and msg.data:
                        df = data_to_dataframe(msg.data)
                        if df is not None and not df.empty:
                            st.dataframe(df, width="stretch", hide_index=True)
                            # Only create fallback chart if API didn't provide one
                            if not has_api_chart and settings.enable_chart_rendering and len(df) > 1:
                                chart = create_chart_from_data(msg.data)
                                if chart:
                                    st.altair_chart(chart, width="stretch")
                        if msg.content:
                            st.markdown(msg.content)
                    elif msg.message_type == "text" and msg.content:
                        st.markdown(msg.content)

                # Mark setup as complete after first successful chat
                st.session_state.setup_complete = True

            except Exception as e:
                error_msg = ChatMessage(
                    role="assistant",
                    content=f"Error communicating with the API: {str(e)}",
                    message_type="error",
                )
                st.session_state.messages.append(error_msg)
                st.error(error_msg.content)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()
