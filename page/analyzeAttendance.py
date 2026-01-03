import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import math
from datetime import datetime, timedelta
import utils
import gspread
from oauth2client.service_account import ServiceAccountCredentials


def read_timesheet():

    sh = utils.open_google_sheet()
    
    # Open the appropriate sheet and read the timesheet
    st.session_state['timesheet'] = sh.worksheet(st.session_state['timesheetName'])
    data = st.session_state['timesheet'].get_all_values()
    timesheet_df = pd.DataFrame(data, columns = ['TA', 'ID', 'Entry time'])

    # Convert entry time to a datetime and the rest to strings
    timesheet_df['Entry time'] = pd.to_datetime(timesheet_df['Entry time'], format = '%a, %d %b %y, %I:%M %p')
    timesheet_df.rename(columns = {'section': 'loggedSection'}, inplace = True)
    timesheet_df.rename(columns = {'ID': 'enteredID'}, inplace = True)

    # Now open the sheet for the roster and read
    st.session_state['rostersheet'] = sh.worksheet(st.session_state['rostersheetName'])
    data = st.session_state['rostersheet'].get_all_values()
    headers = data.pop(0)
    roster_df = pd.DataFrame(data, columns = headers)
    
    # Convert the roster into a mapping series for netID -> ID
    mapSeries_netID_to_ID = roster_df.set_index('netID')['ID']
    mapSeries_ID_to_section = roster_df.set_index('ID')['section']
    mapSeries_ID_to_name = roster_df.set_index('ID')['studentName']
    
    # Calculate sectionAttended from entry time 
    timesheet_df['sectionAttended'] = timesheet_df['Entry time'].dt.strftime('%a') + ' ' + timesheet_df['Entry time'].dt.strftime('%p')
    
    # Process any netID's 
    timesheet_df['actualID'] = timesheet_df['enteredID']    # What if wrong ID?
    mask = timesheet_df['actualID'].isin(mapSeries_netID_to_ID.index)
    timesheet_df.loc[mask, 'actualID'] = timesheet_df.loc[mask, 'actualID'].map(mapSeries_netID_to_ID)
    timesheet_df['existsID'] = timesheet_df['actualID'].isin(roster_df['ID'])
    
    # Now remove any rows where 'existsID' is False
    timesheet_df = timesheet_df[timesheet_df['existsID']]
    
    # Find assigned sections
    timesheet_df['sectionAssigned'] = timesheet_df['actualID'].astype('string').map(mapSeries_ID_to_section)
    
    # Calculate week
    timesheet_df['weekNum'] = np.ceil((timesheet_df['Entry time'] - pd.to_datetime(st.session_state['toml_dict']['user']['start_date'], format = '%Y-%m-%d'))/timedelta(weeks = 1)) # Saves as integer
    timesheet_df['week'] = (pd.to_datetime(st.session_state['toml_dict']['user']['start_date'], format = '%Y-%m-%d') + timesheet_df['weekNum'] * timedelta(weeks = 1)).dt.strftime('%-m/%-d')
    
    # In wrong section
    timesheet_df['inWrongSection'] = timesheet_df['sectionAttended'] != timesheet_df['sectionAssigned']
        
    cols_to_drop = ['existsID']
    timesheet_df.drop(columns = cols_to_drop, inplace = True) 
    
    timesheet_df.rename(columns = {'actualID': 'ID'}, inplace = True)
    timesheet_df['studentName'] = timesheet_df['ID'].astype('string').map(mapSeries_ID_to_name)    

    # Reorder columns
    first_5_cols = ['studentName', 'TA', 'sectionAttended','inWrongSection']
    all_cols = timesheet_df.columns.to_list()
    rem_cols = [col for col in all_cols if col not in first_5_cols]
    new_col_order = first_5_cols + rem_cols
    timesheet_df = timesheet_df[new_col_order]
    
    return timesheet_df

def produce_weekly_summary(timesheet_df):
    wkSummary_df = timesheet_df.groupby(['studentName', 'TA','week']).agg(
                                            In = ('Entry time', 'min'),
                                            Out = ('Entry time', 'max'),
                                            SectionAttended = ('sectionAttended', 'first'),
                                            InWrongSection = ('inWrongSection', 'first')
                                            )
    wkSummary_df['hrsInLab'] = (wkSummary_df['Out'] - wkSummary_df['In'])/timedelta(hours = 1)
    
    # Calculate minutes late and tardiness from entry in section 
    maskAM = wkSummary_df['SectionAttended'].astype(str).str.split().str[1].fillna('') == 'AM'
    maskPM = wkSummary_df['SectionAttended'].astype(str).str.split().str[1].fillna('') == 'PM'
    wkSummary_df.loc[maskAM, 'tardyTime'] = wkSummary_df['In'] - wkSummary_df['In'].dt.normalize() - timedelta(hours = 8)
    wkSummary_df.loc[maskPM, 'tardyTime'] = wkSummary_df['In'] - wkSummary_df['In'].dt.normalize() - timedelta(hours = 13, minutes = 25)
    wkSummary_df['tardyTime'] = (wkSummary_df['tardyTime'].dt.total_seconds()/60.0).clip(lower = 0)
    wkSummary_df['tardy'] = wkSummary_df['tardyTime'] > st.session_state['toml_dict']['user']['late_minutes']
    
    conditions = [
        (wkSummary_df['In'].notnull() == True) & (wkSummary_df['tardy'] == False),
        (wkSummary_df['In'].notnull() == True) & (wkSummary_df['tardy'] == True),
        (wkSummary_df['In'].notnull() == False)]
    values = ['P', 'T', 'A']
    wkSummary_df['Attendance'] = np.select(conditions, values, default = 'Unknown')
    
    summary_df = wkSummary_df.unstack()
    
    shortSummary_df = summary_df
    cols_to_remove = ['In', 'Out', 'tardy']
    shortSummary_df = shortSummary_df.drop(columns = cols_to_remove)
    new_order = ['Attendance', 'tardyTime', 'SectionAttended', 'InWrongSection' , 'hrsInLab']
    shortSummary_df = shortSummary_df[new_order]
    
    return summary_df, shortSummary_df

def runAnalysis():
    timesheet_df = read_timesheet()
    summary_df, shortSummary_df = produce_weekly_summary(timesheet_df)
    shortSummary_df
    
    attendance_cols = shortSummary_df.columns[shortSummary_df.columns.map(lambda x: x[0]) == 'Attendance']
    absences = shortSummary_df[attendance_cols].copy()
    
    absences.columns = absences.columns.droplevel(0)
    
    absences['totAbsences'] = absences.isnull().sum(axis=1)
    
    mask = absences['totAbsences'] > 1
    selectedRows = absences[absences['totAbsences'] > 1]
    
    st.markdown("## Multiple Absences (A > 1)")    
    st.dataframe(selectedRows)
    
    tardyTime_cols = shortSummary_df.columns[shortSummary_df.columns.map(lambda x: x[0]) == 'tardyTime']
    tardies = shortSummary_df[tardyTime_cols].copy()
    
    tardies.columns = tardies.columns.droplevel(0)
    
    mask = tardies > st.session_state['toml_dict']['user']['late_minutes']
    tardies['totalTardies'] = mask.sum(axis=1)
    
    selectedTardyRows = tardies[tardies['totalTardies'] > 1]
    
    st.markdown("## Multiple Tardiness (T > 1)")
    st.dataframe(selectedTardyRows)
    
    # st.markdown('## Weekly Summary')
    # st.dataframe(summary_df)
    
    st.markdown("## Processed Raw Data")
    st.dataframe(timesheet_df)

def handle_course_change():
    st.session_state['timesheetName'] = st.session_state['course_select_box']
    st.session_state['rostersheetName'] = st.session_state['course_select_box'] + '_Roster'
    st.session_state['course_selected'] = True
    st.session_state['needs_update'] = True

if 'course_selected' not in st.session_state:
    st.session_state['course_selected'] = False
if 'needs_update' not in st.session_state:
    st.session_state['needs_update'] = False

st.markdown("# Attendance Report")
utils.read_prefs()

if 'course_select_box' not in st.session_state:
    st.session_state['course_select_box'] = '_none_'
    
selected_option = st.selectbox(
    'Course to be analyzed', # Label for the dropdown
    ['_none_', 'Test'],                         # The options to display
    key = 'course_select_box',
    on_change=handle_course_change
)
if st.session_state['needs_update']:
    runAnalysis()
    st.session_state['needs_update'] = False

utils.shared_sidebar()

  

