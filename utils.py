import streamlit as st
import tomlkit
from tomlkit import comment, document, nl, table
from pathlib import Path
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def read_prefs():
    with open('.streamlit/prefs.toml', 'r') as fp:
        config = tomlkit.load(fp)
    
    st.session_state['toml_dict'] = dict(config)
            
def write_prefs():

    toml_dict = st.session_state['toml_dict']
    
    # Create new TOML document object
    config = document()
    config.add(comment('This is the preferences file for Chem Manager.'))
    config.add(nl())
    
    # Add key-value pairs
    config.add('user', table())
    config['user'].add('version', toml_dict['user']['version'])
    config['user'].add('late_minutes', toml_dict['user']['late_minutes'])
    config['user']['late_minutes'].trivia.comment = '  # If you are later than LATEMINUTES, you are tardy'
    config['user'].add('start_date', toml_dict['user']['start_date'])
    config['user']['start_date'].trivia.comment = '    # Monday of first week of labs'
    config.add(nl())
    
    # Dump the modified configument to a string
    with open('.streamlit/prefs.toml', 'w') as fp:
        fp.write(tomlkit.dumps(config))
    
    st.session_state['file_dirty'] = False

def open_google_sheet():
    
    # Tried to catch gspread exceptions due to bad wifi, but could not do it gracefully
    # Bad wifi just makes the whole interface hang
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    google_service_account_info = st.secrets['google_service_account']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
    client = gspread.authorize(creds)
    return client.open('Card Swipe Shared Sheet')
    
def shared_sidebar():
    st.sidebar.image('assets/Hobbes_glasses.png')
    st.sidebar.write("Melissa.Hines@cornell.edu")

def is_float(input):
    """
    Checks if a string matches a float
    """
    try:
        float(input)
        return True
    except ValueError:
        return False
        
def is_datetime_format(date_string, format_code):
    """
    Checks if a string matches a specific datetime format.
    """
    try:
        # Try to parse the string into a datetime object
        datetime.strptime(date_string, format_code)
        return True
    except ValueError:
        # If a ValueError is raised, the format does not match
        return False
    
