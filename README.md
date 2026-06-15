# DOTMappers Support Ticket AI

A local Streamlit application that loads 500 support tickets from Excel and
uses an n8n Cloud workflow with Groq for natural-language analysis. Anomaly
detection is deterministic and runs inside n8n.

## Features

- Local Excel ingestion and dataset overview
- Natural-language questions converted to a restricted JSON query plan
- No `eval()` or execution of LLM-generated code
- High/Critical unresolved-ticket SLA detection
- Statistical resolution-time outlier detection
- Portable n8n workflow and one-command Streamlit startup

## Architecture

```text
support_tickets.xlsx -> Streamlit -> n8n Webhook
                                      |-- Groq -> validated query plan -> Code node
                                      |-- deterministic anomaly Code node
                         Streamlit <- JSON response
```

Streamlit sends the 500 ticket records to n8n for each analysis request. Groq
receives only the question, schema rules, and reference date. It returns a
structured query plan; a Code node validates the plan against approved fields,
operators, and aggregations before executing it.

Relative phrases such as "this week" and "this month" use the latest
`created_at` value in the historical dataset.

## 1. Security First

The original prototype contained Groq tokens in source code. Revoke
any tokens before sharing this repository. This version does not use either
token locally and does not contain hardcoded credentials.

Do not commit `.streamlit/secrets.toml`.

## 2. Configure n8n Cloud

1. Sign in to `https://***********.app.n8n.cloud/`.
2. Open `https://************.app.n8n.cloud/workflow/g710epe8Jt84qVcK`.
3. From the workflow menu, choose **Import from File** and select
   `n8n_support_workflow.json`.
4. Open the **Groq Chat Model** node.
5. Create or select a Groq credential using the new Groq API key.
6. Save the workflow.

If importing would overwrite work that must be retained, import the JSON as a
new workflow and use that workflow's production webhook URL.

### Test the workflow

1. Open **Support AI Webhook**.
2. Select the test URL and click **Listen for test event**.
3. Temporarily put the test URL in `.streamlit/secrets.toml`.
4. Start Streamlit and confirm the sidebar shows n8n as connected.
5. Run one natural-language query and one anomaly check.

### Activate the workflow

1. Activate or publish the n8n workflow.
2. Open **Support AI Webhook** and copy its production URL. It should end with
   `/webhook/support-ai`.
3. Replace the test URL with the production URL in
   `.streamlit/secrets.toml`.

The webhook is intentionally unauthenticated for this time-limited prototype.
Add header authentication before using real customer data.

## 3. Configure Streamlit

Create the local secrets file:

```powershell
New-Item -ItemType Directory -Force .streamlit
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

Set the production webhook:

```toml
N8N_WEBHOOK_URL = "https://your-instance.app.n8n.cloud/webhook/support-ai"
```

## 4. Install and Run

Python 3.11 or newer is required.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

If the virtual environment does not exist:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

## 5. Demonstration Queries

1. `How many tickets are currently open?`
2. `Which agent has the lowest average customer rating?`
3. `Which agent resolved the most tickets this month?`
4. `Show all Critical tickets not resolved within 12 hours.`
5. `What is the average customer rating for Technical tickets?`

Then open **Anomaly Detection** and show:

- unresolved High/Critical tickets older than 24 hours;
- resolved tickets above mean plus two standard deviations.

## Optional Gmail Alert

Gmail is not required by the assessment. To demonstrate automation:

1. Add a Gmail node after **Detect Anomalies**.
2. Configure an n8n Gmail OAuth credential.
3. Send only when the SLA breach list is not empty.
4. Include the count and ticket IDs in the message.
5. Keep the existing connection to **Return Anomalies**, so Streamlit still
   receives its response.

Do not place Gmail credentials or recipient addresses in this repository.

## Response Contract

The webhook accepts:

```json
{
  "action": "query",
  "question": "How many tickets are currently open?",
  "reference_date": "2024-03-31T18:00:00",
  "tickets": []
}
```

Supported actions are `health`, `query`, and `anomalies`.

A query response contains `ok`, `answer`, `rows`, `summary`, and the validated
`plan`. An anomaly response contains `sla_breaches`, `resolution_outliers`,
and the statistical threshold.

## Error Handling

The UI reports missing webhook configuration, connection and timeout failures,
non-JSON responses, HTTP errors, unsafe Groq plans, and invalid dataset
columns.

## Known Limitations

- The unauthenticated webhook is suitable only for this prototype.
- The full 500-row dataset is sent with each analysis request.
- n8n Cloud availability and the Groq free tier are external dependencies.
- Query intent is limited to approved filter and aggregation operations.
- Relative dates use the dataset's latest timestamp rather than today's date.

## Walkthrough Talking Points

- The LLM understands intent but never receives permission to execute code.
- Query execution and anomaly rules are deterministic and inspectable.
- n8n can later add Slack, Gmail, database, or ticketing actions.
- Production improvements include webhook authentication, persistent storage,
  automated tests, retry policies, and sending dataset IDs instead of all rows.
