import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Seminar Analytics", page_icon="📊", layout="wide")

# ── Custom CSS ──
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .stMetric { background: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #e9ecef; }
    h1 { color: #1a56db; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Seminar Analytics Dashboard")
st.caption("Offline Seminar Performance • 2025-26")

# ── File Upload ──
col1, col2 = st.columns(2)
with col1:
    file1 = st.file_uploader("Upload **Indepth Details (Attendees)**", type=["xlsx", "xls"], key="f1")
with col2:
    file2 = st.file_uploader("Upload **Seminar Report (Based on Attendee)**", type=["xlsx", "xls"], key="f2")

if not file1 or not file2:
    st.info("👆 Please upload both Excel files to begin analysis.")
    st.stop()

# ── Load Data ──
@st.cache_data
def load_attendee_data(file):
    sheets = pd.read_excel(file, sheet_name=None, header=0)
    frames = []
    for name, df in sheets.items():
        expected_cols = ['student_name', 'phone', 'email', 'service_name', 'batch_date',
                         'payment_received', 'total_gst', 'status', 'total_amount', 'total_due']
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        if any(c in df.columns for c in ['student_name', 'studentname']):
            frames.append(df)
    if frames:
        return pd.concat(frames, ignore_index=True)
    return pd.DataFrame()

@st.cache_data
def load_seminar_data(file):
    df = pd.read_excel(file, sheet_name=0, header=1)
    df.columns = df.columns.str.strip()
    return df

attendee_df = load_attendee_data(file1)
seminar_raw = load_seminar_data(file2)

# ── Parse Seminar Data ──
@st.cache_data
def parse_seminar(df):
    col_map = {}
    cols_lower = {c: c.strip().lower().replace('\n', ' ').replace('\r', ' ') for c in df.columns}

    for orig, low in cols_lower.items():
        if 'sr' in low and 'no' in low:
            col_map['sr_no'] = orig
        elif low in ['trainer']:
            col_map['trainer'] = orig
        elif low in ['location']:
            col_map['location'] = orig
        elif 'seminar' in low and 'date' in low:
            col_map['seminar_date'] = orig
        elif 'targeted' == low:
            col_map['targeted'] = orig
        elif 'total' in low and 'attended' in low and 'actual' not in low:
            col_map['total_attended'] = orig
        elif 'actual' in low and 'attended' in low:
            col_map['actual_attended'] = orig
        elif 'targeted' in low and 'attended' in low and '%' in low:
            col_map['targeted_to_attended_pct'] = orig
        elif 'total' in low and 'seat' in low and 'booked' in low:
            col_map['total_seat_booked'] = orig
        elif 'actual' in low and 'expense' in low:
            col_map['actual_expenses'] = orig
        elif 'expected' in low and 'revenue' in low:
            col_map['expected_revenue'] = orig
        elif 'actual' in low and 'revenue' in low and 'total' not in low:
            col_map['actual_revenue'] = orig
        elif 'total' in low and 'revenue' in low:
            col_map['total_revenue'] = orig
        elif 'surplus' in low or 'deficit' in low:
            col_map['surplus_deficit'] = orig
        elif low in ['er to ae', 'er to ae']:
            col_map['er_to_ae'] = orig
        elif low in ['ar to ae']:
            col_map['ar_to_ae'] = orig
        elif 'attended' in low and 'seat' in low and 'booked' in low and '%' in low:
            col_map['attended_to_booked_pct'] = orig
        elif 'morning' in low and 'total' in low:
            col_map['morning_total'] = orig
        elif 'evening' in low and 'total' in low:
            col_map['evening_total'] = orig

    renamed = df.rename(columns={v: k for k, v in col_map.items()})

    # Keep only rows with valid sr_no
    if 'sr_no' in renamed.columns:
        renamed = renamed[pd.to_numeric(renamed['sr_no'], errors='coerce').notna()]

    numeric_cols = ['targeted', 'total_attended', 'actual_attended', 'total_seat_booked',
                    'actual_expenses', 'expected_revenue', 'actual_revenue', 'total_revenue',
                    'surplus_deficit', 'er_to_ae', 'ar_to_ae', 'morning_total', 'evening_total']
    for c in numeric_cols:
        if c in renamed.columns:
            renamed[c] = pd.to_numeric(renamed[c].astype(str).str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)

    return renamed

seminar_df = parse_seminar(seminar_raw)

# ── Parse Attendee Data ──
attendee_df.columns = attendee_df.columns.str.strip().str.lower().str.replace(' ', '_')
for c in ['payment_received', 'total_gst', 'total_amount', 'total_due', 'total_additional_charges']:
    if c in attendee_df.columns:
        attendee_df[c] = pd.to_numeric(attendee_df[c], errors='coerce').fillna(0)

# ── Sidebar Filters ──
st.sidebar.header("🔍 Filters")

# Location filter
locations = sorted(seminar_df['location'].dropna().unique()) if 'location' in seminar_df.columns else []
selected_locations = st.sidebar.multiselect("📍 Location", locations, default=[])

# Trainer filter
if 'trainer' in seminar_df.columns:
    all_trainers = set()
    for t in seminar_df['trainer'].dropna():
        for name in str(t).split(','):
            name = name.strip().split('\n')[0].strip()
            if name:
                all_trainers.add(name)
    all_trainers = sorted(all_trainers)
else:
    all_trainers = []
selected_trainers = st.sidebar.multiselect("👨‍🏫 Trainer", all_trainers, default=[])

# Profit filter
profit_filter = st.sidebar.radio("💰 Profitability", ["All", "Profitable", "Loss-making"], horizontal=True)

# ── Apply Filters ──
filtered = seminar_df.copy()
if selected_locations:
    filtered = filtered[filtered['location'].isin(selected_locations)]
if selected_trainers:
    def has_trainer(trainer_str):
        names = [n.strip().split('\n')[0].strip() for n in str(trainer_str).split(',')]
        return any(n in selected_trainers for n in names)
    filtered = filtered[filtered['trainer'].apply(has_trainer)]
if profit_filter == "Profitable" and 'surplus_deficit' in filtered.columns:
    filtered = filtered[filtered['surplus_deficit'] > 0]
elif profit_filter == "Loss-making" and 'surplus_deficit' in filtered.columns:
    filtered = filtered[filtered['surplus_deficit'] < 0]

# ── KPI Section ──
st.markdown("---")
k1, k2, k3, k4, k5, k6 = st.columns(6)

total_seminars = len(filtered)
total_attended = int(filtered['total_attended'].sum()) if 'total_attended' in filtered.columns else 0
total_revenue = filtered['actual_revenue'].sum() if 'actual_revenue' in filtered.columns else 0
total_expenses = filtered['actual_expenses'].sum() if 'actual_expenses' in filtered.columns else 0
with_exp = filtered[filtered['actual_expenses'] > 0] if 'actual_expenses' in filtered.columns else filtered
profitable_count = int((with_exp['surplus_deficit'] > 0).sum()) if 'surplus_deficit' in with_exp.columns else 0
avg_conversion = 0
if 'attended_to_booked_pct' in filtered.columns:
    avg_conversion = filtered['attended_to_booked_pct'].mean()
elif 'total_seat_booked' in filtered.columns and 'total_attended' in filtered.columns:
    total_att = filtered['total_attended'].sum()
    total_booked = filtered['total_seat_booked'].sum()
    avg_conversion = (total_booked / total_att * 100) if total_att > 0 else 0

k1.metric("📋 Seminars", total_seminars)
k2.metric("👥 Attendees", f"{total_attended:,}")
k3.metric("💰 Revenue", f"₹{total_revenue/100000:.1f}L")
k4.metric("📤 Expenses", f"₹{total_expenses/100000:.1f}L")
k5.metric("🎯 Avg Conversion", f"{avg_conversion:.1f}%")
k6.metric("✅ Profitable", f"{profitable_count}/{len(with_exp)}")

# ── Charts ──
st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Revenue vs Expense", "📈 Surplus/Deficit", "🎯 Attendance Funnel",
    "🥧 Student Status", "📋 Revenue Breakdown"
])

with tab1:
    if 'actual_revenue' in filtered.columns and 'actual_expenses' in filtered.columns:
        chart_data = filtered[filtered['actual_expenses'] > 0][['location', 'actual_revenue', 'actual_expenses']].copy()
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Revenue', x=chart_data['location'], y=chart_data['actual_revenue'], marker_color='#1a56db'))
        fig.add_trace(go.Bar(name='Expense', x=chart_data['location'], y=chart_data['actual_expenses'], marker_color='#f59e0b'))
        fig.update_layout(barmode='group', height=450, xaxis_tickangle=-45,
                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if 'surplus_deficit' in filtered.columns:
        chart_data = filtered[filtered['actual_expenses'] > 0][['location', 'surplus_deficit']].copy()
        colors = ['#10b981' if v >= 0 else '#ef4444' for v in chart_data['surplus_deficit']]
        fig = px.bar(chart_data, x='location', y='surplus_deficit', color_discrete_sequence=['#10b981'])
        fig.update_traces(marker_color=colors)
        fig.update_layout(height=450, xaxis_tickangle=-45,
                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    if all(c in filtered.columns for c in ['targeted', 'total_attended', 'total_seat_booked']):
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Targeted', x=filtered['location'], y=filtered['targeted'], marker_color='#9ca3af', opacity=0.5))
        fig.add_trace(go.Bar(name='Attended', x=filtered['location'], y=filtered['total_attended'], marker_color='#1a56db'))
        fig.add_trace(go.Bar(name='Booked', x=filtered['location'], y=filtered['total_seat_booked'], marker_color='#10b981'))
        fig.update_layout(barmode='group', height=450, xaxis_tickangle=-45,
                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    if 'status' in attendee_df.columns:
        status_counts = attendee_df['status'].value_counts()
        fig = px.pie(values=status_counts.values, names=status_counts.index, hole=0.45,
                     color_discrete_sequence=['#10b981', '#ef4444', '#f59e0b', '#6366f1'])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    if 'service_name' in attendee_df.columns:
        course_rev = attendee_df.groupby('service_name')['payment_received'].sum().sort_values(ascending=False).head(10)
        fig = px.bar(x=course_rev.values, y=course_rev.index, orientation='h',
                     color_discrete_sequence=['#1a56db'])
        fig.update_layout(height=450, yaxis_title='', xaxis_title='Revenue (₹)',
                          plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

# ── Key Insights ──
st.markdown("---")
st.subheader("💡 Key Insights")

if len(with_exp) > 0 and 'surplus_deficit' in with_exp.columns:
    col_a, col_b = st.columns(2)

    best = with_exp.loc[with_exp['surplus_deficit'].idxmax()]
    worst = with_exp.loc[with_exp['surplus_deficit'].idxmin()]

    with col_a:
        st.success(f"**🏆 Best ROI:** {best.get('location', 'N/A')} — Surplus of ₹{int(best.get('surplus_deficit', 0)):,}")
        if 'total_attended' in filtered.columns:
            top_att = filtered.loc[filtered['total_attended'].idxmax()]
            st.info(f"**👥 Highest Attendance:** {top_att.get('location', 'N/A')} — {int(top_att['total_attended']):,} attendees")

    with col_b:
        st.error(f"**⚠️ Worst ROI:** {worst.get('location', 'N/A')} — Deficit of ₹{abs(int(worst.get('surplus_deficit', 0))):,}")
        loss_count = int((with_exp['surplus_deficit'] < 0).sum())
        st.warning(f"**📉 Loss-making seminars:** {loss_count} out of {len(with_exp)} ran at a loss")

# ── Data Table ──
st.markdown("---")
st.subheader("📋 Seminar Performance Data")

display_cols = [c for c in ['sr_no', 'location', 'trainer', 'seminar_date', 'targeted',
                             'total_attended', 'total_seat_booked', 'actual_expenses',
                             'actual_revenue', 'surplus_deficit', 'er_to_ae'] if c in filtered.columns]
st.dataframe(
    filtered[display_cols].reset_index(drop=True),
    use_container_width=True,
    height=400,
    column_config={
        "actual_expenses": st.column_config.NumberColumn("Expenses", format="₹%d"),
        "actual_revenue": st.column_config.NumberColumn("Revenue", format="₹%d"),
        "surplus_deficit": st.column_config.NumberColumn("Surplus/Deficit", format="₹%d"),
    }
)

# ── Attendee Details ──
st.markdown("---")
st.subheader("👤 Attendee Details")

att_display = [c for c in ['student_name', 'phone', 'email', 'service_name', 'batch_date',
                            'payment_received', 'total_gst', 'status', 'total_amount', 'total_due']
               if c in attendee_df.columns]

if 'status' in attendee_df.columns:
    status_filter = st.multiselect("Filter by Status", attendee_df['status'].dropna().unique().tolist())
    display_att = attendee_df[attendee_df['status'].isin(status_filter)] if status_filter else attendee_df
else:
    display_att = attendee_df

st.dataframe(
    display_att[att_display].head(500).reset_index(drop=True),
    use_container_width=True,
    height=400,
    column_config={
        "payment_received": st.column_config.NumberColumn("Payment", format="₹%d"),
        "total_amount": st.column_config.NumberColumn("Total Amt", format="₹%d"),
    }
)

st.caption(f"Showing {min(500, len(display_att))} of {len(display_att)} records")
