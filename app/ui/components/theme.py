"""
Professional theme component for notebook application.

Provides light/dark theme styling with professional color schemes.
"""

import streamlit as st


def apply_professional_theme():
    """Apply professional theme styling."""
    theme = st.session_state.get('theme', 'light')

    if theme == 'dark':
        colors = {
            'bg': '#0E1117',
            'sidebar_bg': '#262730',
            'card_bg': '#1E2130',
            'text': '#FAFAFA',
            'text_muted': '#9CA3AF',
            'border': '#3A3D45',
            'accent': '#4D9EF6',
            'accent_hover': '#3B82F6',
        }
    else:
        colors = {
            'bg': '#FFFFFF',
            'sidebar_bg': '#F0F2F6',
            'card_bg': '#F8F9FA',
            'text': '#262730',
            'text_muted': '#6C757D',
            'border': '#E0E0E0',
            'accent': '#0068C9',
            'accent_hover': '#0056A3',
        }

    st.markdown(f"""
    <style>
        /* Main background */
        .main {{
            background-color: {colors['bg']};
        }}

        /* Sidebar styling */
        section[data-testid="stSidebar"] {{
            background-color: {colors['sidebar_bg']};
        }}

        section[data-testid="stSidebar"] .block-container {{
            padding-top: 2rem;
        }}

        /* Headers */
        .main h1, .main h2, .main h3 {{
            color: {colors['text']};
        }}

        /* Section dividers */
        hr {{
            border-color: {colors['border']};
        }}

        /* Metric cards */
        div[data-testid="stMetricValue"] {{
            font-size: 2.5rem;
            font-weight: 700;
            color: {colors['accent']};
        }}

        div[data-testid="stMetricLabel"] {{
            font-size: 0.9rem;
            color: {colors['text_muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        /* Buttons */
        .stButton > button {{
            border-radius: 0.375rem;
            font-weight: 500;
            transition: all 0.2s;
        }}

        .stButton > button[kind="primary"] {{
            background-color: {colors['accent']};
            border-color: {colors['accent']};
        }}

        .stButton > button[kind="primary"]:hover {{
            background-color: {colors['accent_hover']};
            border-color: {colors['accent_hover']};
        }}

        /* Tab bar styling */
        .tab-container {{
            background-color: {colors['card_bg']};
            padding: 0.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }}

        /* Close button styling for tabs */
        [data-testid="column"] button[kind="secondary"]:has([data-testid="baseButton-secondary"]) {{
            min-width: auto;
        }}

        /* Style close buttons specifically (buttons with single character) */
        button[data-testid="baseButton-secondary"] {{
            padding: 0.25rem 0.5rem;
        }}

        /* Code editor */
        .stCodeBlock {{
            background-color: {colors['card_bg']};
        }}

        /* Hide Streamlit branding */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* Plotly charts background */
        .js-plotly-plot .plotly {{
            background-color: {colors['card_bg']} !important;
        }}
    </style>
    """, unsafe_allow_html=True)
