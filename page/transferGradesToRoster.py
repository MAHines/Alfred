import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import numpy as np
from pathlib import Path
import math
from datetime import datetime, timedelta, date, time
import utils
                
def read_finalGrades_xlsx():
    """ Function to read an Excel file containing your letter grades."""

    if ss.finalGrades_key is not None:
        
        # Read the file
        finalGrades_xlsx = pd.ExcelFile(ss.finalGrades_key)
        
        # Store sheet names and df's 
        ss.sheet_names = finalGrades_xlsx.sheet_names
        ss.xlsx_data = {sheet: finalGrades_xlsx.parse(sheet) for sheet in finalGrades_xlsx.sheet_names}
    else:
        ss.pop('sheet_names', None)
        ss.pop('xlsx_data', None)

def read_fcRoster_csv():
    """ Function to read grade roster downloaded from Faculty Center."""
    
    uploaded_files = ss.fcRoster_key
    if uploaded_files:
        df_list = []
        for file in uploaded_files:
            df = pd.read_csv(file)
            df_list.append(df)
        
        ss.fcRoster_df = pd.concat(df_list, ignore_index = True)

def reset_uploaders():
    """Function to clear the uploaded  data and show the uploaders again."""
    ss.xlsx_data = None
    ss.finalGrades_df = None
    ss.fcRoster_df = None
    ss.gradesCopied = False
            
st.title('Transfer Grades to Faculty Center Roster')

# Initialization 
keys = ['finalGrades_xlsx', 'finalGrades_df', 'fcRoster_df', 'xlsx_data']
for key in keys:
    ss.setdefault(key, None)
keys = ['gradesCopied']
for key in keys:
    ss.setdefault(key, False)

st.button("Reset or work on a different course.", 
            on_click=reset_uploaders,
            type = 'primary')

st.write('#### Load Excel .xlsx File with Letter Grades and SIS User IDs')
text_str = 'The letter grades and SIS User IDs should be in separate columns on the same '
text_str += 'sheet in Excel. The file can contain other columns and multiple sheets. '
text_str += 'We try to ignore information below the main table, but make sure there is no '
text_str += 'extra data below your table in the SIS User ID column.' 
st.write(text_str)

# Logic to display the grades file uploader
if ss.xlsx_data is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload final grades .xlsx here.",
        type=['xlsx'],
        accept_multiple_files=False,
        key = 'finalGrades_key',
        on_change = read_finalGrades_xlsx
    )
else:
    st.write('#### :gray[Grades already uploaded.]')
    if 'sheet_names' in ss:
        selected_sheet = st.selectbox('Select the sheet with grades',
                                        options = ss.sheet_names)
                                        
        st.dataframe(ss.xlsx_data[selected_sheet],
                        hide_index = True)
    
        columns_on_selected_sheet = ss.xlsx_data[selected_sheet].columns.tolist()
        selected_grade_column = st.selectbox('Select the column with your letter grades',
                                        options = columns_on_selected_sheet)
        selected_SIS_User_ID_column = st.selectbox('Select the column with CUIDs / SIS User IDs',
                                        options = columns_on_selected_sheet)
                                                
        if st.button('Copy selected columns', type = 'primary'):
            ss.finalGrades_df = ss.xlsx_data[selected_sheet][[selected_SIS_User_ID_column, selected_grade_column]]
            ss.finalGrades_df = ss.finalGrades_df.rename(columns = {selected_SIS_User_ID_column: 'CUID',
                                                                    selected_grade_column: 'Grade'})
            
            # If there is crap below the grades, we may get blank CUIDs or grades. Remove these.
            ss.finalGrades_df = ss.finalGrades_df.dropna(subset=['CUID', 'Grade'])
            
        if ss.finalGrades_df is not None:
            st.write(f'{len(ss.finalGrades_df)} grades to be transfered')
            st.dataframe(ss.finalGrades_df, hide_index = True)

st.write('#### Load Faculty Center Grade Roster(s) (.csv)')
text_str = 'Download your roster(s) from Faculty Center and upload them here. The script will '
text_str += 'take your grades from above and copy them into the \'INPUT ROSTER GRADE\' column. '
text_str += 'The script will alert you if any students have no grade **and** no entry in '
text_str += '\'POSTED OFFICIAL \' (typically a \'W\'). This might happen, for example, if you '
text_str += 'forget to include INCs.'
st.write(text_str)
text_str = '**Note:** If you have multiple rosters for the same course, upload all of them here. Faculty '
text_str += 'Center will happily process the combined roster.'
st.write(text_str)
# Logic to display the Faculty Center roster file uploader
if ss['fcRoster_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Faculty Center grade roster csv(s) here.",
        type=['csv'],
        accept_multiple_files=True,
        key = 'fcRoster_key',
        on_change = read_fcRoster_csv
    )
else:
    st.write('#### :gray[Faculty Center Roster already uploaded.]')
    st.write(f'{len(ss.fcRoster_df)} students in Faculty Center Roster.')
    st.dataframe(ss.fcRoster_df, hide_index = True)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button('Copy grades to roster', type = 'primary'):
            ss.fcRoster_df['INPUT ROSTER GRADE'] = (
                ss.fcRoster_df['STUDENT ID'].map(ss.finalGrades_df.set_index('CUID')['Grade']))
            ss.gradesCopied = True
                
            missing_data_students = ss.fcRoster_df[ss.fcRoster_df['INPUT ROSTER GRADE'].isna() & ss.fcRoster_df['POSTED OFFICIAL GRADE'].isna()]['NAME'].tolist()
            if len(missing_data_students) > 0:
                st.write(f'The following students have no data: {missing_data_students}')
    with col2:
        if ss.gradesCopied:
            fileName = f"All Rosters for Upload_{datetime.now().strftime('%b_%d')}.csv"            
            roster_for_upload = ss.fcRoster_df.to_csv(index = False, header = True).encode('utf-8')
            st.download_button(label = 'Download Roster as csv',
                            data = roster_for_upload,
                            file_name = fileName,
                            mime = 'text/csv',
                            type = 'primary')
    if ss.gradesCopied:
        st.write('The downloaded roster can be found in ~/Downloads/All_Rosters_for_Upload_(date).csv')
               

utils.shared_sidebar()
