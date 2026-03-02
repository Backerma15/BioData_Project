import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# --- 1. DATABASE CONFIG ---
# Load environment variables from .env file
import os.path

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=env_path, override=True)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port": 5432,
    "sslmode": "require"
}

# Validate config before attempting connection
missing_vars = [k for k, v in DB_CONFIG.items() if v is None and k != "port"]
if missing_vars:
    st.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
    st.stop()

# --- 2. DATA FETCHING LOGIC ---
@st.cache_data(ttl=10)
def get_lab_data():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = "SELECT * FROM lab_readings ORDER BY timestamp DESC LIMIT 500"
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"📡 Database Connection Error: {e}")
        return pd.DataFrame()

# --- 3. STREAMLIT UI SETUP & STYLING ---
st.set_page_config(page_title="BioTech Lab Monitor", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for professional lab instrument style
st.markdown("""
    <style>
    .header-section {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    .status-light {
        display: inline-block;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        margin-right: 8px;
        vertical-align: middle;
    }
    .metric-card {
        background: #f5f5f5;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid;
        text-align: center;
    }
    .metric-value {
        font-size: 32px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 12px;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .status-normal { border-left-color: #2ecc71; background-color: #f0fff4; }
    .status-warning { border-left-color: #f39c12; background-color: #fffbf0; }
    .status-critical { border-left-color: #e74c3c; background-color: #fff5f5; }
    .footer-section {
        background: #ecf0f1;
        padding: 15px;
        border-radius: 8px;
        margin-top: 20px;
        font-size: 12px;
        color: #7f8c8d;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATA FETCHING ---
df = get_lab_data()

if not df.empty:
    # Sidebar - Batch Selection & Controls
    st.sidebar.markdown("### 🧪 Dashboard Controls")
    all_batches = sorted(df['batch_id'].unique(), reverse=True)
    selected_batch = st.sidebar.selectbox("Select Batch ID", all_batches, key="batch_select")
    
    # Filter data and sort chronologically
    batch_df = df[df['batch_id'] == selected_batch].sort_values('timestamp')
    latest = batch_df.iloc[-1]
    
    # Calculate status for each sensor
    def get_status(value, metric_type):
        if metric_type == "temp":
            if 36.5 <= value <= 37.5:
                return "normal", "🟢"
            elif 36.0 <= value <= 38.0:
                return "warning", "🟡"
            else:
                return "critical", "🔴"
        elif metric_type == "ph":
            if 7.0 <= value <= 7.3:
                return "normal", "🟢"
            elif 6.8 <= value <= 7.5:
                return "warning", "🟡"
            else:
                return "critical", "🔴"
        elif metric_type == "o2":
            if 40 <= value <= 100:
                return "normal", "🟢"
            elif 25 <= value < 40:
                return "warning", "🟡"
            else:
                return "critical", "🔴"
    
    temp_status, temp_light = get_status(latest['temperature'], "temp")
    ph_status, ph_light = get_status(latest['ph'], "ph")
    o2_status, o2_light = get_status(latest['dissolved_oxygen'], "o2")
    
    # --- HEADER SECTION ---
    st.markdown(f"""
        <div class="header-section">
            <h2>🧬 BioReactor Real-Time Monitor</h2>
            <p><b>Batch:</b> {selected_batch} | <b>Start Time:</b> {batch_df.iloc[0]['timestamp']} | <b>Duration:</b> {len(batch_df)} readings | <b>Operator:</b> {latest['operator_id']}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # --- STATUS INDICATOR BAR ---
    col_status1, col_status2, col_status3 = st.columns(3)
    with col_status1:
        st.markdown(f"<p style='text-align:center; font-size:14px;'>{temp_light} <b>Temperature</b></p>", unsafe_allow_html=True)
    with col_status2:
        st.markdown(f"<p style='text-align:center; font-size:14px;'>{ph_light} <b>pH Level</b></p>", unsafe_allow_html=True)
    with col_status3:
        st.markdown(f"<p style='text-align:center; font-size:14px;'>{o2_light} <b>Dissolved O₂</b></p>", unsafe_allow_html=True)
    
    st.divider()
    
    # --- CENTRAL DISPLAY: 3 LARGE METRIC CARDS ---
    col_metric1, col_metric2, col_metric3 = st.columns(3, gap="large")
    
    with col_metric1:
        st.markdown(f"""
            <div class="metric-card status-{temp_status}">
                <div class="metric-label">Temperature</div>
                <div class="metric-value">{latest['temperature']:.1f}°C</div>
                <div style="font-size:11px; color:#888;">Range: 36.5 - 37.5°C</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col_metric2:
        st.markdown(f"""
            <div class="metric-card status-{ph_status}">
                <div class="metric-label">pH Level</div>
                <div class="metric-value">{latest['ph']:.2f}</div>
                <div style="font-size:11px; color:#888;">Range: 7.0 - 7.3</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col_metric3:
        st.markdown(f"""
            <div class="metric-card status-{o2_status}">
                <div class="metric-label">Dissolved Oxygen</div>
                <div class="metric-value">{latest['dissolved_oxygen']:.1f}%</div>
                <div style="font-size:11px; color:#888;">Optimal: 40 - 100%</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # --- TREND CHARTS ---
    st.markdown("### 📊 Sensor Trends")
    
    col_chart1, col_chart2 = st.columns(2)
    
    # Temperature Trend Chart
    with col_chart1:
        fig_temp = px.line(batch_df, x='timestamp', y='temperature',
                          title="Temperature Trend",
                          template="plotly_white",
                          height=350)
        fig_temp.add_hrect(y0=36.5, y1=37.5, fillcolor="green", opacity=0.1, line_width=0)
        fig_temp.add_hline(y=36.0, line_dash="dash", line_color="orange", opacity=0.5)
        fig_temp.add_hline(y=38.0, line_dash="dash", line_color="red", opacity=0.5)
        fig_temp.update_traces(line_color="#2a5298", line_width=2)
        fig_temp.update_layout(hovermode="x unified", showlegend=False, margin=dict(t=30))
        st.plotly_chart(fig_temp, use_container_width=True)
    
    # pH Trend Chart
    with col_chart2:
        fig_ph = px.line(batch_df, x='timestamp', y='ph',
                        title="pH Level Trend",
                        template="plotly_white",
                        height=350)
        fig_ph.add_hrect(y0=7.0, y1=7.3, fillcolor="green", opacity=0.1, line_width=0)
        fig_ph.add_hline(y=6.8, line_dash="dash", line_color="orange", opacity=0.5)
        fig_ph.add_hline(y=7.5, line_dash="dash", line_color="red", opacity=0.5)
        fig_ph.update_traces(line_color="#9b59b6", line_width=2)
        fig_ph.update_layout(hovermode="x unified", showlegend=False, margin=dict(t=30))
        st.plotly_chart(fig_ph, use_container_width=True)
    
    # Dissolved Oxygen Trend Chart (full width)
    fig_o2 = px.line(batch_df, x='timestamp', y='dissolved_oxygen',
                    title="Dissolved Oxygen Trend",
                    template="plotly_white",
                    height=300)
    fig_o2.add_hrect(y0=40, y1=100, fillcolor="green", opacity=0.1, line_width=0)
    fig_o2.add_hline(y=25, line_dash="dash", line_color="orange", opacity=0.5)
    fig_o2.update_traces(line_color="#e67e22", line_width=2)
    fig_o2.update_layout(hovermode="x unified", showlegend=False, margin=dict(t=30))
    st.plotly_chart(fig_o2, use_container_width=True)
    
    st.divider()
    
    # --- ANOMALY & DATA SECTION ---
    col_anomaly, col_data = st.columns([1, 2])
    
    with col_anomaly:
        st.markdown("### ⚠️ Alerts")
        anom_temp = batch_df[batch_df['temperature'] > 38.0].shape[0]
        anom_ph = batch_df[batch_df['ph'] < 6.8].shape[0]
        anom_o2 = batch_df[batch_df['dissolved_oxygen'] < 25].shape[0]
        
        if anom_temp + anom_ph + anom_o2 > 0:
            if anom_temp > 0:
                st.warning(f"🌡️ {anom_temp} critical temperature readings")
            if anom_ph > 0:
                st.warning(f"🧪 {anom_ph} critical pH readings")
            if anom_o2 > 0:
                st.warning(f"💨 {anom_o2} critical oxygen readings")
        else:
            st.success("✅ All sensors within normal range")
    
    with col_data:
        with st.expander("📁 View Complete Batch Data Log"):
            st.dataframe(batch_df, use_container_width=True, height=300)
    
    # --- FOOTER SECTION ---
    now = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    st.markdown(f"""
        <div class="footer-section">
            <p>Last Updated: {now} | Data Points: {len(batch_df)} | Database: {DB_CONFIG['host']}</p>
        </div>
    """, unsafe_allow_html=True)

else:
    st.warning("📭 No data found in RDS. Run your simulator and verify your pipeline!")

# Refresh button at bottom
if st.sidebar.button('🔄 Refresh Dashboard', use_container_width=True):
    st.cache_data.clear()
    st.rerun()