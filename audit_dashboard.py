"""
Audit Log Dashboard - View pipeline processing history and health metrics.

This dashboard provides visibility into:
- All file processing events
- Success/failure rates
- Data quality metrics
- Processing performance
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# --- DATABASE CONFIG ---
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

# --- PAGE CONFIG ---
st.set_page_config(page_title="Pipeline Audit Monitor", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .header-section {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATA FETCHING ---
@st.cache_data(ttl=30)
def get_audit_logs(days=30):
    """Fetch audit logs from the last N days"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = f"""
            SELECT * FROM lambda_audit_logs 
            WHERE processed_at >= NOW() - INTERVAL '{days} days'
            ORDER BY processed_at DESC
            LIMIT 1000
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_pipeline_health():
    """Get pipeline health metrics"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        query = """
            SELECT * FROM pipeline_health
            LIMIT 30
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

# --- MAIN APP ---
st.markdown("""
    <div class="header-section">
        <h2>📊 Pipeline Audit Monitor</h2>
        <p>Real-time visibility into Lambda data processing events and success metrics</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar filters
st.sidebar.markdown("### 🔍 Filters")
days_filter = st.sidebar.slider("Days to display", 1, 90, 30)
status_filter = st.sidebar.multiselect("Processing Status", ["SUCCESS", "PARTIAL", "FAILED"], default=["SUCCESS", "PARTIAL", "FAILED"])

# Fetch data
audit_df = get_audit_logs(days_filter)
health_df = get_pipeline_health()

if not audit_df.empty:
    # Filter by status
    audit_df_filtered = audit_df[audit_df['processing_status'].isin(status_filter)]
    
    # --- KEY METRICS ROW ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_files = len(audit_df_filtered)
        st.metric("📁 Files Processed", total_files)
    
    with col2:
        total_records = audit_df_filtered['total_rows'].sum()
        st.metric("📊 Total Records", f"{total_records:,}")
    
    with col3:
        success_rate = (audit_df_filtered[audit_df_filtered['processing_status'] == 'SUCCESS'].shape[0] / total_files * 100) if total_files > 0 else 0
        st.metric("✅ Success Rate", f"{success_rate:.1f}%")
    
    with col4:
        total_errors = audit_df_filtered['errors_flagged'].sum()
        st.metric("⚠️ Errors Flagged", f"{total_errors:,}")
    
    st.divider()
    
    # --- CHARTS ---
    col_chart1, col_chart2 = st.columns(2)
    
    # Success rate over time
    with col_chart1:
        if not health_df.empty:
            fig_success = px.line(
                health_df, 
                x='process_date', 
                y='success_rate_percent',
                title="Daily Success Rate Trend",
                labels={"success_rate_percent": "Success Rate (%)", "process_date": "Date"},
                markers=True,
                template="plotly_white"
            )
            fig_success.add_hline(y=95, line_dash="dash", line_color="green", opacity=0.5)
            st.plotly_chart(fig_success, use_container_width=True)
    
    # Records processed over time
    with col_chart2:
        if not health_df.empty:
            fig_records = px.bar(
                health_df,
                x='process_date',
                y=['records_inserted', 'records_skipped'],
                title="Daily Records: Inserted vs Skipped",
                labels={"value": "Record Count", "process_date": "Date"},
                template="plotly_white",
                barmode='stack'
            )
            st.plotly_chart(fig_records, use_container_width=True)
    
    st.divider()
    
    # --- DETAILED AUDIT LOG TABLE ---
    st.markdown("### 📋 Processing History")
    
    # Display table with status indicators
    display_cols = ['processed_at', 'file_name', 'total_rows', 'rows_inserted', 'rows_skipped', 'errors_flagged', 'processing_status', 'processing_duration_seconds']
    if all(col in audit_df_filtered.columns for col in display_cols):
        table_df = audit_df_filtered[display_cols].copy()
        table_df.columns = ['Processed At', 'File Name', 'Total Rows', 'Inserted', 'Skipped', 'Errors', 'Status', 'Duration (s)']
        st.dataframe(table_df, use_container_width=True, height=400)
    
    # --- ERROR LOGS ---
    if audit_df_filtered[audit_df_filtered['error_message'].notna()].shape[0] > 0:
        st.divider()
        st.markdown("### ❌ Error Details")
        errors_df = audit_df_filtered[audit_df_filtered['error_message'].notna()][['processed_at', 'file_name', 'error_message']]
        for idx, row in errors_df.iterrows():
            with st.expander(f"🔴 {row['file_name']} - {row['processed_at']}"):
                st.error(row['error_message'])

else:
    st.warning("No audit logs found. Run your pipeline to generate logs.")

if st.sidebar.button('🔄 Refresh Data'):
    st.cache_data.clear()
    st.rerun()
