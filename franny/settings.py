"""Resolve server settings without exposing values. Secrets overrides stale process env."""
import os

def resolve_setting(name, default=''):
    import streamlit as st
    try:
        if name in st.secrets:
            # Explicitly empty Secrets stay empty: never revive an old environment credential.
            return str(st.secrets[name]), 'Streamlit Secrets'
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass
    value=os.getenv(name)
    if value is not None:
        return value, '服务器环境变量'
    return default, '默认值/未配置'

def setting(name, default=''):
    return resolve_setting(name,default)[0]

def setting_source(name):
    # Only this label may be rendered in the browser, never the resolved value.
    return resolve_setting(name)[1]
