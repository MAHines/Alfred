import streamlit as st
import tomlkit
from tomlkit import comment, document, nl, table
from pathlib import Path
from datetime import datetime
import utils

def update_late_minutes():
    input = st.session_state.tardy_input
    if utils.is_float(input):    
        st.session_state['toml_dict']['user']['late_minutes'] = float(input)
        st.session_state['file_dirty'] = True
    else:
        st.session_state.tardy_input = 'Error! Floating point value expected!'
        print('\a') # Beep in the terminal

def update_start_date():
    input = st.session_state.start_date_input
    if utils.is_datetime_format(input, '%Y-%m-%d'):
        st.session_state['toml_dict']['user']['start_date'] = input
        st.session_state['file_dirty'] = True
    else:
        st.session_state.start_date_input = 'Error! Enter date in format 2026-01-15!'
        print('\a') # Beep in the terminal

if 'file_dirty' not in st.session_state:
    st.session_state['file_dirty'] = False

# If the prefs file does not exist, make the default file
prefs_file_path = Path('.streamlit/prefs.toml')
prefs_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure the parent directory exists
if not prefs_file_path.is_file():
    toml_dict = {'user': {
                    'version': '1.0',
                    'late_minutes': 5.0,
                    'start_date': '2026-02-02'}
                }
    st.session_state['toml_dict'] = toml_dict
    utils.write_prefs()
    
# Read the prefs file and store values
if 'prefs_initiated' not in st.session_state:
    utils.read_prefs()
    st.session_state['prefs_initiated'] = True

st.markdown("# Alfred Settings")
utils.shared_sidebar()

if 'tardy_input' not in st.session_state:
    st.session_state['tardy_input'] = str(st.session_state['toml_dict']['user']['late_minutes'])

st.text_input('Grace period for tardiness in minutes',
                key = 'tardy_input',
                on_change = update_late_minutes)

if 'start_date_input' not in st.session_state:
    st.session_state['start_date_input'] = st.session_state['toml_dict']['user']['start_date']

st.text_input('Lab start date (Monday of first week of labs)',
                key = 'start_date_input',
                on_change = update_start_date)

if st.session_state['file_dirty']:
    st.button('Save Preferences',
               key = 'save_prefs',
               on_click = utils.write_prefs)
