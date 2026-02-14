"""
Agent Manager Module for DataChat
====================================

LEARNING NOTES:
--------------
This module handles the full lifecycle of Conversational Analytics API data agents:

  CREATE → GET → UPDATE → LIST → DELETE

KEY CONCEPTS:
1. A "Data Agent" is a configured AI assistant connected to your data sources.
   - It has system instructions (authored context) that shape behavior
   - It has data source references (BigQuery tables, Looker Explores)
   - It has an options block (e.g., enable Python analysis)

2. Agent creation can be SYNCHRONOUS or ASYNCHRONOUS:
   - Sync (createSync): Blocks until agent is ready — simpler, good for scripts
   - Async (create): Returns immediately with an operation — good for production

3. Agents have a VERSION CONTROL system for context:
   - stagingContext: Test your changes here
   - publishedContext: What consumers actually use
   - lastPublishedContext: Automatic backup for rollback

4. Agents are SOFT-DELETED: Deleted agents can be recovered within 30 days.

5. The Python SDK uses Protobuf message objects, not dictionaries.
   - geminidataanalytics.DataAgent (not {"name": "..."})
   - This gives you type safety and IDE autocomplete

API ENDPOINT: geminidataanalytics.googleapis.com
"""

import logging
import yaml
from pathlib import Path
from typing import Optional

from google.cloud import geminidataanalytics

from config.settings import settings

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages the lifecycle of Conversational Analytics API data agents.

    ARCHITECTURE NOTE:
    This class wraps the DataAgentServiceClient from the Python SDK.
    The client handles:
    - Authentication (via ADC)
    - Request serialization (Python objects → Protobuf → HTTP)
    - Response deserialization (HTTP → Protobuf → Python objects)
    - Retry logic for transient errors
    """

    def __init__(self):
        """
        Initialize the agent manager with a DataAgentServiceClient.

        LEARNING NOTE:
        The client is initialized once and reused. It maintains a gRPC
        channel to the API. Creating multiple clients wastes resources.
        """
        self.client = geminidataanalytics.DataAgentServiceClient()
        self.project_id = settings.gcp_project_id
        self.location = settings.gcp_location
        self.parent = settings.parent_resource

    # -----------------------------------------------------------------
    # DATA SOURCE CONFIGURATION
    # -----------------------------------------------------------------

    def build_bigquery_datasource(
        self,
        project_id: str,
        dataset_id: str,
        table_ids: list[str],
        table_descriptions: Optional[dict[str, str]] = None,
        column_descriptions: Optional[dict[str, dict[str, str]]] = None,
    ) -> geminidataanalytics.DatasourceReferences:
        """
        Build BigQuery data source references for agent creation.

        LEARNING NOTE:
        Structured context (table/column descriptions) goes HERE,
        not in system instructions. The API automatically incorporates
        structured context — no need to repeat it in system_instruction.

        Args:
            project_id: BigQuery project (e.g., "bigquery-public-data")
            dataset_id: BigQuery dataset (e.g., "thelook_ecommerce")
            table_ids: List of table names (e.g., ["orders", "products"])
            table_descriptions: Optional {table_id: description} mapping
            column_descriptions: Optional {table_id: {column: description}} mapping
        """
        table_references = []

        for table_id in table_ids:
            table_ref = geminidataanalytics.BigQueryTableReference()
            table_ref.project_id = project_id
            table_ref.dataset_id = dataset_id
            table_ref.table_id = table_id

            # Add table description if provided
            if table_descriptions and table_id in table_descriptions:
                table_ref.schema = geminidataanalytics.Schema()
                table_ref.schema.description = table_descriptions[table_id]

                # Add column descriptions if provided
                if column_descriptions and table_id in column_descriptions:
                    fields = []
                    for col_name, col_desc in column_descriptions[table_id].items():
                        fields.append(
                            geminidataanalytics.Field(
                                name=col_name, description=col_desc
                            )
                        )
                    table_ref.schema.fields = fields

            table_references.append(table_ref)
            logger.info(f"Added table reference: {project_id}.{dataset_id}.{table_id}")

        datasource = geminidataanalytics.DatasourceReferences()
        datasource.bq.table_references = table_references
        return datasource

    def get_default_datasource(self) -> geminidataanalytics.DatasourceReferences:
        """
        Build data source from default settings (env configuration).
        Uses the TheLook E-Commerce public dataset by default.
        """
        # Define descriptive context for our e-commerce tables
        table_descriptions = {
            "orders": "E-commerce order transactions with status, timestamps, and customer references",
            "order_items": "Individual items within orders, with product references and sale prices",
            "products": "Product catalog with name, category, brand, department, cost, and retail price",
            "users": "Customer profiles with demographics: age, gender, email, city, state, country, traffic source",
        }

        column_descriptions = {
            "orders": {
                "order_id": "Unique order identifier",
                "user_id": "Reference to the customer who placed the order",
                "status": "Order status: Complete, Cancelled, Returned, Processing, or Shipped",
                "created_at": "Timestamp when the order was placed (UTC)",
                "num_of_item": "Number of items in the order",
            },
            "order_items": {
                "id": "Unique line item identifier",
                "order_id": "Reference to the parent order",
                "product_id": "Reference to the product",
                "sale_price": "Actual sale price in USD",
                "status": "Item status: Complete, Cancelled, Returned, Processing, or Shipped",
            },
            "products": {
                "id": "Unique product identifier",
                "name": "Product display name",
                "category": "Product category (e.g., Jeans, Sweaters, Outerwear)",
                "brand": "Product brand name",
                "department": "Department: Men or Women",
                "retail_price": "Listed retail price in USD",
                "cost": "Cost of goods in USD",
            },
            "users": {
                "id": "Unique customer identifier",
                "age": "Customer age in years",
                "gender": "Customer gender: M or F",
                "city": "Customer city",
                "state": "Customer state/province",
                "country": "Customer country",
                "traffic_source": "How the customer found the site: Search, Organic, Facebook, Email, Display",
                "created_at": "Account creation timestamp",
            },
        }

        return self.build_bigquery_datasource(
            project_id=settings.bq_project_id,
            dataset_id=settings.bq_dataset_id,
            table_ids=settings.table_ids_list,
            table_descriptions=table_descriptions,
            column_descriptions=column_descriptions,
        )

    # -----------------------------------------------------------------
    # SYSTEM INSTRUCTIONS
    # -----------------------------------------------------------------

    def load_system_instructions(
        self, yaml_path: Optional[str] = None
    ) -> str:
        """
        Load system instructions from YAML file.

        LEARNING NOTE:
        Google recommends YAML format for system instructions because:
        1. It's structured and readable
        2. Easy to version control
        3. Clear hierarchy (role, guidelines, definitions)
        4. The API accepts it as a plain string — YAML is just for your organization

        The content is sent as a string to the API's system_instruction field.
        The agent interprets the YAML structure to understand your guidance.
        """
        if yaml_path is None:
            # Default path relative to project root
            yaml_path = Path(__file__).parent.parent / "config" / "system_instructions.yaml"
        else:
            yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            logger.warning(f"System instructions file not found: {yaml_path}")
            return "Help the user analyze their data. Provide clear, concise answers."

        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.info(f"Loaded system instructions from {yaml_path}")
        return content

    # -----------------------------------------------------------------
    # AGENT CRUD OPERATIONS
    # -----------------------------------------------------------------

    def create_agent(
        self,
        agent_id: Optional[str] = None,
        description: str = "DataChat agent for e-commerce data analysis",
        system_instructions: Optional[str] = None,
        datasource: Optional[geminidataanalytics.DatasourceReferences] = None,
    ) -> Optional[geminidataanalytics.DataAgent]:
        """
        Create a new data agent.

        LEARNING NOTE:
        The CreateDataAgentRequest uses these key fields:
        - parent: "projects/{project}/locations/{location}"
        - data_agent_id: Unique ID for the agent (becomes part of resource name)
        - data_agent: The DataAgent proto with:
            - data_analytics_agent.published_context.system_instruction
            - data_analytics_agent.published_context.datasource_references
            - data_analytics_agent.published_context.options (Python analysis, etc.)

        The agent is created ASYNCHRONOUSLY by default.
        For sync creation, the SDK uses CreateDataAgentSync.
        """
        agent_id = agent_id or settings.default_agent_id
        system_instructions = system_instructions or self.load_system_instructions()
        datasource = datasource or self.get_default_datasource()

        # Build the published context
        published_context = geminidataanalytics.Context()
        published_context.system_instruction = system_instructions
        published_context.datasource_references = datasource

        # Enable Python analysis if configured
        if settings.enable_python_analysis:
            published_context.options.analysis.python.enabled = True

        # Build the data agent
        data_agent = geminidataanalytics.DataAgent()
        data_agent.data_analytics_agent.published_context = published_context
        data_agent.name = f"{self.parent}/dataAgents/{agent_id}"
        data_agent.description = description

        # Build the request
        request = geminidataanalytics.CreateDataAgentRequest(
            parent=self.parent,
            data_agent_id=agent_id,
            data_agent=data_agent,
        )

        try:
            response = self.client.create_data_agent(request=request)
            logger.info(f"Data Agent created: {agent_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to create agent '{agent_id}': {e}")
            raise

    def get_agent(self, agent_id: Optional[str] = None) -> Optional[geminidataanalytics.DataAgent]:
        """
        Retrieve an existing data agent.

        LEARNING NOTE:
        Use this to verify agent configuration, check published context,
        or confirm that an agent exists before creating a conversation.
        """
        agent_id = agent_id or settings.default_agent_id

        request = geminidataanalytics.GetDataAgentRequest(
            name=f"{self.parent}/dataAgents/{agent_id}"
        )

        try:
            response = self.client.get_data_agent(request=request)
            logger.info(f"Retrieved agent: {agent_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to get agent '{agent_id}': {e}")
            return None

    def list_agents(self) -> list:
        """
        List all data agents in the project.

        LEARNING NOTE:
        Requires the geminidataanalytics.dataAgents.list IAM permission.
        Returns a paginated result — the SDK handles pagination automatically
        when you iterate over the response.
        """
        request = geminidataanalytics.ListDataAgentsRequest(
            parent=self.parent,
        )

        try:
            agents = []
            for agent in self.client.list_data_agents(request=request):
                agents.append(agent)
            logger.info(f"Listed {len(agents)} agents")
            return agents
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []

    def delete_agent(self, agent_id: Optional[str] = None) -> bool:
        """
        Soft-delete a data agent.

        LEARNING NOTE:
        "Soft delete" means the agent is marked as deleted but can be
        recovered within 30 days. This is a safety feature — accidental
        deletions can be reversed.
        """
        agent_id = agent_id or settings.default_agent_id

        request = geminidataanalytics.DeleteDataAgentRequest(
            name=f"{self.parent}/dataAgents/{agent_id}"
        )

        try:
            self.client.delete_data_agent(request=request)
            logger.info(f"Deleted agent: {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete agent '{agent_id}': {e}")
            return False

    def agent_exists(self, agent_id: Optional[str] = None) -> bool:
        """Check if an agent exists without raising errors."""
        return self.get_agent(agent_id) is not None
