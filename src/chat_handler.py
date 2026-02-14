"""
Chat Handler Module for DataChat
===================================

LEARNING NOTES (Updated for SDK v0.10.0):
-----------------------------------------
The SDK v0.10.0 uses a different message structure than the docs (v1beta).

KEY DIFFERENCES:
  - Message has: user_message (UserMessage) or system_message (SystemMessage)
  - UserMessage has: text (string)
  - SystemMessage has: text, data, chart, analysis, error, schema, etc.
  - ChatRequest uses: conversation_reference / data_agent_context (not names)
  - ConversationReference has: conversation (name), data_agent_context
  - DataAgentContext has: data_agent (name), credentials, context_version

RESPONSE STRUCTURE:
  Each streamed Message contains a SystemMessage with fields:
  - text: TextMessage (human-readable text with parts)
  - data: DataMessage (SQL query + result with columns/rows)
  - chart: ChartMessage (Vega chart config or image)
  - analysis: AnalysisMessage (Python analysis events)
  - error: ErrorMessage (error details)
  - schema: SchemaMessage (schema info)
"""

import logging
import uuid
from typing import Optional
from dataclasses import dataclass, field

from google.cloud import geminidataanalytics

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Represents a single message in the chat for display."""

    role: str  # "user" or "assistant"
    content: str  # Text content
    message_type: str = "text"  # "text", "data", "chart", "reasoning", "sql", "error"
    data: Optional[dict] = None  # Tabular data result
    chart_spec: Optional[dict] = None  # Vega chart spec
    chart_image: Optional[bytes] = None  # Chart as image bytes
    sql_query: Optional[str] = None  # Generated SQL
    metadata: dict = field(default_factory=dict)


class ChatHandler:
    """Handles conversations and chat with the Conversational Analytics API."""

    def __init__(self):
        self.client = geminidataanalytics.DataChatServiceClient()
        self.project_id = settings.gcp_project_id
        self.location = settings.gcp_location
        self.parent = settings.parent_resource

    # -----------------------------------------------------------------
    # CONVERSATION MANAGEMENT
    # -----------------------------------------------------------------

    def create_conversation(
        self,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a new stateful conversation linked to a data agent.
        Returns the conversation resource name.
        """
        agent_id = agent_id or settings.default_agent_id
        conversation_id = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"

        conversation = geminidataanalytics.Conversation()
        conversation.agents = [f"{self.parent}/dataAgents/{agent_id}"]
        conversation.name = f"{self.parent}/conversations/{conversation_id}"

        request = geminidataanalytics.CreateConversationRequest(
            parent=self.parent,
            conversation_id=conversation_id,
            conversation=conversation,
        )

        try:
            response = self.client.create_conversation(request=request)
            logger.info(f"Conversation created: {response.name}")
            return response.name
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise

    def get_conversation(self, conversation_name: str):
        """Retrieve conversation details."""
        request = geminidataanalytics.GetConversationRequest(name=conversation_name)
        try:
            return self.client.get_conversation(request=request)
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            return None

    def list_conversations(self) -> list:
        """List all conversations in the project."""
        request = geminidataanalytics.ListConversationsRequest(parent=self.parent)
        try:
            return list(self.client.list_conversations(request=request))
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []

    def delete_conversation(self, conversation_name: str) -> bool:
        """Delete a conversation."""
        request = geminidataanalytics.DeleteConversationRequest(name=conversation_name)
        try:
            self.client.delete_conversation(request=request)
            logger.info(f"Deleted conversation: {conversation_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False

    # -----------------------------------------------------------------
    # STATEFUL CHAT (v0.10.0 SDK structure)
    # -----------------------------------------------------------------

    def chat_stateful(
        self,
        conversation_name: str,
        user_message: str,
        agent_id: Optional[str] = None,
    ) -> list[ChatMessage]:
        """
        Send a message in a stateful conversation.

        CRITICAL FIX (discovered during debugging):
          The ConversationReference MUST include data_agent_context
          alongside the conversation name. Without it, the API returns
          a misleading "403 User does not have permission to chat" error
          because it cannot resolve the data source references.

        SDK v0.10.0 structure:
          ChatRequest(
              parent=...,
              conversation_reference=ConversationReference(
                  conversation=conv_name,
                  data_agent_context=DataAgentContext(data_agent=agent_name),
              ),
              messages=[Message(user_message=UserMessage(text=...))]
          )
        """
        agent_id = agent_id or settings.default_agent_id
        agent_name = f"{self.parent}/dataAgents/{agent_id}"

        # Build the user message
        msg = geminidataanalytics.Message(
            user_message=geminidataanalytics.UserMessage(text=user_message)
        )

        # Build the request with conversation reference + agent context
        # Both are required — conversation for state, agent for data source config
        request = geminidataanalytics.ChatRequest(
            parent=self.parent,
            conversation_reference=geminidataanalytics.ConversationReference(
                conversation=conversation_name,
                data_agent_context=geminidataanalytics.DataAgentContext(
                    data_agent=agent_name,
                ),
            ),
            messages=[msg],
        )

        return self._process_chat_response(request)

    # -----------------------------------------------------------------
    # STATELESS CHAT (v0.10.0 SDK structure)
    # -----------------------------------------------------------------

    def chat_stateless(
        self,
        agent_id: str,
        user_message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> list[ChatMessage]:
        """
        Send a stateless chat message referencing a saved agent.

        SDK v0.10.0 structure:
          ChatRequest(
              parent=...,
              data_agent_context=DataAgentContext(data_agent=agent_name),
              messages=[...]  # Full history + new message
          )
        """
        messages = []

        # Include conversation history for multi-turn
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(
                        geminidataanalytics.Message(
                            user_message=geminidataanalytics.UserMessage(text=msg.content)
                        )
                    )
                # Note: We only include user messages in stateless history
                # System messages are auto-generated by the API

        # Add the current message
        messages.append(
            geminidataanalytics.Message(
                user_message=geminidataanalytics.UserMessage(text=user_message)
            )
        )

        request = geminidataanalytics.ChatRequest(
            parent=self.parent,
            data_agent_context=geminidataanalytics.DataAgentContext(
                data_agent=f"{self.parent}/dataAgents/{agent_id}",
            ),
            messages=messages,
        )

        return self._process_chat_response(request)

    # -----------------------------------------------------------------
    # RESPONSE PROCESSING (v0.10.0 structure)
    # -----------------------------------------------------------------

    def _process_chat_response(
        self, request: geminidataanalytics.ChatRequest
    ) -> list[ChatMessage]:
        """
        Send a chat request and process the streaming response.

        In v0.10.0, each streamed Message contains:
          - system_message.text: TextMessage (parts, text_type)
          - system_message.data: DataMessage (query, generated_sql, result)
          - system_message.chart: ChartMessage (query, result with vega_config)
          - system_message.analysis: AnalysisMessage (query, progress_event)
          - system_message.error: ErrorMessage (text)
        """
        messages = []

        try:
            response_stream = self.client.chat(request=request)

            for response_msg in response_stream:
                parsed_msgs = self._parse_message(response_msg)
                messages.extend(parsed_msgs)

            logger.info(f"Received {len(messages)} messages in response")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Chat error: {error_msg}")
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=f"Error: {error_msg}",
                    message_type="error",
                )
            )

        return messages

    def _parse_message(self, msg: geminidataanalytics.Message) -> list[ChatMessage]:
        """
        Parse a single API Message into ChatMessage objects.

        A single Message can be either user_message or system_message.
        System messages can contain multiple types of content
        (text, data, chart, error, etc.) — we create a ChatMessage for each.
        """
        results = []

        # Skip user message echoes
        if msg.user_message and msg.user_message.text:
            return results

        # Process system messages
        sys_msg = msg.system_message
        if not sys_msg:
            return results

        # --- TEXT ---
        if sys_msg.text and sys_msg.text.parts:
            text = " ".join(sys_msg.text.parts)
            if text.strip():
                # Extract embedded Vega-Lite JSON from text (API sometimes
                # includes the chart spec as a JSON code block in text)
                # This also returns the chart spec so we can render it
                clean_text, text_chart_spec = self._extract_chart_from_text(text)

                # If we found a chart spec in the text, add it as a chart message
                if text_chart_spec:
                    # Ensure schema is present
                    if '$schema' not in text_chart_spec:
                        text_chart_spec['$schema'] = 'https://vega.github.io/schema/vega-lite/v5.json'
                    results.append(ChatMessage(
                        role="assistant",
                        content="",
                        message_type="chart",
                        chart_spec=text_chart_spec,
                    ))
                    logger.info(f"Extracted chart spec from text: {list(text_chart_spec.keys())}")

                if clean_text.strip():
                    results.append(ChatMessage(
                        role="assistant",
                        content=clean_text,
                        message_type="text",
                    ))

        # --- DATA (SQL + results) ---
        if sys_msg.data:
            data_msg = sys_msg.data

            # Extract generated SQL
            sql_query = None
            if data_msg.generated_sql:
                sql_query = data_msg.generated_sql
                results.append(ChatMessage(
                    role="assistant",
                    content=sql_query,
                    message_type="sql",
                    sql_query=sql_query,
                ))

            # Extract data result
            if data_msg.result:
                data_dict = self._parse_data_result(data_msg.result)
                if data_dict:
                    results.append(ChatMessage(
                        role="assistant",
                        content="",
                        message_type="data",
                        data=data_dict,
                        sql_query=sql_query,
                    ))

        # --- CHART ---
        if sys_msg.chart and sys_msg.chart.result:
            chart_result = sys_msg.chart.result

            # Extract Vega-Lite config using deep protobuf conversion
            # CRITICAL FIX: vega_config is a MapComposite (proto object).
            # dict() only does shallow conversion, leaving nested proto objects
            # that Altair cannot parse. We use MessageToDict for deep conversion.
            if chart_result.vega_config:
                try:
                    from google.protobuf.json_format import MessageToDict
                    # Convert the entire ChartResult protobuf to a clean dict
                    cr_dict = MessageToDict(chart_result._pb)
                    chart_spec = cr_dict.get('vegaConfig', {})

                    # Ensure Vega-Lite schema is present for Altair
                    if chart_spec and '$schema' not in chart_spec:
                        chart_spec['$schema'] = 'https://vega.github.io/schema/vega-lite/v5.json'

                    if chart_spec:
                        results.append(ChatMessage(
                            role="assistant",
                            content="",
                            message_type="chart",
                            chart_spec=chart_spec,
                        ))
                        logger.info(f"Chart spec parsed: {list(chart_spec.keys())}")
                except Exception as e:
                    logger.warning(f"Failed to parse chart vega config: {e}")

            # Try chart image as fallback
            if chart_result.image and chart_result.image.data:
                results.append(ChatMessage(
                    role="assistant",
                    content="",
                    message_type="chart",
                    chart_image=chart_result.image.data,
                ))

        # --- ANALYSIS ---
        if sys_msg.analysis:
            analysis_msg = sys_msg.analysis
            if analysis_msg.progress_event:
                text = str(analysis_msg.progress_event)
                results.append(ChatMessage(
                    role="assistant",
                    content=text,
                    message_type="reasoning",
                ))

        # --- ERROR ---
        if sys_msg.error and sys_msg.error.text:
            results.append(ChatMessage(
                role="assistant",
                content=sys_msg.error.text,
                message_type="error",
            ))

        return results

    def _parse_data_result(self, data_result: geminidataanalytics.DataResult) -> Optional[dict]:
        """
        Parse a DataResult proto into a dict for display.

        CRITICAL: DataResult fields are protobuf types (RepeatedComposite,
        MapComposite), NOT plain Python types. We use MessageToDict for
        proper deep conversion.

        DataResult fields:
          - name: result name
          - schema: Schema (description, fields with name/type)
          - data: RepeatedComposite of Struct rows
          - formatted_data: RepeatedComposite of formatted rows
        """
        try:
            from google.protobuf.json_format import MessageToDict

            result = {"columns": [], "rows": []}

            # Convert the entire DataResult to a clean Python dict
            dr_dict = MessageToDict(data_result._pb)

            # Extract columns from schema
            schema = dr_dict.get("schema", {})
            fields = schema.get("fields", [])
            if fields:
                result["columns"] = [f.get("name", f"col_{i}") for i, f in enumerate(fields)]

            # Extract rows from data (list of Struct -> list of dicts)
            data_rows = dr_dict.get("data", [])
            if data_rows and isinstance(data_rows, list):
                for row in data_rows:
                    if isinstance(row, dict):
                        # Row is a Struct-like dict with "fields" or direct values
                        if "fields" in row:
                            # Protobuf Struct format: {"fields": {"col": {"stringValue": "x"}}}
                            row_values = []
                            for col_name in result["columns"]:
                                val_wrapper = row["fields"].get(col_name, {})
                                # Extract the actual value from the Value proto
                                val = self._extract_proto_value(val_wrapper)
                                row_values.append(val)
                            result["rows"].append(row_values)
                        else:
                            # Direct dict format
                            if not result["columns"]:
                                result["columns"] = list(row.keys())
                            result["rows"].append([row.get(c) for c in result["columns"]])
                    elif isinstance(row, list):
                        result["rows"].append(row)

            # Fallback: try formatted_data
            if not result["rows"]:
                formatted_rows = dr_dict.get("formattedData", [])
                if formatted_rows and isinstance(formatted_rows, list):
                    for row in formatted_rows:
                        if isinstance(row, dict):
                            if "fields" in row:
                                row_values = []
                                for col_name in result["columns"]:
                                    val_wrapper = row["fields"].get(col_name, {})
                                    val = self._extract_proto_value(val_wrapper)
                                    row_values.append(val)
                                result["rows"].append(row_values)
                            else:
                                if not result["columns"]:
                                    result["columns"] = list(row.keys())
                                result["rows"].append([row.get(c) for c in result["columns"]])

            if result["columns"] or result["rows"]:
                logger.info(f"Parsed data: {len(result['columns'])} cols, {len(result['rows'])} rows")
                return result
            return None

        except Exception as e:
            logger.warning(f"Data result parsing error: {e}")
            return None

    @staticmethod
    def _extract_proto_value(val_wrapper: dict):
        """Extract actual value from a protobuf Value message dict."""
        if not val_wrapper:
            return None
        # Protobuf Value has one of: stringValue, numberValue, boolValue, nullValue, etc.
        for key in ("stringValue", "numberValue", "boolValue", "integerValue"):
            if key in val_wrapper:
                return val_wrapper[key]
        if "nullValue" in val_wrapper:
            return None
        # If it's just a plain value (from proto-plus conversion)
        if len(val_wrapper) == 0:
            return None
        # Return the first value found
        return next(iter(val_wrapper.values()), None)

    @staticmethod
    def _extract_chart_from_text(text: str) -> tuple[str, Optional[dict]]:
        """
        Extract embedded Vega-Lite/Altair chart specs from text responses.

        The API sometimes includes the chart spec as raw JSON in the text
        response instead of (or in addition to) the chart field.

        Returns:
            Tuple of (cleaned_text, chart_spec_or_None)

        CRITICAL FIX:
        The JSON can start with various keys:
          - {"config": ...}  (Altair-generated format)
          - {"$schema": ...} (standard Vega-Lite)
          - {"data": ...}    (data-first format)
        We detect ANY JSON containing chart markers ("mark", "encoding").
        """
        import re
        import json

        chart_spec = None

        # Strategy 1: Find JSON in fenced code blocks
        fenced_pattern = r'```(?:json|vega-lite)?\s*(\{.+?\})\s*```'
        fenced_matches = re.findall(fenced_pattern, text, flags=re.DOTALL)
        for match in fenced_matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and ("encoding" in parsed or "mark" in parsed):
                    chart_spec = parsed
                    # Remove the fenced block from text
                    text = text.replace(f"```json\n{match}\n```", "")
                    text = text.replace(f"```{match}```", "")
                    text = re.sub(
                        r'```(?:json|vega-lite)?\s*' + re.escape(match) + r'\s*```',
                        '', text, flags=re.DOTALL
                    )
                    break
            except (json.JSONDecodeError, ValueError):
                continue

        # Strategy 2: Find inline JSON objects containing chart markers
        # This catches JSON that starts with { and contains "mark" and "encoding"
        if chart_spec is None:
            # Find the FIRST '{' that could be a chart spec
            # Look for JSON objects that contain chart-like keys
            brace_positions = [m.start() for m in re.finditer(r'\{', text)]
            for start_pos in brace_positions:
                # Try to find matching closing brace by parsing
                remaining = text[start_pos:]
                # Quick check: does it contain chart markers?
                if '"mark"' not in remaining and '"encoding"' not in remaining:
                    continue

                # Try to parse JSON starting from this position
                try:
                    parsed = json.loads(remaining)
                    if isinstance(parsed, dict) and ("encoding" in parsed or "mark" in parsed):
                        chart_spec = parsed
                        text = text[:start_pos].rstrip()
                        break
                except (json.JSONDecodeError, ValueError):
                    # Try to find the matching closing brace manually
                    depth = 0
                    end_pos = start_pos
                    for i, ch in enumerate(remaining):
                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                end_pos = start_pos + i + 1
                                break
                    if end_pos > start_pos:
                        json_candidate = text[start_pos:end_pos]
                        try:
                            parsed = json.loads(json_candidate)
                            if isinstance(parsed, dict) and ("encoding" in parsed or "mark" in parsed):
                                chart_spec = parsed
                                text = (text[:start_pos] + text[end_pos:]).strip()
                                break
                        except (json.JSONDecodeError, ValueError):
                            continue

        # Final cleanup: remove any trailing "Here's the chart:" type prefixes
        # that are now orphaned
        text = re.sub(r'(?:Here(?:\'s| is) (?:a |the )?(?:bar |line |pie )?chart[^.]*?:\s*$)', '', text, flags=re.IGNORECASE).strip()

        return text, chart_spec

    @staticmethod
    def _strip_vega_json(text: str) -> str:
        """
        Strip embedded Vega-Lite JSON specs from text responses.
        Wrapper around _extract_chart_from_text that only returns the cleaned text.
        """
        clean_text, _ = ChatHandler._extract_chart_from_text(text)
        return clean_text
