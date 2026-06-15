from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "support_tickets (2).xlsx"
EXPECTED_COLUMNS = {
    "ticket_id",
    "created_at",
    "category",
    "priority",
    "status",
    "response_time_hrs",
    "resolution_time_hrs",
    "agent_id",
    "customer_rating",
    "issue_summary",
}
REQUEST_TIMEOUT_SECONDS = 45


st.set_page_config(
    page_title="DOTMappers Support AI",
    page_icon=":material/support_agent:",
    layout="wide",
)


def get_webhook_url() -> str:
    try:
        return str(st.secrets.get("N8N_WEBHOOK_URL", "")).strip()
    except (FileNotFoundError, KeyError):
        return ""


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, engine="openpyxl")
    missing = EXPECTED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {', '.join(sorted(missing))}")

    frame = frame.copy()
    frame["created_at"] = pd.to_datetime(frame["created_at"], errors="coerce")
    if frame["created_at"].isna().any():
        raise ValueError("One or more created_at values are invalid.")
    return frame


def records_for_api(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.copy()
    clean["created_at"] = clean["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    clean = clean.astype(object).where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


def call_n8n(
    action: str,
    *,
    frame: pd.DataFrame | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    webhook_url = get_webhook_url()
    if not webhook_url:
        raise RuntimeError(
            "n8n is not configured. Create .streamlit/secrets.toml and add "
            'N8N_WEBHOOK_URL = "https://saipatil1666.app.n8n.cloud/webhook/1408fe67-b992-4bad-9663-36b7a67b4067"'
        )

    payload: dict[str, Any] = {"action": action}
    if frame is not None:
        payload["reference_date"] = frame["created_at"].max().isoformat()
        payload["tickets"] = records_for_api(frame)
    if question is not None:
        payload["question"] = question

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise RuntimeError(
            f"n8n did not respond within {REQUEST_TIMEOUT_SECONDS} seconds."
        ) from exc
    except requests.ConnectionError as exc:
        raise RuntimeError("Could not connect to the configured n8n webhook.") from exc
    except requests.HTTPError as exc:
        detail = response.text[:300].strip()
        raise RuntimeError(
            f"n8n returned HTTP {response.status_code}: {detail or 'No details'}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("n8n returned a response that was not valid JSON.") from exc

    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict):
        raise RuntimeError("n8n returned an unexpected response shape.")
    if data.get("ok") is False:
        raise RuntimeError(str(data.get("error", "The n8n workflow failed.")))
    return data


@st.cache_data(ttl=60, show_spinner=False)
def check_n8n_connection(webhook_url: str) -> tuple[bool, str]:
    if not webhook_url:
        return False, "Not configured"
    try:
        result = call_n8n("health")
        return bool(result.get("ok")), str(result.get("message", "Connected"))
    except RuntimeError as exc:
        return False, str(exc)


def render_result(result: dict[str, Any]) -> None:
    answer = result.get("answer")
    rows = result.get("rows", [])
    summary = result.get("summary")

    if answer is not None:
        st.success("Analysis complete")
        if isinstance(answer, (int, float)):
            st.metric("Answer", answer)
        else:
            st.markdown(f"**Answer:** {answer}")

    if summary:
        st.caption(str(summary))

    if isinstance(rows, list) and rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    elif answer is None:
        st.info("The workflow completed but returned no matching records.")


def render_anomaly_section(
    title: str,
    description: str,
    rows: Any,
) -> None:
    records = rows if isinstance(rows, list) else []
    st.subheader(f"{title} ({len(records)})")
    st.caption(description)
    if records:
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    else:
        st.info("No matching anomalies were found.")


st.title("AI Support Ticket Intelligence")
st.caption("Local Streamlit dashboard with Groq-powered analysis orchestrated by n8n")

if not DATA_FILE.exists():
    st.error(f"Dataset not found: {DATA_FILE.name}")
    st.stop()

try:
    df = load_data(DATA_FILE)
except (ValueError, OSError) as exc:
    st.error(f"Could not load the ticket dataset: {exc}")
    st.stop()

reference_date = df["created_at"].max()
webhook_url = get_webhook_url()
connected, connection_message = check_n8n_connection(webhook_url)

with st.sidebar:
    st.header("System status")
    if connected:
        st.success(f"n8n: {connection_message}")
    elif webhook_url:
        st.error("n8n: Connection failed")
        st.caption(connection_message)
    else:
        st.warning("n8n: Not configured")
        st.code(
            'N8N_WEBHOOK_URL = "https://your-instance.app.n8n.cloud/'
            'webhook/support-ai"',
            language="toml",
        )

    st.divider()
    st.write(f"Dataset: `{DATA_FILE.name}`")
    st.write(f"Rows: **{len(df):,}**")
    st.write(f"Reference date: **{reference_date:%Y-%m-%d}**")
    st.caption(
        "Relative questions such as 'this month' use the latest date in the dataset."
    )
    if st.button("Refresh connection"):
        check_n8n_connection.clear()
        st.rerun()

overview_tab, query_tab, anomaly_tab = st.tabs(
    ["Overview", "Natural Language Query", "Anomaly Detection"]
)

with overview_tab:
    open_count = int(df["status"].eq("Open").sum())
    unresolved_count = int(df["status"].ne("Resolved").sum())
    critical_unresolved = int(
        (df["priority"].eq("Critical") & df["status"].ne("Resolved")).sum()
    )
    average_rating = df["customer_rating"].mean()

    metric_columns = st.columns(4)
    metric_columns[0].metric("Total tickets", f"{len(df):,}")
    metric_columns[1].metric("Open tickets", open_count)
    metric_columns[2].metric("Unresolved critical", critical_unresolved)
    metric_columns[3].metric(
        "Average rating",
        f"{average_rating:.2f}" if pd.notna(average_rating) else "N/A",
    )

    chart_columns = st.columns(2)
    with chart_columns[0]:
        st.subheader("Tickets by status")
        st.bar_chart(df["status"].value_counts())
    with chart_columns[1]:
        st.subheader("Tickets by priority")
        priority_order = ["Critical", "High", "Medium", "Low"]
        priority_counts = df["priority"].value_counts().reindex(priority_order).fillna(0)
        st.bar_chart(priority_counts)

    st.subheader("Ticket data")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Total unresolved tickets: {unresolved_count}")

with query_tab:
    st.subheader("Ask the ticket data")
    st.write(
        "Groq converts your question into a restricted query plan. "
        "n8n validates and executes that plan without Python eval."
    )
    question = st.text_input(
        "Question",
        placeholder="Which agent has the lowest average customer rating?",
    )
    with st.expander("Example questions"):
        st.markdown(
            """
- How many tickets are currently open?
- Which agent has the lowest average customer rating?
- Which agent resolved the most tickets this month?
- Show all Critical tickets not resolved within 12 hours.
- What is the average customer rating for Technical tickets?
"""
        )

    if st.button("Run query", type="primary", disabled=not question.strip()):
        with st.spinner("n8n and Groq are analyzing the ticket data..."):
            try:
                query_result = call_n8n("query", frame=df, question=question.strip())
                render_result(query_result)
                with st.expander("Validated query plan"):
                    st.json(query_result.get("plan", {}))
            except RuntimeError as exc:
                st.error(str(exc))

with anomaly_tab:
    st.subheader("Operational anomalies")
    st.write(
        "Detect unresolved High/Critical tickets older than 24 hours and unusually "
        "long resolved tickets using the mean plus two standard deviations."
    )

    if st.button("Detect anomalies", type="primary"):
        with st.spinner("n8n is running deterministic anomaly checks..."):
            try:
                anomaly_result = call_n8n("anomalies", frame=df)
                threshold = anomaly_result.get("resolution_threshold_hrs")
                if threshold is not None:
                    st.metric("Resolution outlier threshold", f"{threshold:.2f} hours")

                render_anomaly_section(
                    "SLA breaches",
                    "Unresolved High/Critical tickets older than 24 hours.",
                    anomaly_result.get("sla_breaches"),
                )
                render_anomaly_section(
                    "Resolution outliers",
                    "Resolved tickets above mean + 2 standard deviations.",
                    anomaly_result.get("resolution_outliers"),
                )
            except RuntimeError as exc:
                st.error(str(exc))
