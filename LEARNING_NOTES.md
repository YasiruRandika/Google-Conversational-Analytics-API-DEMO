# DataChat — Complete Learning Journey & Expert Guide

> **Author**: Yasas Randika
> **Date**: February 9-10, 2026
> **Goal**: Become an expert in Agentic AI by building a real application with Google Cloud's Conversational Analytics API

---

## Part 1: Why This Project Matters for Agentic AI Mastery

### What Is "Agentic AI"?

Agentic AI refers to AI systems that can **autonomously reason, plan, and take actions** to achieve a goal — not just respond to prompts. The key characteristics are:

| Property | Traditional LLM | Agentic AI |
|----------|----------------|------------|
| **Reasoning** | Single prompt → single response | Multi-step reasoning loop |
| **Tool Use** | None | Calls tools (SQL, Python, APIs) |
| **Memory** | Stateless | Retains context across turns |
| **Autonomy** | Passive (answers questions) | Active (decides what to do next) |
| **Error Recovery** | None | Detects failures and retries |

### How DataChat Demonstrates Agentic AI

The Conversational Analytics API is a **managed agentic system**. When a user asks "What are the top 5 products by revenue?", the agent:

```
1. REASON   → "I need to query the products and order_items tables"
2. PLAN     → "I'll write a SQL query with JOIN, SUM, GROUP BY, ORDER BY"
3. EXECUTE  → Runs SQL against BigQuery
4. EVALUATE → "Query succeeded with 5 rows"
5. DECIDE   → "I should also create a bar chart for this data"
6. EXECUTE  → Generates Vega-Lite chart specification
7. RESPOND  → Returns text summary + data table + chart
```

If the SQL fails (syntax error, column mismatch), the agent:
```
RETRY #1  → Reads the error, rewrites the SQL, tries again
RETRY #2  → If still failing, simplifies the query
RETRY #3  → If all fails, returns an error explanation
```

This is the **ReAct pattern** (Reason + Act) — the same paradigm used by Google's ADK, LangChain agents, and OpenAI function calling. The difference is that Google manages the entire loop for you.

### Where DataChat Fits in the Agentic AI Landscape

```
                    AGENTIC AI ECOSYSTEM
┌──────────────────────────────────────────────────┐
│                                                  │
│  FRAMEWORKS (Build Your Own Agent)               │
│  ├── Google ADK (Agent Development Kit)          │
│  ├── LangChain / LangGraph                       │
│  ├── OpenAI Assistants API                       │
│  └── AutoGen / CrewAI                            │
│                                                  │
│  MANAGED SERVICES (Pre-Built Agent Capabilities) │
│  ├── Google Conversational Analytics API  ◄─ THIS│
│  ├── Google Vertex AI Agents                     │
│  └── AWS Bedrock Agents                          │
│                                                  │
│  PROTOCOLS (Agent Communication)                 │
│  ├── A2A (Agent-to-Agent Protocol)               │
│  ├── MCP (Model Context Protocol)                │
│  └── AP2 (Agent Payment Protocol)                │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Part 2: The Complete Build Journey

### Phase 1: Research (Before Writing Code)

**What we did**: Deep-dived into the official documentation, Colab notebooks, and API reference.

**Key research outputs** → See `../RESEARCH_AND_LEARNING.md` (1000+ lines)

**What we learned**:
- The API has two interfaces: **HTTP/REST** and **Python SDK** (we chose SDK)
- Two conversation modes: **Stateful** (API manages history) and **Stateless** (you manage history)
- Data sources: **BigQuery** (full support), **Looker** (good support), **databases** (QueryData only)
- The SDK package is `google-cloud-geminidataanalytics` (v0.10.0 as of Feb 2026)
- Authentication uses **Application Default Credentials** (ADC) — Google's standard pattern

### Phase 2: Architecture & Scaffolding

We designed a modular architecture following separation of concerns:

```
DataChat/
├── app.py                    # Streamlit UI — presentation layer
├── config/
│   ├── settings.py           # Pydantic Settings — typed config from env vars
│   └── system_instructions.yaml  # Agent behavior — business context
├── src/
│   ├── auth.py               # GCP authentication — ADC handling
│   ├── agent_manager.py      # Agent CRUD — create/get/list/delete
│   ├── chat_handler.py       # Chat logic — stateful/stateless conversations
│   └── visualization.py      # Chart rendering — Vega-Lite → visual charts
├── .env                      # Local secrets (not committed)
└── service-account-key.json  # Service account (not committed)
```

**Why this structure matters**: Each module maps to one API concept. When debugging, you know exactly which file to look at.

### Phase 3: Implementation

1. **Authentication** → `auth.py`: Set up ADC with service account support
2. **Configuration** → `settings.py` + YAML: Typed config with env var fallbacks
3. **Agent Management** → `agent_manager.py`: Create agents with BigQuery data source
4. **Chat Logic** → `chat_handler.py`: Implement both stateful and stateless modes
5. **Visualization** → `visualization.py`: Render Vega-Lite chart specs
6. **UI** → `app.py`: Streamlit chat interface with sidebar controls

### Phase 4: Debugging (Where Real Learning Happened)

This is where we discovered things that **no documentation tells you**. See Part 4 for full details.

### Phase 5: Feature Completion

After fixing core issues, we verified all API features work end-to-end:
- Natural language → SQL → Data tables → Charts → Text summaries
- Multi-turn conversations with context retention
- Bar charts, line charts with proper date rendering
- CSV download, SQL display, reasoning steps

---

## Part 3: Module-by-Module Deep Dive

### Module 1: Authentication (`src/auth.py`)

**API Concept**: Application Default Credentials (ADC)

ADC is Google's unified authentication pattern. The SDK checks credentials in this order:
1. `GOOGLE_APPLICATION_CREDENTIALS` env var → service account JSON file
2. `gcloud auth application-default` → your personal Google login
3. GCE/Cloud Run metadata server → when running on Google Cloud

```python
# HTTP approach (manual, error-prone)
access_token = subprocess.check_output(["gcloud", "auth", "print-access-token"])
headers = {"Authorization": f"Bearer {access_token}"}
# Token expires in ~1 hour! Must refresh manually.

# SDK approach (automatic, recommended)
client = geminidataanalytics.DataAgentServiceClient()
# Auth is handled automatically. Token refresh is automatic.
```

**Expert Insight: Service Account vs Personal Credentials**

We discovered that the **same API error can mean different things** depending on your credential type:

| Credential Type | Malformed Request | Error Returned |
|----------------|-------------------|----------------|
| Personal (ADC) | Missing data_agent_context | `400 InvalidArgument: REFERENCES_NOT_SET` |
| Service Account | Missing data_agent_context | `403 PermissionDenied: User does not have permission to chat` |

The `403` from the service account was **misleading** — it wasn't actually a permission problem. See Critical Discovery #1 in Part 4.

**Lesson**: When debugging API errors, **always test with personal credentials too**. Different credential types can produce different error messages for the same underlying problem.

### Module 2: Configuration (`config/settings.py` + `system_instructions.yaml`)

**API Concept**: Authored Context (System Instructions + Structured Context)

The Conversational Analytics API accepts two types of context:

```
STRUCTURED CONTEXT (BigQuery only)          SYSTEM INSTRUCTIONS (all sources)
├── Table descriptions                      ├── Business definitions
├── Column descriptions                     ├── Response formatting rules
├── Synonyms (e.g., "revenue" = sale_price) ├── Data interpretation notes
├── Tags                                    └── Guardrails & restrictions
└── Example queries (golden queries)

→ Goes in: datasource_references              → Goes in: system_instruction
→ Purpose: Help agent understand schema       → Purpose: Shape agent behavior
→ Format: Protobuf fields                     → Format: YAML string
```

**Rule**: Use structured context FIRST, then supplement with system instructions. Don't duplicate.

**Why YAML for system instructions?**
Google recommends YAML because it's structured, human-readable, version-controllable, and the agent parses the hierarchy to understand role/purpose/guidelines.

**Expert Insight**: System instructions are the **single biggest factor** in agent accuracy. Example:
```yaml
role: E-Commerce Data Analyst
purpose: Help business users analyze TheLook e-commerce data
guidelines:
  - Always include dollar signs for revenue values
  - When showing trends, prefer line charts
  - When comparing categories, use bar charts
  - Never show more than 20 rows in a table
data_notes:
  - sale_price is in USD, already net of discounts
  - order status "Complete" means fully shipped
```

### Module 3: Agent Manager (`src/agent_manager.py`)

**API Concept**: Data Agents — persistent AI assistants with data connections

A data agent is NOT ephemeral. It persists across sessions:
```python
# Create once
agent = create_data_agent("ecommerce_agent", bigquery_tables, system_instructions)

# Use forever (different users, different sessions)
response = chat_with_agent("ecommerce_agent", "What's our revenue?")
```

**Key Concept: Protobuf Message Objects**

The SDK uses Protocol Buffer messages, NOT Python dicts:
```python
# WRONG (will not work)
agent = {"name": "projects/my-project/locations/global/dataAgents/my-agent"}

# CORRECT (protobuf style)
agent = geminidataanalytics.DataAgent()
agent.name = "projects/my-project/locations/global/dataAgents/my-agent"
agent.data_analytics_agent.published_context.system_instruction = yaml_text
```

**Expert Insight: Golden Queries**

Example queries (golden queries) dramatically improve SQL generation accuracy:
```python
example = geminidataanalytics.ExampleQuery()
example.natural_language_question = "Top 5 products by revenue"
example.sql_query = "SELECT p.name, SUM(oi.sale_price) as revenue FROM order_items oi JOIN products p ON oi.product_id = p.id GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
```
The agent uses these as templates. If a user asks something similar, the SQL quality is dramatically better.

### Module 4: Chat Handler (`src/chat_handler.py`) — The Core

**API Concept: Two Conversation Modes**

| Aspect | Stateful (Recommended) | Stateless |
|--------|----------------------|-----------|
| History managed by | Google Cloud | Your application |
| Follow-up questions | Automatic context | You send full history each turn |
| Setup required | Create a Conversation resource | Nothing extra |
| IAM role | `dataAgentUser` | `dataAgentStatelessUser` |
| Conversation limit | 50 turns max | No limit (you control) |
| Best for | Interactive chat apps | Simple single-turn queries |

**API Concept: Streaming Response Protocol**

The API returns a **stream** of messages, not a single response. Each chat turn typically produces:

```
Message 1: [ANALYSIS]  → progress_event (reasoning indicator)
Message 2: [ANALYSIS]  → progress_event (more reasoning)
Message 3: [DATA]      → generated_sql (the SQL query text)
Message 4: [DATA]      → generated_sql + result (SQL + query output)
Message 5: [ANALYSIS]  → progress_event (chart reasoning)
Message 6: [DATA]      → result (data rows with schema)
Message 7: [CHART]     → chart.query (chart generation instructions)
Message 8: [CHART]     → chart.result.vega_config (Vega-Lite spec with data)
Message 9: [TEXT]       → text.parts (final text summary)
```

**Each message is a `geminidataanalytics.Message`** with mutually exclusive fields:
- `user_message` → echo of what the user sent
- `system_message.text` → text response
- `system_message.data` → SQL + data results
- `system_message.chart` → chart specs
- `system_message.analysis` → reasoning steps
- `system_message.error` → error messages

**API Concept: Two Separate Clients**

```python
# Client 1: For agent CRUD (create, get, update, delete)
data_agent_client = geminidataanalytics.DataAgentServiceClient()

# Client 2: For conversations and chat (separate gRPC service)
data_chat_client = geminidataanalytics.DataChatServiceClient()
```

This follows Google's standard pattern of one client per gRPC service definition.

### Module 5: Visualization (`src/visualization.py`)

**API Concept: Vega-Lite Chart Specifications**

The API returns charts as Vega-Lite JSON — a declarative visualization grammar:
```json
{
    "title": "Monthly Revenue Trend for 2024",
    "mark": {"type": "line", "point": true, "interpolate": "monotone"},
    "data": {"values": [{"month": 1704067200, "revenue": 37848.82}, ...]},
    "encoding": {
        "x": {"field": "month", "type": "temporal", "title": "Month"},
        "y": {"field": "revenue", "type": "quantitative", "title": "Revenue"}
    }
}
```

**Chart type auto-selection** is based on question keywords:
- "trend", "change", "over time" → **Line chart**
- "compare", "vs", "top N" → **Bar chart**
- "distribution", "proportion" → **Pie chart**
- Column names mentioned → **Table** (no chart)

**Expert Insight**: You can **guide** chart selection by phrasing your question:
- "Show me a bar chart of revenue by category" → Forces bar chart
- "What's the trend in monthly sales?" → Gets a line chart

### Module 6: Streamlit App (`app.py`)

**Key Pattern: Auto-Setup Flow**

The app handles first-run seamlessly:
1. User types a question
2. App checks: Is agent created? → If not, creates it (handles 409 "already exists")
3. App checks: Is conversation created? (stateful mode) → If not, creates one
4. Sends the chat message
5. No manual setup required

**Key Pattern: Session State Management**

Streamlit re-runs the entire script on every interaction. We use `st.session_state` to persist:
- `messages` — Chat history (list of ChatMessage objects)
- `agent_created` — Whether agent exists (bool)
- `conversation_name` — Active conversation ID (string)
- `show_sql` / `show_reasoning` — UI preferences

---

## Part 4: Critical Discoveries — What No Documentation Tells You

These are the most valuable learnings — problems we hit in production that are not covered in any official documentation.

### Critical Discovery #1: The Misleading 403 Error

**Symptom**: Stateful chat returns `403 PermissionDenied: User does not have permission to chat`

**Investigation Timeline**:
1. Checked IAM roles → All correct (`dataAgentCreator`, `dataAgentUser`, `cloudaicompanion.user`, `bigquery.user`)
2. Checked agent-level IAM → Service account has `dataAgentOwner`
3. Created custom IAM role with explicit `geminidataanalytics.dataAgents.chat` permission → Still 403
4. Tested stateless mode → **Works perfectly**
5. Tested stateful with personal credentials → **Different error!**: `400 InvalidArgument: REFERENCES_NOT_SET`

**Root Cause**: The `ConversationReference` in stateful `ChatRequest` was missing `data_agent_context`. Without it, the API can't resolve which data sources to use.

**The Fix**:
```python
# WRONG — causes 403 with service account, 400 with personal creds
request = geminidataanalytics.ChatRequest(
    parent=parent,
    conversation_reference=geminidataanalytics.ConversationReference(
        conversation=conversation_name,
    ),
    messages=[msg],
)

# CORRECT — include data_agent_context in ConversationReference
request = geminidataanalytics.ChatRequest(
    parent=parent,
    conversation_reference=geminidataanalytics.ConversationReference(
        conversation=conversation_name,
        data_agent_context=geminidataanalytics.DataAgentContext(
            data_agent=agent_name,
        ),
    ),
    messages=[msg],
)
```

**Expert Lessons**:
1. **Always test with multiple credential types** — different credentials produce different error messages for the same bug
2. **The API returns misleading errors** — a `403` doesn't always mean permission problems
3. **The SDK docs don't specify which fields are required** — you discover through trial and error
4. **Stateless and stateful modes have different request structures** — stateless uses `data_agent_context` at the top level; stateful uses it nested inside `conversation_reference`

### Critical Discovery #2: Chart Rendering — Protobuf MapComposite

**Symptom**: Charts render as empty frames with axes but no data bars

**Root Cause (Three Layers)**:

**Layer 1: Shallow Protobuf Conversion**
```python
vega_config = chart_result.vega_config  # This is a MapComposite, NOT a dict
spec = dict(vega_config)                 # SHALLOW conversion — nested values remain as proto!
# spec["encoding"] is still a MapComposite → Altair can't read it
```

Fix: Use `MessageToDict` from protobuf for deep conversion:
```python
from google.protobuf.json_format import MessageToDict
cr_dict = MessageToDict(chart_result._pb)  # Deep conversion via ._pb
chart_spec = cr_dict.get('vegaConfig', {})  # Clean Python dict
```

**Key Concept: Proto-Plus `._pb` Attribute**

The Google Cloud SDK uses `proto-plus`, a wrapper around protobuf. Every proto-plus object has a `._pb` attribute that gives you the raw protobuf message:
```python
# proto-plus wrapper (what the SDK returns)
chart_result = sys_msg.chart.result              # proto-plus object
type(chart_result.vega_config)                    # MapComposite

# Raw protobuf (what MessageToDict needs)
chart_result._pb                                  # raw protobuf message
MessageToDict(chart_result._pb)                  # clean Python dict
```

**Layer 2: Altair Serialization Loss**

Even with a clean dict, routing through Altair (`alt.Chart.from_dict()` → `st.altair_chart()`) lost the inline data during serialization.

Fix: Use `st.vega_lite_chart()` which renders Vega-Lite JSON directly:
```python
# BROKEN — Altair serialization loses data
chart = alt.Chart.from_dict(spec)
st.altair_chart(chart)

# WORKING — Streamlit renders Vega-Lite natively
st.vega_lite_chart(spec, use_container_width=True)
```

**Layer 3: Vega-Lite v5 vs v6 Incompatibility**

The API produces v5 specs, but Streamlit's renderer uses Vega-Lite v6. The `transform` field with `window` and `sort` operations fails silently, creating "Infinite extent" errors.

Fix: Strip incompatible transforms:
```python
def _clean_vega_spec(spec):
    # Remove window/sort transforms (data already sorted in data.values)
    if "transform" in spec:
        if any("window" in t or "sort" in t for t in spec["transform"]):
            del spec["transform"]

    # Remove empty sort objects from encoding
    for axis in spec.get("encoding", {}).values():
        if isinstance(axis, dict) and axis.get("sort") == {}:
            del axis["sort"]
```

### Critical Discovery #3: Temporal Data — Unix Seconds vs Milliseconds

**Symptom**: Line chart dates all show "Jan 1970"

**Root Cause**: The API returns dates as Unix timestamps in **seconds** (e.g., `1704067200` = Jan 1, 2024), but Vega-Lite expects **milliseconds** (1704067200000).

**Fix**: Detect temporal fields from the encoding and multiply by 1000:
```python
def _fix_temporal_data(spec):
    for axis in spec.get("encoding", {}).values():
        if axis.get("type") == "temporal":
            field = axis.get("field")
            for row in spec.get("data", {}).get("values", []):
                if 1e8 < row.get(field, 0) < 3e9:  # Looks like seconds
                    row[field] *= 1000               # Convert to milliseconds
```

### Critical Discovery #4: Chart Spec Embedded in Text (Not Chart Field)

**Symptom**: Raw JSON displayed as green text in the chat instead of a rendered chart. The JSON starts with `{"config": {"view": ...}` — an Altair-generated Vega-Lite spec.

**Root Cause**: The API doesn't always return chart specs through `sys_msg.chart.result.vega_config`. Sometimes the entire Vega-Lite spec is embedded as raw JSON in `sys_msg.text.parts` — the text response. Our initial regex-based stripping only matched JSON starting with `{"data":` or fenced code blocks, missing JSON that starts with `{"config":`.

**Additional Complication**: The embedded spec uses `"data": {"name": "data-b241..."}` (Altair's named dataset format) instead of `"data": {"values": [...]}` (inline data). Our rendering code checked only for `data.values` and skipped rendering when it was absent.

**Fix (Two Parts)**:

```python
# Part 1: Robust JSON extraction from text using actual JSON parsing
def _extract_chart_from_text(text):
    """Find ANY JSON object containing 'mark' or 'encoding' keys."""
    for start_pos in find_all_braces(text):
        remaining = text[start_pos:]
        if '"mark"' not in remaining and '"encoding"' not in remaining:
            continue
        try:
            parsed = json.loads(remaining)
            if "encoding" in parsed or "mark" in parsed:
                return text[:start_pos].rstrip(), parsed  # cleaned text, chart spec
        except json.JSONDecodeError:
            # Try to find matching closing brace manually
            ...

# Part 2: Handle named datasets in chart rendering
data_section = spec.get("data", {})
has_data = (
    data_section.get("values")    # inline data
    or data_section.get("name")    # named dataset (Altair format)
    or data_section.get("url")     # URL data source
    or "datasets" in spec          # Altair-style embedded datasets
)
```

**Expert Lesson**: Never assume the API returns chart specs through a single consistent channel. Always implement both:
1. Parse from the dedicated `sys_msg.chart` field (protobuf)
2. Extract from `sys_msg.text` field (embedded JSON)

### Critical Discovery #5: DataResult Protobuf Parsing

**Symptom**: Data tables show empty or missing data

**Root Cause**: `data_result.data` is a `RepeatedComposite` (proto repeated field), not a string or list. `isinstance(d, str)` checks always fail.

**Fix**: Same pattern — use `MessageToDict` for deep conversion:
```python
from google.protobuf.json_format import MessageToDict
dr_dict = MessageToDict(data_result._pb)
rows = dr_dict.get("data", [])         # Clean list of dicts
schema = dr_dict.get("schema", {})     # Clean schema dict
```

**Universal Rule**: When working with the `google-cloud-geminidataanalytics` SDK, **always use `MessageToDict(obj._pb)` to convert proto objects to Python dicts**. Never use `dict()` or manual field access for complex nested structures.

---

## Part 5: IAM & Security Deep Dive

### Required Roles

| Role | Scope | Purpose | Who Needs It |
|------|-------|---------|-------------|
| `geminidataanalytics.dataAgentCreator` | Project | Create agents | Data engineers |
| `geminidataanalytics.dataAgentUser` | Agent/Project | Chat with agents (stateful) | Business users |
| `geminidataanalytics.dataAgentStatelessUser` | Project | Chat without history | API integrations |
| `cloudaicompanion.user` | Project | Create managed conversations | Anyone using stateful mode |
| `bigquery.user` | Project | Query BigQuery data | Anyone chatting |
| `bigquery.dataViewer` | Dataset | Read specific datasets | For fine-grained access |

### IAM Assignment Levels

Roles can be assigned at different levels:
```
Project Level (broad)
  └── gcloud projects add-iam-policy-binding PROJECT_ID \
        --member="serviceAccount:SA@PROJECT.iam.gserviceaccount.com" \
        --role="roles/geminidataanalytics.dataAgentCreator"

Agent Level (granular)
  └── gcloud geminidataanalytics data-agents add-iam-policy-binding AGENT_ID \
        --member="user:analyst@company.com" \
        --role="roles/geminidataanalytics.dataAgentUser"
```

**Expert Insight**: For production, use **agent-level** IAM. Different teams should only access their own agents:
- Marketing team → `marketing_agent` (access to marketing data only)
- Finance team → `finance_agent` (access to financial data only)

### Service Account Setup

```bash
# Create service account
gcloud iam service-accounts create datachat-agent \
  --display-name="DataChat Service Account"

# Grant required roles
for role in geminidataanalytics.dataAgentCreator \
            geminidataanalytics.dataAgentUser \
            cloudaicompanion.user \
            bigquery.user; do
  gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:datachat-agent@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/$role"
done

# Create and download key
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=datachat-agent@PROJECT_ID.iam.gserviceaccount.com
```

---

## Part 6: SDK Internals — What You Need to Know

### Proto-Plus Type System

The `google-cloud-geminidataanalytics` SDK uses `proto-plus`, Google's Python wrapper for protobuf:

```python
# The type hierarchy
from google.cloud import geminidataanalytics

msg = geminidataanalytics.Message()          # proto-plus wrapper
msg._pb                                       # raw protobuf message
type(msg)                                     # <class '...Message'>
type(msg._pb)                                 # <class '...Message_pb2.Message'>
```

### Common Proto-Plus Collection Types

| SDK Type | Python Equivalent | How to Convert |
|----------|------------------|----------------|
| `MapComposite` | `dict` | `MessageToDict(obj._pb)` or `dict(obj)` (shallow!) |
| `RepeatedComposite` | `list` | `MessageToDict(obj._pb)` or `list(obj)` (shallow!) |
| `str`, `int`, `float` | Same | Direct access |
| `bool` | Same | Direct access |
| `bytes` | `bytes` | Direct access |

### The MessageToDict Pattern

```python
from google.protobuf.json_format import MessageToDict

# Convert any proto-plus object to a clean Python dict
clean_dict = MessageToDict(proto_plus_object._pb)

# Note: MessageToDict uses camelCase keys (protobuf convention)
# "vega_config" in proto-plus → "vegaConfig" in MessageToDict output
```

### Streaming Pattern

```python
# The chat method returns an iterator of response messages
response_stream = client.chat(request=chat_request)

# Each iteration yields one Message from the stream
for msg in response_stream:
    # msg.system_message contains the actual response content
    sys_msg = msg.system_message
    if sys_msg:
        if sys_msg.text:    # Text content
        if sys_msg.data:    # SQL + data results
        if sys_msg.chart:   # Vega-Lite chart specs
        if sys_msg.analysis:  # Reasoning steps
        if sys_msg.error:   # Error messages
```

---

## Part 7: Production Readiness Checklist

If you were to deploy DataChat to production, here's what would need to change:

### Authentication
- [ ] Use **Workload Identity Federation** instead of service account key files
- [ ] Rotate service account keys regularly (or eliminate them entirely)
- [ ] Use **VPC Service Controls** for sensitive data

### Error Handling
- [ ] Implement exponential backoff for API rate limits (10 QPS, 600 QPM)
- [ ] Handle `ServiceUnavailable` (503) with retry
- [ ] Log all API errors with request IDs for support escalation

### Scalability
- [ ] Use a persistent database for conversation history (not Streamlit session state)
- [ ] Deploy on Cloud Run with auto-scaling
- [ ] Use connection pooling for API clients

### Security
- [ ] Never expose service account keys in the frontend
- [ ] Use agent-level IAM (not project-level) for multi-tenant deployments
- [ ] Enable audit logging for all API calls
- [ ] Implement row-level security in BigQuery if needed

### Cost Management
- [ ] API is free during Preview, but BigQuery queries cost money
- [ ] Monitor BigQuery slot usage and query complexity
- [ ] Set budget alerts for unexpected query volume

---

## Part 8: The Big Picture — Comparison with Other Approaches

### DataChat vs Your "Data Agent - Basic" Project

| Aspect | DataChat (CA API) | Data Agent - Basic (Custom) |
|--------|------------------|-----------------------------|
| **Lines of code** | ~2,000 | ~3,000+ |
| **SQL generation** | Google's Gemini (managed) | Custom LangGraph pipeline |
| **Retry logic** | Automatic (3 attempts) | Custom error handler |
| **Conversation memory** | API-managed stateful mode | Custom persistence |
| **RAG/Context** | Authored context (structured + YAML) | Custom FAISS vector store |
| **Visualization** | API generates Vega-Lite specs | Not included |
| **Data sources** | BigQuery, Looker | Azure SQL, any ODBC |
| **LLM** | Gemini (built-in) | Azure OpenAI GPT-4 |
| **Setup effort** | Enable 3 APIs, authenticate | Install ODBC, configure Azure |
| **Customization** | Limited to API capabilities | Full control |

### When to Use Which Approach

**Use Conversational Analytics API when**:
- Data is in BigQuery or Looker
- You want to ship fast (days, not weeks)
- You trust Google's reasoning engine
- You don't need custom SQL post-processing
- Chart generation is important

**Use Custom Agent (ADK/LangGraph) when**:
- Data is in SQL Server, Postgres, or other databases
- You need custom SQL generation logic
- You need RAG over unstructured documents alongside data
- You need full control over the reasoning loop
- You're building a multi-agent orchestration system

### Integration with Google ADK

The Conversational Analytics API can be used **inside** an ADK agent via `ask_data_insights`:
```python
# ADK agent that delegates data questions to the CA API
from google.adk.tools import ask_data_insights

class OrchestratorAgent:
    def handle(self, query):
        if is_data_question(query):
            return ask_data_insights(query, agent="ecommerce_agent")
        elif is_action_request(query):
            return process_action(query)
```

This is the **multi-agent pattern** — a general-purpose agent orchestrates specialized sub-agents.

---

## Part 9: Key Patterns & Best Practices

### Pattern 1: Fallback Chart Rendering

When the API provides a chart spec, use it. Otherwise, create a fallback from data:
```python
has_api_chart = any(m.message_type == "chart" and m.chart_spec for m in messages)

for msg in messages:
    if msg.message_type == "chart" and msg.chart_spec:
        st.vega_lite_chart(clean_spec(msg.chart_spec))
    elif msg.message_type == "data" and not has_api_chart:
        chart = create_chart_from_data(msg.data)  # Fallback
        st.altair_chart(chart)
```

### Pattern 2: Spec Cleaning Pipeline

Always clean API-generated Vega-Lite specs before rendering:
```python
def clean_vega_spec(spec):
    spec = deep_copy(spec)
    remove_incompatible_transforms(spec)    # v5→v6 compat
    clean_empty_sort_objects(spec)           # Encoding cleanup
    fix_temporal_data(spec)                  # seconds → milliseconds
    return spec
```

### Pattern 3: Strip Embedded JSON from Text

The API sometimes embeds chart specs as raw JSON in text responses:
```python
def strip_vega_json(text):
    # Remove fenced code blocks with Vega specs
    text = re.sub(r'```json?\s*\{.*?"encoding".*?\}\s*```', '', text, flags=re.DOTALL)
    # Remove inline Vega JSON
    text = re.sub(r'\{"data":.*?"encoding".*$', '', text, flags=re.DOTALL)
    return text.strip()
```

### Pattern 4: Graceful Agent Creation

Handle the "already exists" case without failing:
```python
try:
    client.create_data_agent(request)
    print("Agent created")
except google.api_core.exceptions.AlreadyExists:
    print("Agent already exists, using it")
    # Continue — no error
```

---

## Part 10: Glossary of Key Terms

| Term | Definition |
|------|-----------|
| **Data Agent** | A persistent AI assistant configured with data source connections and business context |
| **Authored Context** | The combination of structured context (BigQuery metadata) and system instructions (YAML) that guide agent behavior |
| **Structured Context** | Table descriptions, column descriptions, synonyms, and example queries (BigQuery-specific) |
| **System Instructions** | YAML-formatted text that defines the agent's role, guidelines, and restrictions |
| **Golden Query** | An example query (NL question + SQL) that teaches the agent the correct query pattern |
| **Conversation** | A managed resource in Google Cloud that stores chat history for stateful mode |
| **ConversationReference** | The request field that links a chat message to an existing conversation (stateful mode) |
| **DataAgentContext** | The request field that links a chat message to a data agent's configuration |
| **Vega-Lite** | A declarative JSON grammar for describing interactive visualizations |
| **MapComposite** | A proto-plus collection type that wraps protobuf map fields |
| **RepeatedComposite** | A proto-plus collection type that wraps protobuf repeated fields |
| **ADC** | Application Default Credentials — Google's standard auth pattern |
| **Proto-plus** | Google's Python wrapper library for protobuf messages |
| **ReAct** | Reason + Act — the agentic AI pattern of reasoning about what to do, then executing |

---

## Part 11: Demo Script — Showcasing All Features

### Setup (before demo)
1. Ensure Streamlit is running (`streamlit run app.py`)
2. Ensure agent exists (the app auto-creates it)

### Demo Sequence

**1. Bar Chart + Data Table** (Natural Language → SQL → Data → Chart)
```
Ask: "Show me the top 5 product categories by revenue"
Shows: Generated SQL (expandable) + Data table + Bar chart + Text summary
```

**2. Follow-Up Question** (Multi-turn context retention)
```
Ask: "Now show me the monthly trend for the top category"
Shows: Agent remembers "top category" = Outerwear & Coats from previous answer
       Line chart with proper month labels (Jan–Dec)
```

**3. Simple Data Query** (Table-only response)
```
Ask: "How many customers signed up in 2024?"
Shows: Data table with monthly signups + Text summary
```

**4. Toggle Show SQL** (Behind-the-scenes)
```
Click: "Show Generated SQL" checkbox
Shows: The actual SQL the agent generated — great for learning SQL
```

**5. Switch to Stateless Mode** (Mode comparison)
```
Click: "stateless" radio button
Ask: Same question — compare behavior
Shows: Works the same but conversation history is managed client-side
```

**6. Agent Management** (CRUD operations)
```
Click: "List Agents" — shows existing agents
Click: "Delete Agent" + "Create Agent" — demonstrates lifecycle
```

---

## Part 12: Next Steps for Mastery

1. **Run the Colab notebooks** to see the HTTP approach and compare with SDK
2. **Experiment with system instructions** — change the YAML and observe how answers differ
3. **Connect Looker Explores** — test with Looker data sources (requires Looker instance)
4. **Try the multi-agent pattern** — create specialized agents and an ADK orchestrator
5. **Enable Python analysis** — ask questions that need statistical calculations beyond SQL
6. **Build a production deployment** — Cloud Run + Workload Identity + Firestore for sessions
7. **Compare with custom agents** — implement the same features using ADK/LangGraph
8. **Explore A2A and MCP** — understand agent communication protocols
9. **Read the generated SQL** — enable "Show SQL" to learn query patterns from the AI
10. **Contribute to the ecosystem** — write the LinkedIn article about your experience

---

## Appendix: Files Modified During the Journey

| File | What Changed | Why |
|------|-------------|-----|
| `src/chat_handler.py` | Added `data_agent_context` to `ConversationReference` | Fix stateful chat 403 error |
| `src/chat_handler.py` | Used `MessageToDict` for chart + data parsing | Fix proto MapComposite conversion |
| `src/chat_handler.py` | Added `_strip_vega_json()` | Remove raw JSON from text responses |
| `src/visualization.py` | Added `_clean_vega_spec()` | Fix Vega-Lite v5→v6 compatibility |
| `src/visualization.py` | Added `_fix_temporal_data()` | Fix Unix timestamp seconds→milliseconds |
| `app.py` | Used `st.vega_lite_chart()` instead of `st.altair_chart()` | Fix chart data loss during Altair serialization |
| `app.py` | Added `has_api_chart` flag | Prevent duplicate charts |
| `app.py` | Fixed `use_container_width` deprecation | Streamlit 2026 API changes |
| `src/chat_handler.py` | Added `_extract_chart_from_text()` | Extract chart specs embedded in text responses (not just chart field) |
| `app.py` | Added named dataset support in chart rendering | Handle `data.name` format (Altair-style) not just `data.values` |
| `config/settings.py` | Changed default mode to `"stateful"` | After fixing stateful chat |
