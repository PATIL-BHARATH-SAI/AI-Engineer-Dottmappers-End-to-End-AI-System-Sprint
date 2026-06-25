import streamlit as st
import requests
import pandas as pd
import json

# Page Config
st.set_page_config(
    page_title="AI Support Intelligence Dashboard",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Premium Gradients and micro-animations)
st.markdown("""
    <style>
    .main {
        background-color: #0f111a;
        color: #e2e8f0;
    }
    .stMetric {
        background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%);
        border: 1px solid #4c1d95;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: transform 0.2s;
    }
    .stMetric:hover {
        transform: translateY(-3px);
        border-color: #a855f7;
    }
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        background: linear-gradient(to right, #a855f7, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .card {
        background-color: #1e293b;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
        border-left: 5px solid #6366f1;
    }
    .anomaly-card {
        background-color: #1e1b1b;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
        border-left: 5px solid #ef4444;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.title("⚙️ Connection Settings")
n8n_query_url = st.sidebar.text_input(
    "N8N Query Webhook URL",
    value=st.secrets.get("N8N_WEBHOOK_QUERY_URL", "https://saipatil1666.app.n8n.cloud/webhook/query")
)
n8n_anomalies_url = st.sidebar.text_input(
    "N8N Anomalies Webhook URL",
    value=st.secrets.get("N8N_WEBHOOK_ANOMALIES_URL", "https://saipatil1666.app.n8n.cloud/webhook/anomalies")
)
n8n_health_url = st.sidebar.text_input(
    "N8N Health Webhook URL",
    value=st.secrets.get("N8N_WEBHOOK_HEALTH_URL", "https://saipatil1666.app.n8n.cloud/webhook/health")
)

st.sidebar.info("💡 Ensure your n8n workflow is Active and Webhook triggers are live.")

# App Header
st.title("🎫 AI Support Intelligence Dashboard")
st.subheader("DOTMappers Customer Support Insights Portal")

# Load Tickets Data
@st.cache_data
def load_tickets_data():
    try:
        # Load from support_tickets (2).xlsx
        df = pd.read_excel("support_tickets (2).xlsx")
        # Ensure correct string formatting of datetime
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
        # Replace NaN/nulls with None so they serialize cleanly to JSON
        df = df.astype(object).where(pd.notnull(df), None)
        return df.to_dict(orient='records')
    except Exception as e:
        st.error(f"Error loading Excel file: {e}")
        return []

tickets_data = load_tickets_data()

# Fetch Anomaly Data for use in overview and tab2
@st.cache_data(ttl=10)
def fetch_anomalies(webhook_url):
    try:
        res = requests.post(webhook_url, timeout=30)
        if res.status_code == 200:
            try:
                data = res.json()
            except ValueError:
                st.error("Invalid JSON received from n8n.")
                return []
            
            if isinstance(data, list):
                if len(data) > 0:
                    data = data[0]
                else:
                    return []
            
            if isinstance(data, dict):
                if "message" in data and "anomalies" not in data:
                    st.warning(f"n8n webhook message: {data['message']}")
                    return []
                return data.get("anomalies", [])
            return []
        else:
            st.error(f"n8n returned status code {res.status_code}: {res.text}")
    except Exception as e:
        st.error(f"Error connecting to n8n anomalies webhook: {e}")
    return []

anomalies = fetch_anomalies(n8n_anomalies_url)

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Analytics Overview", "🚨 Anomaly Monitor", "💬 AI Chat Assistant"])

with tab1:
    st.markdown("### Key Operational Metrics")
    
    # Calculate metrics dynamically
    total_tickets = len(tickets_data)
    
    # Average rating calculation
    ratings = [t['customer_rating'] for t in tickets_data if t['customer_rating'] is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    
    # Unresolved tickets (Open or Escalated)
    unresolved_tickets = len([t for t in tickets_data if t['status'] in ['Open', 'Escalated']])
    
    # Grid columns
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Total Ingested Tickets", str(total_tickets), help="Total records loaded into n8n Python engine")
    col2.metric("Average Customer Rating", f"{avg_rating:.2f} / 5.0" if avg_rating else "N/A", help="Average customer satisfaction score")
    col3.metric("Unresolved Tickets", str(unresolved_tickets), help="Tickets with status Open or Escalated")
    col4.metric("Flagged Anomalies", str(len(anomalies)), delta_color="inverse")
    
    st.markdown("---")
    
    st.markdown("### Ticket Category Distribution")
    if tickets_data:
        df_tickets = pd.DataFrame(tickets_data)
        cat_counts = df_tickets['category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Tickets']
        st.bar_chart(cat_counts.set_index("Category"))
    else:
        st.write("No ticket data available.")

with tab2:
    st.markdown("### Flagged SLA Violations & Anomalies")
    st.write("Below are tickets flagged by the n8n Python engine for exceeding response times or SLA breaches:")
    
    if not anomalies:
        st.success("🎉 No active anomalies or SLA breaches detected!")
    else:
        for idx, item in enumerate(anomalies):
            with st.container():
                st.markdown(
                    f"""
                    <div class="anomaly-card">
                        <h4>Ticket: {item['ticket_id']} | Priority: <span style="color:#ef4444">{item['priority']}</span></h4>
                        <p><strong>Reason:</strong> {item['reason']}</p>
                        <p><strong>Summary:</strong> {item['issue_summary']}</p>
                        <p><strong>Agent:</strong> {item['agent_id']} | <strong>Status:</strong> {item['status']} | <strong>Created:</strong> {item['created_at']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

with tab3:
    st.markdown("### Query the Tickets Database")
    st.write("Ask natural language questions about the support tickets (e.g., 'How many billing tickets are open?' or 'Which agent has the lowest average customer rating?')")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Enter your question here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("AI Agent is analyzing the dataset..."):
                try:
                    payload = {"question": prompt}
                    res = requests.post(n8n_query_url, json=payload, timeout=30)
                    if res.status_code == 200:
                        try:
                            data = res.json()
                        except ValueError:
                            data = {}
                        
                        # Robust parsing of response
                        ans = ""
                        if isinstance(data, str):
                            try:
                                data = json.loads(data)
                            except Exception:
                                ans = data
                        
                        if not ans:
                            if isinstance(data, list):
                                if len(data) > 0:
                                    data = data[0]
                                else:
                                    data = {}
                            
                            if isinstance(data, dict):
                                ans = data.get("answer", data.get("output", data.get("message", "Sorry, I received an empty response from n8n.")))
                            else:
                                ans = str(data)
                            
                        st.markdown(ans)
                        st.session_state.messages.append({"role": "assistant", "content": ans})
                    else:
                        error_msg = f"Error: n8n returned status code {res.status_code}. Details: {res.text}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
                except Exception as e:
                    error_msg = f"Failed to connect to n8n: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
