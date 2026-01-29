import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import math
from datetime import datetime, timedelta, date, time
import utils
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import ast
import plotly.express as px


def read_timesheet():

    sh = utils.open_google_sheet()  # Actual code in utils
    
    # Open the appropriate sheet and read the timesheet
    st.session_state['timesheet'] = sh.worksheet(st.session_state['timesheetName'])
    data = st.session_state['timesheet'].get_all_values()
    timesheet_df = pd.DataFrame(data, columns = ['course','TA', 'section','ID','Log time']) # We do not use the course and section columns
    columns_to_drop = ['course', 'section']
    timesheet_df.drop(columns = columns_to_drop, inplace = True)
    timesheet_df['TA'] = timesheet_df['TA'].str.capitalize()    # Fix the capitalization of TA names
    
    # Convert entry time to a datetime and the rest to strings
    timesheet_df['Log time'] = pd.to_datetime(timesheet_df['Log time'], format = '%a, %d %b %y, %I:%M %p')
    timesheet_df.rename(columns = {'section': 'loggedSection'}, inplace = True)
    timesheet_df.rename(columns = {'ID': 'enteredID'}, inplace = True)

    # Take care of "skipped days." For example, if 2/12 and 2/13 were skipped, then those students attended on 2/19 and 2/20,
    #   Therefore, we will 'pretend' 2/19 = 2/12 and 2/20 = 2/13.
    start_key = st.session_state['timesheetName'][-4:] + ':'
    start_marker = st.session_state['toml_dict']['user']['skip_days'].find(start_key) + len(start_key)
    content_start = st.session_state['toml_dict']['user']['skip_days'].find('[', start_marker)
    content_end = st.session_state['toml_dict']['user']['skip_days'].find(']', content_start)
    skip_days_str = st.session_state['toml_dict']['user']['skip_days'][content_start:content_end + 1]
    datetime_skip_days = pd.to_datetime(ast.literal_eval(skip_days_str)).date
    datetime_adv_days = [dt + timedelta(weeks=1) for dt in datetime_skip_days]  # Dates that replaced skipped days
    
    target_dates = datetime_adv_days   # List of dates to target
    mask = timesheet_df['Log time'].dt.date.isin(target_dates)   # Mask of df containing adv dates
    timesheet_df.loc[mask, 'Log time'] -= pd.offsets.DateOffset(weeks = 1)    # Here is where we fake the dates by subtracting a week

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
    timesheet_df['sectionAttended'] = timesheet_df['Log time'].dt.strftime('%a') + ' ' + timesheet_df['Log time'].dt.strftime('%p')
    
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
    timesheet_df['weekNum'] = np.floor((timesheet_df['Log time'] - pd.to_datetime(st.session_state['toml_dict']['user']['start_date'], format = '%Y-%m-%d'))/timedelta(weeks = 1)) # Saves as integer
    timesheet_df['week'] = (pd.to_datetime(st.session_state['toml_dict']['user']['start_date'], format = '%Y-%m-%d') + timesheet_df['weekNum'] * timedelta(weeks = 1)).dt.strftime('%m/%d')
    
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
                                            In = ('Log time', 'min'),
                                            Out = ('Log time', 'max'),
                                            SectionAttended = ('sectionAttended', 'first'),
                                            InWrongSection = ('inWrongSection', 'first')
                                            )
    # If student only clocked in (or out), then In = Out. Fix this by setting out to Nan
    # If df['In'] == df['Out'] is True, assign np.nan, else keep df['Out']
    # wkSummary_df['Out'] = np.where(wkSummary_df['In'] == wkSummary_df['Out'], np.nan, wkSummary_df['Out'])
    # wkSummary_df['Out'] = np.where((wkSummary_df['Out'] - wkSummary_df['In']).dt.total_seconds()/60 < 2.0, pd.NaT, wkSummary_df['Out'])
    condition = (wkSummary_df['Out'] - wkSummary_df['In']).dt.total_seconds() / 60 >= 2.0
    wkSummary_df['Out'] = wkSummary_df['Out'].where(condition, pd.NaT)
    
    # Calculate the time in the lab
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

def produce_section_summary(timesheet_df):
    sectSummary_df = timesheet_df.groupby(['TA','sectionAttended','week','studentName']).agg(
                                            In = ('Log time', 'min'),
                                            Out = ('Log time', 'max'),
                                            ).reset_index()
    sectSummaryLong_df = pd.melt(sectSummary_df,
                                    id_vars = ['TA','sectionAttended','week','studentName'],
                                    value_vars = ['In', 'Out'],
                                    var_name = 'event_type',
                                    value_name = 'time')
    sectSummaryLong_df.sort_values(by='time', inplace = True)
    sectSummaryLong_df['change'] = 0
    sectSummaryLong_df.loc[sectSummaryLong_df['event_type'] == 'In', 'change'] = 1
    sectSummaryLong_df.loc[sectSummaryLong_df['event_type'] == 'Out', 'change'] = -1
    sectSummaryLong_df['numStudents'] = sectSummaryLong_df['change'].cumsum()
    cols_to_drop = ['studentName', 'event_type', 'change']
    sectSummaryLong_df.drop(columns = cols_to_drop, inplace = True)
    return sectSummaryLong_df
    
def dayOffset(section):
    day = section.split()
    match day[0]:
        case 'Mon':
            return 0
        case 'Tue':
            return 1
        case 'Wed':
            return 2
        case 'Thu':
            return 3
        case 'Fri':
            return 4

def prepare_plot(df, TA, section, week):
    plot_df = df[(df['TA'] == TA) & (df['sectionAttended'] == section) & (df['week'] == week)].reset_index()
    split_week = week.split('/')
    startDate = date(2026, int(split_week[0]), int(split_week[1]) + dayOffset(section))
    if 'AM' in section:
        startTime = time(8,00)
        endTime = time(11, 00)
    else:
        startTime = time(13, 25)
        endTime = time(17, 25)
    start_dt = datetime.combine(startDate, startTime)
    end_dt = datetime.combine(startDate, endTime)
    title_str = TA + ' ' + section
    fig = px.line(plot_df,
                    x = 'time',
                    y = 'numStudents',
                    title = title_str
                    )
    fig.add_vline(x=start_dt, 
              line_width=2, line_dash="dash", line_color="red")

    fig.add_vline(x=end_dt, 
              line_width=2, line_dash="dash", line_color="red")
    return fig
    
def runAnalysis():
    timesheet_df = read_timesheet()
    summary_df, shortSummary_df = produce_weekly_summary(timesheet_df)
    sectSummaryLong_df = produce_section_summary(timesheet_df)
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
    
#     st.markdown('## Weekly Summary')
#     st.dataframe(summary_df)
    
#     st.markdown('## Section Summary')
#     st.dataframe(sectSummaryLong_df)
    #df_to_plot = sectSummaryLong_df[sectSummaryLong_df['TA'] == 'Cindy' & sectSummaryLong_df['sectionAttended'] == 'Mon PM' & sectSummaryLong_df['week'] == '01/26']
    
    temp_df = timesheet_df.groupby(['TA','sectionAttended']).agg(
                                    Fake = ('studentName', 'first')).reset_index()
    temp_df.drop(columns = ['Fake'], inplace = True)
    sections_list = temp_df.values.tolist()
    
    for row in sections_list:
        fig = prepare_plot(sectSummaryLong_df, row[0], row[1], '01/26')
        with st.container():
            st.plotly_chart(fig, width ='stretch')
    
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

# Make a list of attendance sheets 
processed_list = [
    f"Chem_{item}" if item.strip().isdigit() else item.strip() 
    for item in re.split(',\\s*', st.session_state['toml_dict']['user']['allowed_classes'])
]
st.session_state['course_select_list'] = processed_list

if 'course_select_box' not in st.session_state:
    st.session_state['course_select_box'] = '_none_'
    
selected_option = st.selectbox(
    'Course to be analyzed', # Label for the dropdown
    st.session_state['course_select_list'],                         # The options to display
    key = 'course_select_box',
    on_change=handle_course_change
)
if st.session_state['needs_update']:
    runAnalysis()
    st.session_state['needs_update'] = False

utils.shared_sidebar()

  

