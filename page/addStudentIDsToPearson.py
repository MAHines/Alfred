# This script adds student IDs pulled from the current Canvas
#   gradebook to the Pearson roster. To find the Pearson roster, go to the Instructor Tools
#   page of Pearson, click on 'Student IDs & Groups', the click on 'Export/Import Roster Details'
#   at the top of the next page. This opens a window. Click on 'Export'

import streamlit as st
import pandas as pd
import numpy as np
import utils
import re

def read_pearson_roster_csv():
    """ Reads the Pearson roster from a csv downloaded as described above. Skips to
        the first row starting with 'Name'
    
        pearson_roster_df: Name, Student ID, Groups, Export/Import ID
    """

    if st.session_state['pearson_roster_key'] is not None:
  
        # Read in the required columns of canvas csv 
        pearson_roster_df = read_csv_from_marker(st.session_state['pearson_roster_key'],
                                 'Name')
        pearson_roster_df.dropna(how='all', inplace=True)   # Remove completely blank lines
        st.session_state['pearson_roster_df'] = pearson_roster_df
        
#     st.markdown('## Pearson_roster_df')
#     st.dataframe(pearson_roster_df)

def read_csv_from_marker(uploaded_file, marker):
    """Skips lines until the marker string is found."""
    uploaded_file.seek(0)
    
    skip = 0
    for i, line in enumerate(uploaded_file):
        # Decode bytes to string for comparison if necessary
        if marker in line.decode('utf-8'): 
            skip = i
            break
            
    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file,
                        dtype=str,
                        skiprows=skip)
    return df

def check_string_is_netID(s):
    """
    Checks if a string starts with 2 or 3 alphanumeric characters 
    (a-z, A-Z) followed by an integer.
    """
    # The regex pattern is:
    # ^      - start of the string
    # [a-zA-Z]{2,3} - exactly 2 or 3 alphanumeric characters
    # \d+    - one or more digits (integer part)
    # $ no more characters
    pattern = r'^[a-zA-Z]{2,3}\d+$'
    
    if re.match(pattern, s):
        return True
    else:
        return False

def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    st.session_state['canvas_df'] = None
    st.session_state['pearson_roster_df'] = None

# Initialization 
if 'canvas_df' not in st.session_state:
    st.session_state['canvas_df'] = None
if 'pearson_roster_df' not in st.session_state:
    st.session_state['pearson_roster_df'] = None


st.markdown('## Add Student IDs to Pearson')

info_str = 'To find the Pearson roster, go to the Instructor Tools page of Pearson, '
info_str += 'click on Student IDs & Groups, the click on Export/Import Roster Details '
info_str += 'at the top of the next page. This opens a window. Click on Export to download '
info_str += 'the Pearson roster. Upload the roster and a recent Canvas gradebook below. '
info_str += 'You will receive more instructions after the calculation.'
st.write(info_str)

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

# Logic to display the Pearson roster file uploader
if st.session_state['pearson_roster_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Pearson roster here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'pearson_roster_key',
        on_change = read_pearson_roster_csv
    )

# Logic to display the Canvas gradebook file uploader
if st.session_state['canvas_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Canvas gradebook here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'canvas_gradebook_key',
        on_change = utils.read_canvas_gradebook_csv
    )
    
if all(v is not None for v in [st.session_state['canvas_df'],st.session_state['pearson_roster_df']]):

    canvas_df = st.session_state['canvas_df']
    modPearson_df = st.session_state['pearson_roster_df'].copy()
    mapSeries_name_to_ID = canvas_df.set_index('studentName')['ID']
    mapSeries_netID_to_ID = canvas_df.set_index('netID')['ID']
    
    # Get rid of 0's in the Student ID column
    modPearson_df['Student ID'] = modPearson_df['Student ID'].replace('0', np.nan)
    
    modPearson_df['CUIDname'] = modPearson_df['Name'].map(mapSeries_name_to_ID)
    
    # Try to infer netID
    modPearson_df['Export/Import ID'] = modPearson_df['Export/Import ID'].replace(np.nan, '').astype(str)
    mask = modPearson_df['Export/Import ID'].str.contains('@', na=False)
    modPearson_df.loc[mask, 'netID'] = modPearson_df.loc[mask, 'Export/Import ID'].str.split('@').str[0]
    mask = modPearson_df['Export/Import ID'].apply(check_string_is_netID)
    modPearson_df.loc[mask, 'netID'] = modPearson_df['Export/Import ID']
    
    # Now use inferred netID to fill in CUIDnetid
    modPearson_df['CUIDnetid'] = modPearson_df['netID'].map(mapSeries_netID_to_ID)
    
    # Make a note of any cases where the CUID calculated from the name is not the same as 
    #   the CUID calculated from the netID. This could happen, for example, with identically
    #   named students
    conflict1_df = modPearson_df[
                        (modPearson_df['CUIDnetid'] != modPearson_df['CUIDname']) & 
                        (modPearson_df['CUIDnetid'].notna()) & 
                        (modPearson_df['CUIDname'].notna())]
                        
    # Use the value from the name if there is no value from netID
    modPearson_df['CUIDnetid'] = modPearson_df['CUIDnetid'].fillna(modPearson_df['CUIDname'])
    
    # Tidy up
    modPearson_df.rename(columns={'CUIDnetid': 'CUID'}, inplace=True)
    cols_to_remove = ['CUIDname', 'netID']
    modPearson_df = modPearson_df.drop(columns=cols_to_remove)
    
    # Make a note of any cases where the calculated CUID is not equal to the currently entered Student ID
    conflict2_df = modPearson_df[
                        modPearson_df['Student ID'].notna() &
                        (modPearson_df['Student ID'] != modPearson_df['CUID'])]
                        
    # If conflicts have been found, alert the user
    if len(conflict1_df) + len(conflict2_df) > 0:
        st.markdown('## Conflicts')
        info_str = 'Any entries in the following two tables should be carefully examined, '
        info_str += 'because the CUID calculated in different ways gives different results. '
        info_str += 'This could happen if two students had the same name, for example.'
        st.write(info_str)
        st.dataframe(conflict1_df)
        st.dataframe(conflict2_df)
    
    # If two students have the same CUID, alert the user
    duplicate_CUIDs_df = modPearson_df[modPearson_df['CUID'].duplicated(keep=False) & modPearson_df['CUID'].notna()]
    if len(duplicate_CUIDs_df) > 0:
        st.markdown('## Duplicates')
        info_str = 'Students in this list have identical CUIDs, which should not happen. This may be '
        info_str = 'due to students having the same name. This needs to be fixed.'
        st.write(info_str)
        st.dataframe(duplicate_CUIDs_df)
    
    # If a "student" does not have a CUID, alert the user
    missing_CUID_df = modPearson_df[modPearson_df['CUID'].isnull()]
    if len(missing_CUID_df) > 0:
        st.markdown('## Missing Info')
        info_str = 'People with missing CUID information may be a TA/undergrad TA, or they may have dropped the course. It would '
        info_str += 'be smart to double check that the script did not miss a modified name.'
        st.write(info_str)
        st.dataframe(missing_CUID_df)

    # Present the results and a button for downloading a csv
    st.markdown('## Extracted Cornell IDs')
    info_str = 'Use the button to download the table below. Open the csv, then copy the CUID column into the Student ID column in '
    info_str += 'the original Pearson csv, and upload to Pearson.'
    st.write(info_str)
    st.dataframe(modPearson_df)
    
    roster_data = modPearson_df.to_csv(index = False, header = True).encode('utf-8')
    st.download_button(label = 'Download IDs',
                    data = roster_data,
                    file_name = 'Cornell IDs.csv',
                    mime = 'text/csv',
                    type = 'primary')



