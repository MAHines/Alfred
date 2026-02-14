import streamlit as st
import pandas as pd
import utils
import re

# The purpose of this script is to compare the current Canvas roster, as given by the gradebook,
#   with the current Alfred roster. The script then adds any new enrollees to the Alfred roster
#   upon request.

def read_Alfred_roster():
    st.session_state['rosterSheetName'] = st.session_state['selected_course'] + '_Roster'
    st.session_state['sectionsSheetName'] = st.session_state['selected_course'] + '_Sections'
    
    error, roster_df = utils.read_roster_sheet()
    if error < 0:
        return -1

    error, sections_df = read_sections_sheet()
    if error < 0:
        return -1
        
    st.session_state['sections_df'] = sections_df
    st.session_state['roster_df'] = roster_df
    st.session_state['roster_read'] = True
    return 0

def read_sections_sheet():

    try:
        data = utils.read_google_sheet_with_retry(st.session_state['sectionsSheetName'], 'sections')
    except Exception as e:
        st.error(f'Failed after retries (likely wifi issue):: {e}')
        return -1, None
    
    headers = data.pop(0)
    sections_df = pd.DataFrame(data, columns = headers)
    
    return 0, sections_df

def read_canvas_gradebook_csv():
    """Callback function to update session state after a file/folder is uploaded. Used to remove file upload input."""
    # Check if a file was actually uploaded in the callback
    if st.session_state['canvas_gradebook_key'] is not None:
  
        # Read in the required columns of canvas csv 
        columns = ["Student", "SIS User ID", "SIS Login ID", "Section"]
        canvas_df = pd.read_csv(st.session_state['canvas_gradebook_key'],
                             dtype=str,
                             skiprows=[1,2],
                             usecols = columns
                             )
        canvas_df = canvas_df[~canvas_df['Student'].str.contains('Student, Test', na=False)]
        canvas_df = canvas_df.rename(columns = {'SIS User ID':'ID', 'Student': 'studentName', 'SIS Login ID': 'netID', 'Section':'allSections'})
        canvas_df = canvas_df[['ID', 'netID', 'studentName', 'allSections']]
        canvas_df['sectionNumber'] = canvas_df['allSections'].str.extract(r'LAB(\d{3})')
        canvas_df.drop(columns=['allSections'], inplace=True)
        st.session_state['gradebook_uploaded'] = True
        st.session_state['canvas_df'] = canvas_df

def add_new_enrollees():
    new_enrollees_df = st.session_state['new_enrollees_df']
    
    for row in new_enrollees_df.itertuples(index=False):
        utils.append_row_to_google_sheet(st.session_state['rosterSheetName'], list(row))

def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    st.session_state['canvas_df'] = None
    st.session_state['roster_df'] = None
    st.session_state['sections_df'] = None
    st.session_state['new_enrollees_df'] = None
    st.session_state['switched_df'] = None
    st.session_state['selected_course'] = None

# Initialization 
if 'canvas_df' not in st.session_state:
    st.session_state['canvas_df'] = None
if 'roster_df' not in st.session_state:
    st.session_state['roster_df'] = None
if 'sections_df' not in st.session_state:
    st.session_state['sections_df'] = None
if 'new_enrollees_df' not in st.session_state:
    st.session_state['new_enrollees_df'] = None
if 'switched_df' not in st.session_state:
    st.session_state['switched_df'] = None
if 'toml_dict' not in st.session_state:
    utils.read_prefs()

st.markdown("# Update Roster")

st.button("Work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

# Make a list of attendance sheets from allowed classes in settings
processed_list = [
    f"Chem_{item}" if item.strip().isdigit() else item.strip() 
    for item in re.split(',\\s*', st.session_state['toml_dict']['user']['allowed_classes'])
]
st.session_state['course_select_list'] = processed_list

if st.session_state['roster_df'] is None:
    st.selectbox(
        'Course to be updated', # Label for the dropdown
        st.session_state['course_select_list'],                         # The options to display
        index = None,
        placeholder = 'Select a course…',
        key = 'selected_course',
        on_change = read_Alfred_roster
    )

# Logic to display the file uploader or the "Analyze a different file/folder" button
if st.session_state['canvas_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Canvas gradebook here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'canvas_gradebook_key',
        on_change = read_canvas_gradebook_csv
    )
    
if all(v is not None for v in [st.session_state['canvas_df'],st.session_state['roster_df'],st.session_state['sections_df']]):
    
    canvas_df = st.session_state['canvas_df']
    sections_df = st.session_state['sections_df']
    roster_df = st.session_state['roster_df']
    mapSeries_sectionNumber_to_section = sections_df.set_index('sectionNumber')['section']
    canvas_df['section'] = canvas_df['sectionNumber'].astype('string').map(mapSeries_sectionNumber_to_section)
    
    mask = ~canvas_df['ID'].isin(roster_df['ID'])
    new_enrollees_df = canvas_df[mask]
    new_enrollees_df = new_enrollees_df.drop(columns = ['sectionNumber'])
    
    st.write('# Newly Enrolled Students')
    st.dataframe(new_enrollees_df)
    st.session_state['new_enrollees_df'] = new_enrollees_df
    if len(new_enrollees_df) > 0:
        st.button('Update Alfred',
                    on_click = add_new_enrollees,
                    type = 'primary')
        
    
    mask = ~roster_df['ID'].isin(canvas_df['ID'])
    dropped_df = roster_df[mask]
    
    st.write('# Dropped Students')
    st.write('There is no need to remove these students from the Alfred roster or the attendance records.')
    st.dataframe(dropped_df)
    
    merged_df = pd.merge(roster_df, canvas_df, on='ID', how='inner', suffixes=('_Alfred', '_cnv'))
    
    # Filter rows where the section values are different
    switched_df = merged_df[merged_df['section_Alfred'] != merged_df['section_cnv']]
    switched_df = switched_df.rename(columns={'section_Alfred': 'oldSection'})
    switched_df = switched_df.drop(columns = ['sectionNumber'])
    switched_df = switched_df.drop(columns=[col for col in switched_df.columns if col.endswith('_Alfred')])
    switched_df.columns = switched_df.columns.str.removesuffix('_cnv')
    switched_df = switched_df[['ID', 'netID', 'studentName', 'section', 'oldSection']]
    st.write('# Switched Sections')
    st.dataframe(switched_df)
    st.session_state['switched_df'] = 'switched_df'
    

# if st.session_state['canvas_df'] is not None:
#     st.write('# Canvas Roster')
#     st.dataframe(st.session_state['canvas_df'])
# 
# if st.session_state['roster_df'] is not None:
#     st.write('# Alfred Roster')
#     st.dataframe(st.session_state['roster_df'])
#     
# if st.session_state['sections_df'] is not None:
#     st.write('# Sections')
#     st.dataframe(st.session_state['sections_df'])

utils.shared_sidebar()
