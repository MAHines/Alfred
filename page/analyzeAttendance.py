# The purpose of this script is to calculate student attendance from the in/out timesheet in
#   a shared Google sheet. The script also requires the class roster, again from the shared
#   Google sheet to translate netIDs to CUIDs. The script produces a calculated roster (calcRoster_df)
#   which is based on actual student attendance patterns (i.e., which section a student actually
#   attends.

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
import plotly.graph_objects as go

def read_timesheet():
    """ Read the in/out timesheet from the shared Google doc. Produce timesheet_df, calcRoster_df, and enrollment_df.
    
        calcRoster_df: studentName, ID, netID, TA, and sectionAssigned
        enrollment_df: TA, sectionAssigned, Count
        timesheet_df: studentName, TA, sectionAttended, inWrongSection, dayTA, enteredID, Log time, ID, sectionAssigned, weekNum, week
        
        TA = assigned TA; dayTA = the TA in the section attended on a particular day
         """

    try:
        data = utils.read_google_sheet_with_retry(st.session_state['timesheetName'], 'attendance')
    except Exception as e:
        st.error(f'Failed after retries (likely wifi issue): {e}')
        return(-1, None, None, None)
        
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
    date_strings = skip_days_str.strip('[]').replace(' ', '').split(',')
    datetime_skip_days = [pd.to_datetime(date_str).date() for date_str in date_strings]
    datetime_adv_days = [dt + timedelta(weeks=1) for dt in datetime_skip_days]  # Dates that replaced skipped days
    
    target_dates = datetime_adv_days   # List of dates to target
    mask = timesheet_df['Log time'].dt.date.isin(target_dates)   # Mask of df containing adv dates
    timesheet_df.loc[mask, 'Log time'] -= pd.offsets.DateOffset(weeks = 1)    # Here is where we fake the dates by subtracting a week

    error, readRoster_df = utils.read_roster_sheet()
    if error < 0:
        return -1, readRoster_df
    
    # Convert the readRoster into a mapping series for netID -> ID
    mapSeries_netID_to_ID = readRoster_df.set_index('netID')['ID']
    mapSeries_ID_to_netID = readRoster_df.set_index('ID')['netID']
    mapSeries_ID_to_section = readRoster_df.set_index('ID')['section']
    mapSeries_ID_to_name = readRoster_df.set_index('ID')['studentName']
    
    # Calculate sectionAttended from entry time 
    timesheet_df['sectionAttended'] = timesheet_df['Log time'].dt.strftime('%a') + ' ' + timesheet_df['Log time'].dt.strftime('%p')
    
    # Process any netID's 
    timesheet_df['actualID'] = timesheet_df['enteredID']    # What if wrong ID?
    mask = timesheet_df['actualID'].isin(mapSeries_netID_to_ID.index)
    timesheet_df.loc[mask, 'actualID'] = timesheet_df.loc[mask, 'actualID'].map(mapSeries_netID_to_ID)
    timesheet_df['existsID'] = timesheet_df['actualID'].isin(readRoster_df['ID'])
    
    # Now remove any rows where 'existsID' is False
    unknown_df = timesheet_df[~timesheet_df['existsID']]
    st.session_state['unknown_df'] = unknown_df
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
    
    # Clean up multiple swipes
    timesheet_df['time since last'] = timesheet_df.groupby('ID')['Log time'].diff().dt.total_seconds()/60
    timesheet_df['Remove'] = False
    timesheet_df.loc[timesheet_df['time since last'] < 5.0, 'Remove'] = True
    timesheet_df.sort_values(by=['TA','sectionAttended','Log time'], inplace = True)
    rows_to_drop = timesheet_df[timesheet_df['Remove']].index
    timesheet_df.drop(rows_to_drop, inplace=True)
    cols_to_drop = ['Remove', 'time since last']
    timesheet_df.drop(cols_to_drop, axis = 1, inplace = True)

    # Infer actual TA to create a calculated roster
    timesheet_df.rename(columns = {'TA': 'dayTA'}, inplace = True)
    timesheet_df['TA'] = pd.NA
    calcRoster_df = timesheet_df.groupby(['studentName', 'ID','sectionAssigned', 'inWrongSection','week']).agg(
                                        dayTA = ('dayTA', 'first'),
                                        sectionAttended = ('sectionAttended', 'first')
                                        )
    calcRoster_df = calcRoster_df.unstack().reset_index()
    calcRoster_df = calcRoster_df[calcRoster_df['inWrongSection'] == False]    # Remove students in wrong section
    temp_filtered = calcRoster_df.loc[:, ('dayTA', slice(None))]
    temp_filtered.columns = temp_filtered.columns.get_level_values(1)
    calcRoster_df['TA'] = temp_filtered.apply(find_most_common, axis=1)
    keep_cols = ['studentName', 'ID','TA', 'sectionAssigned']
    calcRoster_df = calcRoster_df[keep_cols]
    calcRoster_df['netID'] = calcRoster_df['ID'].map(mapSeries_ID_to_netID)
    calcRoster_df.columns = calcRoster_df.columns.get_level_values(0)

    # Now set the actual TA in the timesheet
    mapSeries_ID_to_TA = calcRoster_df.set_index('ID')['TA']
    timesheet_df['TA'] = timesheet_df['ID'].map(mapSeries_ID_to_TA)
    
    # Calculate enrollment
    enrollment_df = calcRoster_df.groupby(['TA', 'sectionAssigned']).agg(                     # Count unique students
                                       Count = ('studentName', 'nunique'))
                                       
    # At this stage, calcRoster_df does not contain any students who have not attended their correct section at least once
    #   so we need to recalculate
    calcRoster_df = timesheet_df[['studentName', 'ID','TA', 'sectionAssigned']].copy()
    calcRoster_df.drop_duplicates(inplace = True)
    calcRoster_df['netID'] = calcRoster_df['ID'].map(mapSeries_ID_to_netID)
    calcRoster_df = calcRoster_df[['studentName', 'ID','netID','TA', 'sectionAssigned']]
    calcRoster_df = calcRoster_df.set_index('studentName', drop = True)
    calcRoster_df = calcRoster_df.sort_index(ascending=True)

    # Reorder columns
    first_5_cols = ['studentName', 'TA', 'sectionAttended','inWrongSection']
    all_cols = timesheet_df.columns.to_list()
    rem_cols = [col for col in all_cols if col not in first_5_cols]
    new_col_order = first_5_cols + rem_cols
    timesheet_df = timesheet_df[new_col_order]
    
#     st.markdown('## Roster & Timesheet_df')
#     st.dataframe(calcRoster_df)
#     st.dataframe(enrollment_df)
#     st.dataframe(timesheet_df)
   
    return 0, timesheet_df, calcRoster_df, enrollment_df

def find_most_common(row):
    return row.mode()[0]

def produce_summary(timesheet_df):
    """ Summarizes the data in timesheet_df, which was produced by readTimesheet()
    
        weeklySummary_df summarizes each student's activity in a particular week. There is
            one row of data for every week attended
        weeklySummary_df: studentName, ID, TA, week, In, Out, sectionAssigned, InWrongSection, dayTA,
            hrsInLab, tardyTime, tardy, Attendance
        
        shortSummary_df is the actual dataframe shown to the user. Each row summarizes the attendance
            history of one student.
        shortSummary_df: (indices) studentName, TA
                         (MultiIndex by week) Attendance, tardyTime, sectionAttended, InWrongSection, hrsInLab 
         """
    wkSummary_df = timesheet_df.groupby(['studentName', 'ID','TA','week'], dropna=False).agg( 
                                            In = ('Log time', 'min'),
                                            Out = ('Log time', 'max'),
                                            sectionAttended = ('sectionAttended', 'first'),
                                            InWrongSection = ('inWrongSection', 'first'),
                                            dayTA = ('dayTA', 'first')
                                            )
    # If student only clocked in (or out), then In = Out. Fix this by setting out to Nan
    # If df['In'] == df['Out'] is True, assign np.nan, else keep df['Out']
    condition = (wkSummary_df['Out'] - wkSummary_df['In']).dt.total_seconds() / 60 >= 5.0
    wkSummary_df['Out'] = wkSummary_df['Out'].where(condition, pd.NaT)
    
    # Calculate the time in the lab
    wkSummary_df['hrsInLab'] = (wkSummary_df['Out'] - wkSummary_df['In'])/timedelta(hours = 1)
    
    # Calculate minutes late and tardiness from entry in section 
    maskAM = wkSummary_df['sectionAttended'].astype(str).str.split().str[1].fillna('') == 'AM'
    maskPM = wkSummary_df['sectionAttended'].astype(str).str.split().str[1].fillna('') == 'PM'
    wkSummary_df.loc[maskAM, 'tardyTime'] = wkSummary_df['In'] - wkSummary_df['In'].dt.normalize() - timedelta(hours = 8)
    wkSummary_df.loc[maskPM, 'tardyTime'] = wkSummary_df['In'] - wkSummary_df['In'].dt.normalize() - timedelta(hours = 13, minutes = 25)
    wkSummary_df['tardyTime'] = (wkSummary_df['tardyTime'].dt.total_seconds()/60.0).clip(lower = 0)
    wkSummary_df['tardy'] = wkSummary_df['tardyTime'] > st.session_state['toml_dict']['user']['late_minutes']
    
    conditions = [
        (wkSummary_df['In'].notnull() == True) & (wkSummary_df['tardy'] == False),
        (wkSummary_df['In'].notnull() == True) & (wkSummary_df['tardy'] == True),
        (wkSummary_df['In'].notnull() == False)]    # Absent people will not have an entry in this df
    values = ['P', 'T', 'A']
    wkSummary_df['Attendance'] = np.select(conditions, values, default = 'Unknown')    
    
    shortSummary_df = wkSummary_df.unstack()
    
    # Need to add absences to the shortSummary_df. First add them for previous weeks
    weeks = timesheet_df['week'].unique().tolist()
    thisWeek = weeks[-1]
    completeWeeks = weeks[:-1]
    for week in completeWeeks:
        column = ('Attendance', week)
        shortSummary_df[column] = shortSummary_df[column].fillna('A')
        
    # Look up each student's assigned section
    shortSummary_df['ID'] = shortSummary_df.index.get_level_values(1)   # Kludge to get ID from index
    calcRoster_df = st.session_state['calcRoster_df']
    mapSeries_ID_to_section = calcRoster_df.set_index('ID')['sectionAssigned']
    shortSummary_df['sect'] = shortSummary_df['ID'].map(mapSeries_ID_to_section)
    
    # Make a list of all of the sections from this week that have finished
    sections = calcRoster_df['sectionAssigned'].unique().tolist()
    currentTime = datetime.now()
    pastSections = [s for s in sections if sectionDateTimes(s, thisWeek, 3) < currentTime]
        
    # Now mark students absent this week if their section is already finished
    attendCol = ('Attendance', thisWeek)
    mask = (shortSummary_df['sect'].isin(pastSections)) & (shortSummary_df[attendCol].isna())
    shortSummary_df.loc[mask, attendCol] = 'A'
    
    cols_to_remove = ['In', 'Out', 'tardy']
    shortSummary_df = shortSummary_df.drop(columns = cols_to_remove)
    # new_order = ['Attendance', 'tardyTime', 'sectionAttended', 'InWrongSection' , 'hrsInLab', 'dayTA']
    new_order = ['Attendance', 'tardyTime', 'sectionAttended', 'InWrongSection' , 'hrsInLab']
    shortSummary_df = shortSummary_df[new_order]
    shortSummary_df = shortSummary_df.droplevel(1)

#     st.markdown('## Weekly Summary')
#     st.dataframe(wkSummary_df)
#     st.markdown('## Short Summary')
#     st.dataframe(shortSummary_df)
    
    return wkSummary_df, shortSummary_df

def produce_section_summary(wkSummary_df):
    """ Produces sectSummaryLong_df which summarizes the weekly attendance in each section
    
        sectSummaryLong_df: dayTA, sectionAttended, week, time, numStudents
        time appears to be the time at which the first student swiped in
    """

    temp = wkSummary_df.reset_index()
    cols_to_remove = ['TA','InWrongSection', 'hrsInLab', 'tardyTime', 'tardy','Attendance']
    temp.drop(columns = cols_to_remove, inplace = True)
    
    new_order = ['dayTA','sectionAttended','week','studentName', 'In', 'Out']
    temp = temp.reindex(columns = new_order)
    
    sectSummaryLong_df = pd.melt(temp,
                                id_vars = ['dayTA','sectionAttended','week','studentName'],
                                value_vars = ['In', 'Out'],
                                var_name = 'event_type',
                                value_name = 'time')

    sectSummaryLong_df.sort_values(by=['dayTA','sectionAttended','week','time'], inplace = True)
    sectSummaryLong_df['change'] = 0
    sectSummaryLong_df.loc[sectSummaryLong_df['event_type'] == 'In', 'change'] = 1
    sectSummaryLong_df.loc[sectSummaryLong_df['event_type'] == 'Out', 'change'] = -1
    sectSummaryLong_df['numStudents'] = sectSummaryLong_df['change'].cumsum()
    
    cols_to_drop = ['studentName', 'event_type', 'change']
    sectSummaryLong_df.drop(columns = cols_to_drop, inplace = True)

#     st.markdown('## sectSummaryLong_df')
#     st.dataframe(sectSummaryLong_df)

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
            
def sectionDateTimes(section, week, addHrs):

    # Find date, start and end times
    split_week = week.split('/')
    theDate = date(2026, int(split_week[0]), int(split_week[1]) + dayOffset(section))
    if 'AM' in section:
        theTime = time(8, 00)
    else:
        theTime = time(13, 25)
    the_dt = datetime.combine(theDate, theTime) + timedelta(hours = addHrs)
    
    return the_dt

def prepare_plot(df, TA, section, week, enroll_df):
    
    """ Produces a plot of students vs time for a specific section """
    plot_df = df[(df['dayTA'] == TA) & (df['sectionAttended'] == section) & (df['week'] == week)].reset_index()
    
    # Get enrollment of section
    result_series = enroll_df.loc[(enroll_df['TA'] == TA) & (enroll_df['sectionAssigned'] == section), 'Count']
    enrollment = result_series.values[0] if not result_series.empty else 0
    
    start_dt = sectionDateTimes(section, week, 0)
    end_dt = sectionDateTimes(section, week, 3.0)
    
    title_str = TA + ' ' + section
    fig = go.Figure()
    fig.layout.title = title_str
    
    x_line = [start_dt, start_dt, end_dt, end_dt]   # Add line for Enrolled
    y_line = [0, enrollment, enrollment, 0]
    fig.add_trace(go.Scatter(
                    x = x_line,
                    y = y_line,
                    mode = 'lines',
                    name = 'Enrolled'
                    ))
    
    fig.add_trace(go.Scatter(                       # Add line for Attended
                    x = plot_df['time'],
                    y = plot_df['numStudents'],
                    mode='lines',
                    line_shape = 'hv',
                    name = 'Attended'
                    ))
                    
    return fig
    
def runAnalysis():
    """ Performs the actual analysis of the timesheet """
    error, timesheet_df, calcRoster_df, enrollment_df = read_timesheet()
    if error < 0:
        return error
    st.session_state['timesheet_df'] = timesheet_df
    st.session_state['calcRoster_df'] = calcRoster_df
    enrollment_df = enrollment_df.reset_index()
    st.session_state['enrollment_df'] = enrollment_df

    wkSummary_df, shortSummary_df = produce_summary(timesheet_df)
    st.session_state['shortSummary_df'] = shortSummary_df
    
    sectSummaryLong_df = produce_section_summary(wkSummary_df)
    st.session_state['sectSummaryLong_df'] = sectSummaryLong_df
    
    attendance_cols = shortSummary_df.columns[shortSummary_df.columns.map(lambda x: x[0]) == 'Attendance']
    absences_df = shortSummary_df[attendance_cols].copy()
    absences_df.columns = absences_df.columns.droplevel(0)
    
    mask = absences_df == 'A'
    absences_df['totAbsences'] = mask.sum(axis = 1)
        
    tardyTime_cols = shortSummary_df.columns[shortSummary_df.columns.map(lambda x: x[0]) == 'tardyTime']
    tardies_df = shortSummary_df[tardyTime_cols].copy()
    tardies_df.columns = tardies_df.columns.droplevel(0)
    
    mask = tardies_df > st.session_state['toml_dict']['user']['late_minutes']
    tardies_df['totalTardies'] = mask.sum(axis=1)

    st.session_state['absences_df'] = absences_df
    st.session_state['tardies_df'] = tardies_df   
    
    return 0 
        
#     st.markdown('## Enrollment')
#     st.dataframe(enrollment_df)

#     st.markdown('## Weekly Summary')
#     st.dataframe(wkSummary_df)
    
#     st.markdown('## Section Summary')
#     st.dataframe(sectSummaryLong_df)

def handle_course_change():
    if st.session_state['selected_course'] == 'None selected':
        st.write('st.session_state[selected_course] == None selected called unexpectedly')
        st.session_state['analysis_needs_update'] = False
        st.session_state['display_ready'] = False
        st.session_state['attendance_title_str'] = '# Attendance Report'
    elif st.session_state['selected_course'] == st.session_state['last_selected_course']:
        st.session_state['analysis_needs_update'] = False
    else:    
        st.session_state['timesheetName'] = st.session_state['selected_course']
        st.session_state['rosterSheetName'] = st.session_state['selected_course'] + '_Roster'
        st.session_state['analysis_needs_update'] = True
    st.session_state['last_selected_course'] = st.session_state['selected_course']
    st.session_state['selected_course'] = 'None selected'

def update_attendance_title_str():
    st.session_state['attendance_title_str'] = '# ' + st.session_state['cur_analyzed_course'].replace("_", " ") + ' Attendance Report'
    attendTitleContainer.write(st.session_state['attendance_title_str'])

# Initialization
if 'analysis_needs_update' not in st.session_state:
    st.session_state['analysis_needs_update'] = False
if 'display_ready' not in st.session_state:
    st.session_state['display_ready'] = False
if 'analysis_complete' not in st.session_state:
    st.session_state['analysis_complete'] = False
if 'toml_dict' not in st.session_state:
    utils.read_prefs()
if 'cur_analyzed_course' not in st.session_state:
    st.session_state['cur_analyzed_course'] = ''
if 'attendance_title_str' not in st.session_state:
    st.session_state['attendance_title_str'] = '# Attendance Report'
    
utils.init_course_select_list()  # Initiates st.session_state['course_select_list']

attendTitleContainer = st.container(border = False)
    
st.selectbox(
    'New course to be analyzed', # Label for the dropdown
    st.session_state['course_select_list'],                         # The options to display
    key = 'selected_course',                # Always start at none selected
    on_change=handle_course_change
)

if st.session_state['analysis_needs_update']:
    error = runAnalysis()
    if error == 0:
        st.session_state['analysis_needs_update'] = False
        st.session_state['display_ready'] = True
        st.session_state['cur_analyzed_course'] = st.session_state['timesheetName']

# Does the actual display if the data are ready for display
if st.session_state['display_ready']:
    timesheet_df = st.session_state['timesheet_df']
    calcRoster_df = st.session_state['calcRoster_df']
    shortSummary_df = st.session_state['shortSummary_df']
    sectSummaryLong_df = st.session_state['sectSummaryLong_df']
    enrollment_df = st.session_state['enrollment_df']
    absences_df = st.session_state['absences_df']
    tardies_df = st.session_state['tardies_df']

    st.dataframe(shortSummary_df)
    
    # Download buttons here. Create two columns, side-by-side
    col1, col2 = st.columns(2)

    shortSummary_data = shortSummary_df.to_csv(index = True, header = True).encode('utf-8')
    with col1:
        st.download_button(label = 'Download Attendance',
                            data = shortSummary_data,
                            file_name = 'Attendance.csv',
                            mime = 'text/csv',
                            type = 'primary')
                        
    roster_data = calcRoster_df.to_csv(index = True, header = True).encode('utf-8')
    with col2:
        st.download_button(label = 'Download Roster',
                            data = roster_data,
                            file_name = 'Roster.csv',
                            mime = 'text/csv',
                            type = 'primary')    

    mask = absences_df['totAbsences'] > 1
    selectedRows = absences_df[absences_df['totAbsences'] > 1]
    
    st.markdown("## Multiple Absences (A > 1)")    
    st.dataframe(selectedRows)
    
    selectedTardyRows = tardies_df[tardies_df['totalTardies'] > 1]
    
    st.markdown("## Multiple Tardiness (T > 1)")
    st.dataframe(selectedTardyRows)

    st.session_state['plot_week'] = timesheet_df['week'].unique().tolist()
    st.session_state['plot_week'].reverse()
    
    # Select the default week to plot. We would like this to be the last complete week
    default_week = 0

    if 'selected_plot_week' not in st.session_state:
        st.session_state['selected_plot_week'] = st.session_state['plot_week'][default_week]
    st.selectbox(
        'Week being plotted', # Label for the dropdown
        st.session_state['plot_week'],                         # The options to display
        key = 'selected_plot_week'#,
        #on_change = handle_plot_week_change
    )
    
    temp_df = timesheet_df.groupby(['TA','sectionAssigned']).agg(
                                    Fake = ('studentName', 'first')).reset_index()
    temp_df.drop(columns = ['Fake'], inplace = True)
    sections_list = temp_df.values.tolist()
    
    for row in sections_list:
        fig = prepare_plot(sectSummaryLong_df, row[0], row[1], st.session_state['selected_plot_week'], enrollment_df)
        with st.container():
            st.plotly_chart(fig, width ='stretch')

    st.markdown("## Processed Raw Data")
    st.dataframe(timesheet_df)
    
    st.markdown('## Unknown entries')
    st.dataframe(st.session_state['unknown_df'])

update_attendance_title_str()
utils.shared_sidebar()

  

