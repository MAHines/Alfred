# The purpose of this script is to compare the current Canvas roster, as given by the Canvas gradebook,
#   with the current Alfred roster, which is read from the shared Google sheet. The script then adds any
#   new enrollees to the Alfred roster upon request.

# Important distinction: readRoster_df is read from a Google sheet
#                        calcRoster_df, produced by analyzeAttendance, is inferred from the attendance data

import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import utils
import re

def read_Alfred_roster():
    """ Reads the current roster from a shared Google sheet (e.g., Chem_2070_Roster). These data 
            were typically entered by an instructor at the beginning of the course
    
        readRoster_df: ID, netID, studentName, section
    """
    if ss['selected_course'] != 'None selected':
        ss['rosterSheetName'] = ss['selected_course'] + '_Roster'
        ss['sectionsSheetName'] = ss['selected_course'] + '_Sections'
        
        error, readRoster_df = utils.read_roster_sheet()
        if error < 0:
            return -1
    
        error, sections_df = read_sections_sheet()
        if error < 0:
            return -1
            
        ss['sections_df'] = sections_df
        ss['readRoster_df'] = readRoster_df
        ss['cur_roster'] = ss['selected_course']
        ss['last_selected_course'] = ss['selected_course']
    ss['selected_course'] = 'None selected'
    return 0

def read_sections_sheet():
    """ Reads the sectionNumber and section from a shared Google sheet (e.g., Chem_2070_Sections).
    
        sections_df: sectionNumber (e.g., 401), section (e.g., 'Tue PM')
    """

    try:
        data = utils.read_google_sheet_with_retry(ss['sectionsSheetName'], 'sections')
    except Exception as e:
        st.error(f'Failed after retries (likely wifi issue):: {e}')
        return -1, None
    
    headers = data.pop(0)
    sections_df = pd.DataFrame(data, columns = headers)
    
    return 0, sections_df        

def add_new_enrollees():
    new_enrollees_df = ss['new_enrollees_df']
    
    for row in new_enrollees_df.itertuples(index=False):
        utils.append_row_to_google_sheet(ss['rosterSheetName'], list(row))

def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    ss['canvas_df'] = None
    ss['readRoster_df'] = None
    ss['sections_df'] = None
    ss['new_enrollees_df'] = None
    ss['switched_df'] = None
    ss['last_selected_course'] = ss['course_select_list'][0]
    ss['cur_roster'] = ''
    
def update_roster_title_str():
    ss['roster_title_str'] = '# Update ' + ss['cur_roster'].replace("_", " ") + ' Roster'
    rosterTitleContainer.write(ss['roster_title_str'])

# Initialization 
keys = ['canvas_df', 'readRoster_df', 'sections_df', 'new_enrollees_df', 'switched_df']
for key in keys:
    ss.setdefault(key, None)

if 'toml_dict' not in ss:
    utils.read_prefs()
if 'display_ready' not in ss: # Used by analyzeAttendance.py
    ss['display_ready'] = False
if 'cur_roster' not in ss:
    ss['cur_roster'] = ''

utils.init_course_select_list()  # Initiates ss['course_select_list'] and ss['last_selected_course']

rosterTitleContainer = st.container(border = False)

text_str = 'This module compare the current Canvas roster, as given by the Canvas gradebook, '
text_str += 'with the current Alfred roster, which is read from the shared Google sheet. The script '
text_str += 'then adds any new enrollees to the Alfred roster upon request.'
st.write(text_str)

st.button("Work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

if ss['sections_df'] is None: # Note that analyzeAttendance.py does not load this df
    st.selectbox(
        'Course to be updated', # Label for the dropdown
        ss['course_select_list'],                         # The options to display
        index = 0,              # Always start at none selected,
        key = 'selected_course',
        on_change = read_Alfred_roster
    )
    
# Logic to display the Canvas gradebook file uploader
if ss['canvas_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Canvas gradebook here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'canvas_gradebook_key',
        on_change = utils.read_canvas_gradebook_csv
    )
else:
    st.write('### Canvas gradebook already uploaded')

# The actual calculation is performed when all of the df's have been loaded. No other action needed.
if all(v is not None for v in [ss['canvas_df'],ss['readRoster_df']]):
    
    canvas_df = ss['canvas_df']
    sections_df = ss['sections_df']
    readRoster_df = ss['readRoster_df']
    mapSeries_sectionNumber_to_section = sections_df.set_index('sectionNumber')['section']
    canvas_df['section'] = canvas_df['sectionNumber'].astype('string').map(mapSeries_sectionNumber_to_section)
    
    mask = ~canvas_df['ID'].isin(readRoster_df['ID'])
    new_enrollees_df = canvas_df[mask]
    new_enrollees_df = new_enrollees_df.drop(columns = ['sectionNumber'])
    
    st.write('# Newly Enrolled Students')
    st.dataframe(new_enrollees_df)
    ss['new_enrollees_df'] = new_enrollees_df
    if len(new_enrollees_df) > 0:
        st.button('Update Alfred',
                    on_click = add_new_enrollees,
                    type = 'primary')
        
    
    mask = ~readRoster_df['ID'].isin(canvas_df['ID'])
    dropped_df = readRoster_df[mask]
    
    st.write('# Dropped Students')
    st.write('There is no need to remove these students from the Alfred roster or the attendance records.')
    st.dataframe(dropped_df)
    
    merged_df = pd.merge(readRoster_df, canvas_df, on='ID', how='inner', suffixes=('_Alfred', '_cnv'))
    
    # Filter rows where the section values are different
    switched_df = merged_df[merged_df['section_Alfred'] != merged_df['section_cnv']]
    switched_df = switched_df.rename(columns={'section_Alfred': 'oldSection'})
    switched_df = switched_df.drop(columns = ['sectionNumber'])
    switched_df = switched_df.drop(columns=[col for col in switched_df.columns if col.endswith('_Alfred')])
    switched_df.columns = switched_df.columns.str.removesuffix('_cnv')
    switched_df = switched_df[['ID', 'netID', 'studentName', 'section', 'oldSection']]
    st.write('# Switched Sections')
    st.dataframe(switched_df)
    ss['switched_df'] = 'switched_df'
    

# if ss['canvas_df'] is not None:
#     st.write('# Canvas Roster')
#     st.dataframe(ss['canvas_df'])
# 
# if ss['readRoster_df'] is not None:
#     st.write('# Alfred Roster')
#     st.dataframe(ss['readRoster_df'])
#     
# if ss['sections_df'] is not None:
#     st.write('# Sections')
#     st.dataframe(ss['sections_df'])

update_roster_title_str()
utils.shared_sidebar()
