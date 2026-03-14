# This module queries Canvas for all of the Turnitin similarity scores for a single assignment
#   using the current Canvas gradebook. The scores are output in a csv.
#
# This module requires a Canvas token be stored via Settings and that the base URL of the Canvas
#   instance be set in Settings. These must be set up before running the module or errors will result.
import pandas as pd
import numpy as np
import streamlit as st
from streamlit import session_state as ss
import keyring as kr
from datetime import datetime, date, timedelta, timezone
import os
import requests
import utils
from canvasapi import Canvas

def get_auth_token():
    """ Get Canvas token from system keychain. This needs to be set up in Settings """
    try:
        username = os.getlogin()
        pwd = kr.get_password("alfred_canvas", username)
        auth_token = pwd
        return auth_token
    except:
        st.error('No Canvas token on this computer.')
        return 'No token'

def currentTerm():
    """ Guesses the current semester based on today's date. """
    today = date.today()
    springEnd = datetime.strptime('May 30 2025', '%b %d %Y').date().replace(year=today.year)
    summerEnd = datetime.strptime('Aug 15 2025', '%b %d %Y').date().replace(year=today.year)
    term = 'Spring' if today < springEnd else ('Summer' if today < summerEnd else 'Fall')
    return term + ' ' + str(today.year)
    
def handle_course_change():
    """ Handles course selection change drop down """
    selected_course = ss['selected_course']
    
    if ss['last_selected_course'] != selected_course:  # Changed value
        ss['last_selected_course'] = selected_course
        ss['selected_assignment'] = 'None selected'
        if selected_course != 'None selected': # Need to update assignment list
            ss['assignment_dict'] = getAssignmentDict()
        else:
            ss['assignment_dict'] = {'None selected': 0} 
            

def handle_cnv_upload_change():
    """ Read in the Canvas gradebook, keeping only a few columns  """
    columns = ["Student", "ID", "SIS User ID", "SIS Login ID", "Section"]
    cnv_df = pd.read_csv(st.session_state['cnv_uploader_key'],
                         dtype = str,
                         skiprows=[1,2],
                         usecols = columns
                         )
    cnv_df = cnv_df[~cnv_df['Student'].str.contains('Student, Test', na=False)] # Remove test student
    cnv_df['similarity'] = np.nan
    cnv_df['turnitin_report'] = None
    
    st.session_state['cnv_df'] = cnv_df

def handle_assignment_change():
    selected_assignment = ss['selected_assignment']

def getCourseDict(onlyThisTerm = True):
    """Returns a dict of courses to which the current user has access. By default, only courses
        from the current semester are returned. Pass onlyThisTerm = False to get all courses. """

    courses = ss['canvas'].get_courses(include=["term"])

    names = ['None selected']
    ids = [0]
    curTerm = currentTerm()
    
    # Iteration required because Canvas returns PaginatedList
    for course in courses:
        course_id = getattr(course, "id", None)
        course_name = getattr(course, "name", None)
        term_obj = getattr(course, "term", None)

        # Skip malformed/incomplete course objects
        if course_id is None or not course_name:
            continue

        if not onlyThisTerm:
            names.append(course_name)
            ids.append(course_id)
            continue

        # If term info is missing, skip adding
        if term_obj is None:
            continue

        if isinstance(term_obj, dict) and term_obj.get("name") == curTerm:
            names.append(course_name)
            ids.append(course_id)

    course_dict = {k: v for k, v in zip(names, ids)}
    return course_dict
    
def getAssignmentDict():
    """ Returns a dict of assignments for course id ss['course_dict'][ss['last_selected_course_index']] """

    course_id = ss['course_dict'][ss['last_selected_course']]
    course = ss['canvas'].get_course(course_id)
    assignments = course.get_assignments()
    
    names = ['None selected']
    ids = [0]
    
    # Iteration required because Canvas returns PaginatedList
    for assignment in assignments:
        assignment_id = getattr(assignment, "id", None)
        assignment_name = getattr(assignment, "name", None)

        if assignment_id is None or not assignment_name:
            continue

        names.append(str(assignment_name))
        ids.append(assignment_id)
    
    assignment_dict = {k: v for k, v in zip(names, ids)}
    return assignment_dict

def getSimilarity(course_id, assignment_id, student_id): # Canvas ID, not CUID
    """ Gets the Turnitin similarity score and report for one student """
    
    # Formulate the Canvas query
    auth_token = 'Bearer ' + ss['auth_token']
    url = (ss['canvas_domain'] + '/api/v1/courses/' + f"{int(course_id)}" + '/assignments/'
            + f"{int(assignment_id)}" + '/submissions/' + f"{int(student_id)}")
    headers = {"authorization": auth_token}
    
    try:
        response = requests.get(url, headers = headers, timeout = 20)
    except Exception:
        return float('nan'), None

    # Process the json response
    if response.status_code == 200: # Success
        json_data = response.json()
        if 'turnitin_data' in json_data:
            attachment_name = list(json_data['turnitin_data'].keys())[0]
            similarity = json_data.get('turnitin_data', {}).get(attachment_name, {}).get('similarity_score')
            report_url = json_data.get('turnitin_data', {}).get(attachment_name, {}).get('view_report_url')
            if report_url is not None:
                turnitin_report = ss['canvas_domain'] + report_url
        else:
            similarity = float('nan')
            turnitin_report = None
    else:
        similarity = float('nan')   # User may have dropped, not turned in assignment, etc.
        turnitin_report = None

    return similarity, turnitin_report
    
def getAllSimilarities():
    """ Walks through the students in the Gradebook, querying for a Turnitin report"""
    cnv_df = ss['cnv_df']
    course_id = ss['course_dict'][ss['last_selected_course']]
    assignment_id = ss['assignment_dict'][ss['selected_assignment']]
    students = len(cnv_df)
    ii = 0
    status_text.text("Querying Canvas…")
    for row in cnv_df.itertuples(index = True):
        similarity, turnitin_report = getSimilarity(course_id, assignment_id, row.ID)
        cnv_df.loc[row.Index, 'similarity'] = similarity
        cnv_df.loc[row.Index, 'turnitin_report'] = turnitin_report
        ii += 1
        ss['progress'] = ii/students
        if ii%4 == 0:
            progress_bar.progress(ss['progress']) # Update every 4 students for efficiency
    
    # Sort dataframe by similarity
    ss['cnv_df'] = ss['cnv_df'].sort_values(by='similarity', ascending=False)
    ss['progress'] = 1.0 
    status_text.text("Operation complete!")

def reset_uploader():
    """Function to clear the uploaded files and show the uploaders again."""
    st.session_state['cnv_df'] = None
    ss['selected_course'] = 'None selected'
    ss['last_selected_course'] = 'None selected'    # None selected
    ss['selected_assignment'] = 'None selected'
    ss.progress = 0.0

# Read in preferences, then Canvas token, then Canvas class, then current list of courses
if 'toml_dict' not in st.session_state:
    utils.read_prefs()
if 'auth_token' not in ss:
    auth_token = get_auth_token()   # Returns 'No token' if no token
    ss['auth_token'] = auth_token
if 'canvas_domain' not in ss:
    ss['canvas_domain'] = ss['toml_dict']['user']['canvas_domain']
    if not ss['canvas_domain'].startswith("https://"):
        st.error('The base URL does not start with https://. Fix this in Settings.')
if 'canvas' not in ss:
    if ss['auth_token'] != 'No token':
        try:
            canvas = Canvas(ss['canvas_domain'], ss['auth_token'])
            ss['canvas'] = canvas
        except:
            st.error('Error initializng Canvas class.')
            ss['canvas'] = None
if 'course_dict' not in ss:
    ss['course_dict'] = {'None selected': 0}
    if ss['auth_token'] != 'No token':
        try:
            course_dict = getCourseDict()
            ss['course_dict'] = course_dict
        except:
            st.error('Error contacting Canvas.')
if 'last_selected_course' not in ss:
    ss['last_selected_course'] = 'None selected'    # None selected
if 'assignment_dict' not in ss:
    ss['assignment_dict'] = {'None selected': 0}
if 'selected_assignment' not in ss:
    ss['selected_assignment'] = 'None selected'
if 'cnv_df' not in ss:
    ss['cnv_df'] = None
if 'progress' not in ss:
    ss.progress = 0.0

st.title('Get Turnitin Similarities')

if ss['auth_token'] != 'No token': 
    st.button("Reset or work on a different course.", 
                on_click=reset_uploader,
                type = 'primary')
    
    if st.session_state['cnv_df'] is None:
        # Display the uploader only if no file has been uploaded yet
        st.file_uploader(
            "Upload your Canvas gradebook csv here:",
            type=['csv'],
            accept_multiple_files=False,
            key = 'cnv_uploader_key',
            on_change = handle_cnv_upload_change
        )
    else:
        st.write('#### :gray[Canvas gradebook already uploaded.]')    
    
    st.selectbox(
        'Select a course', # Label for the dropdown
        options = list(ss['course_dict'].keys()), # The options to display
        key = 'selected_course',                # Always start at none selected
        on_change = handle_course_change
    )
    
    st.selectbox(
        'Select an assignment', # Label for the dropdown
        options = list(ss['assignment_dict'].keys()), # The options to display
        key = 'selected_assignment',                # Always start at none selected
        on_change = handle_assignment_change
    )
    
    course_id = ss['course_dict'][ss['last_selected_course']]
    assignment_id = ss['assignment_dict'][ss['selected_assignment']]
    if (ss['cnv_df'] is not None and course_id > 0 and assignment_id > 0 and ss['progress'] < 0.99):
        
        st.button('Get Similarities',
                        on_click = getAllSimilarities,
                        type = 'primary')
    
        progress_bar = st.progress(ss['progress'])
        status_text = st.empty()
    
    # If a similarity report has finished, display a button for downloading report
    if ss['cnv_df'] is not None and ss['progress'] > 0.98:
        st.markdown('## Similarity Report') 
        st.dataframe(st.session_state['cnv_df'],
                    column_config={'turnitin_report': st.column_config.LinkColumn(
                    "Turnitin Link",
                    display_text="Click for report"
        )
    })
        
        assignment_name = ss['selected_assignment']
        file_name = ' '.join(assignment_name.split()[:3]) + ' Similarity.csv'
        
        similarity_data = ss['cnv_df'].to_csv(index = False, header = True).encode('utf-8')
        st.download_button(label = 'Download Similarity Report as csv',
                        data = similarity_data,
                        file_name = file_name,
                        mime = 'text/csv',
                        type = 'primary')
else:
    st.error('No Canvas token on this computer.')

utils.shared_sidebar()
