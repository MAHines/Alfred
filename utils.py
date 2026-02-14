import streamlit as st
import pandas as pd
import tomlkit
import os
from tomlkit import comment, document, nl, table
from pathlib import Path
from datetime import datetime
import gspread
from gspread.exceptions import WorksheetNotFound
from oauth2client.service_account import ServiceAccountCredentials
import time
from tenacity import retry, stop_after_attempt, wait_fixed

def read_prefs():

    # If the prefs file does not exist, make the default file
    prefs_file_path = Path(__file__).parent / '.streamlit' / 'prefs.toml'
    prefs_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure the parent directory exists
    if not prefs_file_path.is_file():
        toml_dict = {'user': {
                        'version': '1.0',
                        'late_minutes': 5.0,
                        'start_date': '2026-01-26',
                        'spreadsheet_name': 'Lab Attendance, Spring 2026',
                        'allowed_classes': '2070, 2510, Test',
                        'skip_days': '2070: [], 2510: [2026-02-12, 2026-02-13], Test: [2026-02-12, 2026-02-13]'
                        }
                    }
        st.session_state['toml_dict'] = toml_dict
        write_prefs()
    else:
        with open(prefs_file_path, 'r') as fp:
            config = tomlkit.load(fp)
        
        st.session_state['toml_dict'] = config
            
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
    config['user'].add('spreadsheet_name', toml_dict['user']['spreadsheet_name'])
    config['user']['spreadsheet_name'].trivia.comment = '    # Spreadsheet name'
    config['user'].add('allowed_classes', toml_dict['user']['allowed_classes'])
    config['user']['allowed_classes'].trivia.comment = '    # Allowed classes e.g., 2070, 2510, Test'
    config['user'].add('skip_days', toml_dict['user']['skip_days'])
    config['user']['skip_days'].trivia.comment = '    # Skipped days e.g., 2070: [], 2510: [2026-02-12, 2026-02-13], Test: []'
    config.add(nl())
    
    # Dump the modified configument to a string
    prefs_file_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'prefs.toml')
    with open(prefs_file_path, 'w') as fp:
        fp.write(tomlkit.dumps(config))
    
    st.session_state['file_dirty'] = False

@retry(
    stop=stop_after_attempt(5), # Stop after a maximum of 5 attempts
    wait=wait_fixed(1) 
)
def read_google_sheet_with_retry(sheetName, msg):   # Open Sheet, then read entire sheet with sheetName
    
    message = f'Reading {msg} Google sheet'
    alert = st.warning(message)
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    google_service_account_info = st.secrets['google_service_account']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
    client = gspread.authorize(creds)
    sh = client.open(st.session_state['toml_dict']['user']['spreadsheet_name'])
    
    # Open the appropriate sheet and read it
    data = sh.worksheet(sheetName).get_all_values()
    alert.empty()
    return data
    
def read_roster_sheet():

    # Now open the sheet for the roster and read
    try:
        data = read_google_sheet_with_retry(st.session_state['rosterSheetName'], 'roster')
    except Exception as e:
        st.error(f'Failed after retries (likely wifi issue):: {e}')
        return -1, None
    
    headers = data.pop(0)
    roster_df = pd.DataFrame(data, columns = headers)
    roster_df.drop_duplicates(inplace = True)
    
    # We want to make sure each student is only entered once
    duplicate_mask = roster_df.duplicated(subset=['ID'], keep=False)
    duplicate_rows = roster_df[duplicate_mask]
    
    if len(duplicate_rows) > 0:
        st.write(f'There are {int(len(duplicate_rows)/2)} students in multiple sections. This must be fixed before proceeding')
        st.dataframe(duplicate_rows)
        return -1, duplicate_rows
    
    return 0, roster_df

@retry(
    stop=stop_after_attempt(5), # Stop after a maximum of 5 attempts
    wait=wait_fixed(1) 
)
def append_row_to_google_sheet(spreadsheet_name, spreadsheet_entry):
    
    alert = st.warning('Writing to Alfred Google sheet')
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
    google_service_account_info = st.secrets['google_service_account']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
    client = gspread.authorize(creds)
    sh = client.open(st.session_state['toml_dict']['user']['spreadsheet_name'])
    sheetName = sh.worksheet(spreadsheet_name)    
    sheetName.append_row(spreadsheet_entry) # Actual spreadsheet entry
    alert.empty()

def check_if_sheet_exists(sheet_title):
    """
    Checks if a worksheet with the given title exists in the spreadsheet.

    Returns:
        True if the sheet exists, False otherwise.
    """
    try:
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        google_service_account_info = st.secrets['google_service_account']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(google_service_account_info, scope)
        client = gspread.authorize(creds)
        client.open(sheet_title)
        # print(f"The sheet '{sheet_title}' exists.")
        return True

    except WorksheetNotFound:
        # print(f"The sheet '{sheet_title}' does not exist.")
        return False
    except Exception as e:
        # print(f"An error occurred: {e}")
        return False

    
def shared_sidebar():
    image_path = os.path.join(os.path.dirname(__file__), 'assets', 'Hobbes_glasses.png')
    #unique_image_path = f"{image_path}?{time.time()}"
    st.sidebar.image(image_path)
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
    
