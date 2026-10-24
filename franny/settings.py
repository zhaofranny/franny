"""Load ordinary deployment settings lazily, without logging secrets."""
import os

def setting(name, default=''):
    value = os.getenv(name)
    if value:
        return value
    import streamlit as st
    try:
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default
