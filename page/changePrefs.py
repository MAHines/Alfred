import streamlit as st
import tomlkit
from tomlkit import comment, document, nl, table
from pathlib import Path
from datetime import datetime
import keyring as kr
import utils
import re
import os
from streamlit import session_state as ss


def update_late_minutes():
    input = ss.tardy_input
    if utils.is_float(input):    
        ss['toml_dict']['user']['late_minutes'] = float(input)
        ss['file_dirty'] = True
    else:
        ss.tardy_input = 'Error! Floating point value expected!'
        print('\a') # Beep in the terminal

# def update_start_date():
#     input = ss.start_date_input
#     if utils.is_datetime_format(input, '%Y-%m-%d'):
#         ss['toml_dict']['user']['start_date'] = input
#         ss['file_dirty'] = True
#     else:
#         ss.start_date_input = 'Error! Enter date in format 2026-01-15!'
#         print('\a') # Beep in the terminal

# def update_spreadsheet_name():
#     input = ss.spreadsheet_name_input
#     if utils.check_if_sheet_exists(input):
#         ss['toml_dict']['user']['spreadsheet_name'] = input
#         ss['file_dirty'] = True
#     else:
#         ss.spreadsheet_name_input = 'Error! Sheet does not exist!'
#         print('\a') # Beep in the terminal
        
# def update_allowed_classes():
#     input = ss.allowed_classes_input
#     
#     # Deal with possible inclusion of Test as a class
#     raw_class_list = re.split(',\\s*', input)
#     if raw_class_list[-1].lower() == 'test':
#         class_list = raw_class_list[:-1]
#     else:
#         class_list = raw_class_list
#         
#     # Make sure that classes are just 4 numbers
#     if any(char.isalpha() for char in class_list):
#         ss.allowed_classes_input = 'Error! Class names should be 4 numbers. Separate classes with commas. Test must be last if included.'
#         print('\a') # Beep in the terminal
#     else:
#         class_list = [int(item) for item in input.split(',')]
#         ss['toml_dict']['user']['allowed_classes'] = input
#         ss['file_dirty'] = True

def update_skip_days():
    input = ss.skip_days_input
    ss['toml_dict']['user']['skip_days'] = input  # Needs input validation
    ss['file_dirty'] = True
    
def update_pct_pearson():
    input = ss.pct_pearson_input
    ss['toml_dict']['user']['pct_pearson'] = input  # Needs input validation
    ss['file_dirty'] = True
    
def update_lab_order():
    input = ss.lab_order_input
    ss['toml_dict']['user']['lab_order'] = input  # Needs input validation
    ss['file_dirty'] = True    

def update_canvas_domain():
    input = ss.canvas_domain_input
    if input.endswith('/'):
        input = input[:-1]
    ss['toml_dict']['user']['canvas_domain'] = input  # Needs input validation
    ss['file_dirty'] = True    

# Store Canvas token in system keyring
def update_canvas_token():
    input = ss.canvas_token_input
    username = os.getlogin()
    kr.set_password('alfred_canvas', username, input)
    ss.canvas_token_input = ''    

if 'toml_dict' not in ss:
    utils.read_prefs()
if 'file_dirty' not in ss:
    ss['file_dirty'] = False

st.markdown("# Alfred Settings")

st.text_input('Enter new/updated Canvas token',
                key = 'canvas_token_input',
                on_change = update_canvas_token)
st.divider() 

# Set the tardy minutes
if 'tardy_input' not in ss:
    ss['tardy_input'] = str(ss['toml_dict']['user']['late_minutes'])

st.text_input('Grace period for tardiness in minutes',
                key = 'tardy_input',
                on_change = update_late_minutes)

# Set the start date    # Now calculated from data
# if 'start_date_input' not in ss:
#     ss['start_date_input'] = ss['toml_dict']['user']['start_date']
# 
# st.text_input('Lab start date (Monday of first week of labs)',
#                 key = 'start_date_input',
#                 on_change = update_start_date)

# Set the spreadsheet name
# if 'spreadsheet_name_input' not in ss:
#     ss['spreadsheet_name_input'] = ss['toml_dict']['user']['spreadsheet_name']
# 
# st.text_input('Spreadsheet name',
#                 key = 'spreadsheet_name_input',
#                 on_change = update_spreadsheet_name)
                
# Set the allowed classes
# if 'allowed_classes_input' not in ss:
#     ss['allowed_classes_input'] = ss['toml_dict']['user']['allowed_classes']
# 
# st.text_input('Allowed classes',
#                 key = 'allowed_classes_input',
#                 on_change = update_allowed_classes)
                
# Set the skipped days
if 'skip_days_input' not in ss:
    ss['skip_days_input'] = ss['toml_dict']['user']['skip_days']

st.text_input('Days skipped in lab (e.g., partial week for Feb break)',
                key = 'skip_days_input',
                on_change = update_skip_days)

# Set the percent of PS grade alloted to Pearson problems
if 'pct_pearson_input' not in ss:
    ss['pct_pearson_input'] = str(ss['toml_dict']['user']['pct_pearson'])

st.text_input('Percentage of PS grade alloted to Pearson problems (e.g., 0.5)',
                key = 'pct_pearson_input',
                on_change = update_pct_pearson) 

# Set the order of the labs
if 'lab_order_input' not in ss:
    ss['lab_order_input'] = str(ss['toml_dict']['user']['lab_order'])

st.text_input('First word of each lab in chronological order e.g., 2070: [\'Density\', …]',
                key = 'lab_order_input',
                on_change = update_lab_order) 

# Set the base URL of Canvas
if 'canvas_domain_input' not in ss:
    ss['canvas_domain_input'] = str(ss['toml_dict']['user']['canvas_domain'])

st.text_input('The base URL of the Canvas instance, including https://',
                key = 'canvas_domain_input',
                on_change = update_canvas_domain) 

if ss['file_dirty']:
    st.button('Save Preferences',
               key = 'save_prefs',
               on_click = utils.write_prefs,
               type = 'primary')

utils.shared_sidebar()
