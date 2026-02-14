# DataChat - Chat with Your Data

A Streamlit-based application that uses **Google Cloud's Conversational Analytics API** to let users ask natural language questions about structured data in BigQuery and receive answers with auto-generated SQL, data tables, and charts.

## Architecture

```
User (Streamlit UI)
    ↓ Natural Language Question
app.py (Streamlit)
    ↓
src/chat_handler.py → Conversational Analytics API
    ↓                    ↓ Reasoning Engine
src/visualization.py     ↓ SQL Generation
    ↓                    ↓ Python Analysis
Vega-Lite Charts      BigQuery Data
    ↓
User sees: Text + Tables + Charts
```

## What This Project Demonstrates

1. **Agent Creation**: Programmatically create AI data agents with business context
2. **Stateful Conversations**: Multi-turn Q&A with automatic history management
3. **Authored Context**: YAML system instructions that shape agent behavior
4. **Structured Context**: Table/column descriptions for accurate SQL generation
5. **Streaming Responses**: Real-time response processing from the API
6. **Visualization**: Auto-rendering of Vega-Lite chart specs from the API
7. **IAM Integration**: Proper GCP authentication and access control

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| API | Google Cloud Conversational Analytics API |
| SDK | `google-cloud-geminidataanalytics` (Python) |
| Data | BigQuery (TheLook E-Commerce public dataset) |
| Charts | Vega-Lite (via Streamlit + Altair) |
| Config | Pydantic Settings + YAML |

## Prerequisites

1. **Google Cloud account** with a project
2. **gcloud CLI** installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
3. **Python 3.10+**

## Setup

### 1. Enable Required APIs

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable the three required APIs
gcloud services enable geminidataanalytics.googleapis.com --project=YOUR_PROJECT_ID
gcloud services enable cloudaicompanion.googleapis.com --project=YOUR_PROJECT_ID
gcloud services enable bigquery.googleapis.com --project=YOUR_PROJECT_ID
```

### 2. Grant IAM Roles

```bash
# Grant yourself the required roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/geminidataanalytics.dataAgentCreator"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/cloudaicompanion.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:YOUR_EMAIL" \
  --role="roles/bigquery.user"
```

### 3. Authenticate

```bash
gcloud auth application-default login
```

### 4. Install Dependencies

```bash
cd DataChat
pip install -r requirements.txt
```

### 5. Configure

Copy `env.example` to `.env` and set your project ID:

```
GCP_PROJECT_ID=your-gcp-project-id
```

### 6. Run

```bash
streamlit run app.py
```

## Usage

1. **Set Project ID** in the sidebar
2. **Check Auth** — click to verify authentication
3. **Create Agent** — creates the data agent with BigQuery connection
4. **Ask Questions** — type natural language questions in the chat input

### Example Questions

| Category | Question |
|----------|----------|
| Revenue | "What are the top 10 product categories by total revenue?" |
| Trends | "Show me the monthly revenue trend for 2024" |
| Customers | "How many new customers signed up each month?" |
| Products | "Which brand has the highest average order value?" |
| Comparison | "Compare Men's vs Women's department sales" |
| Analysis | "What traffic source brings the most valuable customers?" |

## Project Structure

```
DataChat/
├── app.py                              # Main Streamlit application
├── config/
│   ├── __init__.py
│   ├── settings.py                     # Pydantic settings (env vars)
│   └── system_instructions.yaml        # Agent behavior instructions
├── src/
│   ├── __init__.py
│   ├── auth.py                         # GCP authentication helpers
│   ├── agent_manager.py                # Data agent CRUD operations
│   ├── chat_handler.py                 # Conversation + chat logic
│   └── visualization.py               # Chart rendering (Vega-Lite)
├── .streamlit/
│   └── config.toml                     # Streamlit theme config
├── requirements.txt                    # Python dependencies
├── env.example                         # Environment variable template
├── start.bat                           # Windows launch script
├── LEARNING_NOTES.md                   # Detailed learning journey & notes
├── LICENSE                             # MIT License
└── README.md                           # This file
```

## Key Files Explained

| File | Purpose | Key Learning |
|------|---------|-------------|
| `config/settings.py` | Centralized configuration | Pydantic Settings for typed config with env var support |
| `config/system_instructions.yaml` | Agent behavior rules | YAML format recommended by Google for system instructions |
| `src/auth.py` | Authentication | Application Default Credentials (ADC) pattern |
| `src/agent_manager.py` | Agent lifecycle | Create/Get/List/Delete agents with the SDK |
| `src/chat_handler.py` | Chat logic | Stateful vs stateless conversations, streaming responses |
| `src/visualization.py` | Chart rendering | Vega-Lite specs → Charts (with protobuf/version fixes) |
| `app.py` | Streamlit UI | Bringing all modules together in an interactive app |


## API Rate Limits

- **10 QPS** (Queries Per Second)
- **600 QPM** (Queries Per Minute) per project
- **No billing** for the API during Preview

## Resources

- [Official Documentation](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/overview)
- [Python SDK Reference](https://docs.cloud.google.com/python/docs/reference/google-cloud-geminidataanalytics/latest)
- [Official Codelab](https://codelabs.developers.google.com/ca-api-bigquery) — Step-by-step tutorial from Google
- [HTTP Colab Notebook](https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/agents/gemini_data_analytics/intro_gemini_data_analytics_http.ipynb)
- [SDK Colab Notebook](https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/agents/gemini_data_analytics/intro_gemini_data_analytics_sdk.ipynb)
- [Release Notes](https://cloud.google.com/gemini/docs/conversational-analytics-api/release-notes)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
