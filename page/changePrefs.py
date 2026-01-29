import streamlit as st
import tomlkit
from tomlkit import comment, document, nl, table
from pathlib import Path
from datetime import datetime
import utils
import re

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

def update_spreadsheet_name():
    input = st.session_state.spreadsheet_name_input
    if utils.check_if_sheet_exists(input):
        st.session_state['toml_dict']['user']['spreadsheet_name'] = input
        st.session_state['file_dirty'] = True
    else:
        st.session_state.spreadsheet_name_input = 'Error! Sheet does not exist!'
        print('\a') # Beep in the terminal
        
def update_allowed_classes():
    input = st.session_state.allowed_classes_input
    
    # Deal with possible inclusion of Test as a class
    raw_class_list = re.split(',\\s*', input)
    if raw_class_list[-1].lower() == 'test':
        class_list = raw_class_list[:-1]
    else:
        class_list = raw_class_list
        
    # Make sure that classes are just 4 numbers
    if any(char.isalpha() for char in class_list):
        st.session_state.allowed_classes_input = 'Error! Class names should be 4 numbers. Separate classes with commas. Test must be last if included.'
        print('\a') # Beep in the terminal
    else:
        class_list = [int(item) for item in input.split(',')]
        st.session_state['toml_dict']['user']['allowed_classes'] = input
        st.session_state['file_dirty'] = True

def update_skip_days():
    input = st.session_state.skip_days_input
    st.session_state['toml_dict']['user']['skip_days'] = input  # Needs input validation
    st.session_state['file_dirty'] = True
    

if 'file_dirty' not in st.session_state:
    st.session_state['file_dirty'] = False

# If the prefs file does not exist, make the default file
prefs_file_path = Path('.streamlit/prefs.toml')
prefs_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure the parent directory exists
if not prefs_file_path.is_file():
    toml_dict = {'user': {
                    'version': '1.0',
                    'late_minutes': 5.0,
                    'start_date': '2026-01-26',
                    'spreadsheet_name': 'Lab Attendance, Spring 2026',
                    'allowed_classes': '2070, 2510, Test',
                    'skip_days': '2070: [], 2510: [2026-02-12, 2026-02-13], Test: []'
                    }
                }
    st.session_state['toml_dict'] = toml_dict
    utils.write_prefs()
    
# Read the prefs file and store values
if 'prefs_initiated' not in st.session_state:
    utils.read_prefs()
    st.session_state['prefs_initiated'] = True

st.markdown("# Alfred Settings")
utils.shared_sidebar()

# Set the tardy minutes
if 'tardy_input' not in st.session_state:
    st.session_state['tardy_input'] = str(st.session_state['toml_dict']['user']['late_minutes'])

st.text_input('Grace period for tardiness in minutes',
                key = 'tardy_input',
                on_change = update_late_minutes)

# Set the start date
if 'start_date_input' not in st.session_state:
    st.session_state['start_date_input'] = st.session_state['toml_dict']['user']['start_date']

st.text_input('Lab start date (Monday of first week of labs)',
                key = 'start_date_input',
                on_change = update_start_date)

# Set the spreadsheet name
if 'spreadsheet_name_input' not in st.session_state:
    st.session_state['spreadsheet_name_input'] = st.session_state['toml_dict']['user']['spreadsheet_name']

st.text_input('Spreadsheet name',
                key = 'spreadsheet_name_input',
                on_change = update_spreadsheet_name)
                
# Set the allowed classes
if 'allowed_classes_input' not in st.session_state:
    st.session_state['allowed_classes_input'] = st.session_state['toml_dict']['user']['allowed_classes']

st.text_input('Allowed classes',
                key = 'allowed_classes_input',
                on_change = update_allowed_classes)
                
# Set the skipped days
if 'skip_days_input' not in st.session_state:
    st.session_state['skip_days_input'] = st.session_state['toml_dict']['user']['skip_days']

st.text_input('skip_days_input',
                key = 'skip_days_input',
                on_change = update_skip_days)

if st.session_state['file_dirty']:
    st.button('Save Preferences',
               key = 'save_prefs',
               on_click = utils.write_prefs)
