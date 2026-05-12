import streamlit as st
import os
import utils
import time

st.set_page_config(layout='wide')

def Home():
    # Create three columns and put content in the middle one
    left, mid, right = st.columns([1, 2, 1])
    
    with mid: #
        image_path = os.path.join(os.path.dirname(__file__), 'assets', 'Alfred.png')
        st.image(image_path, caption=f"{time.time()}", width=250)
        st.html('<div style="font-size: 44px;font-weight: bold">Welcome to Alfred </div>')
    utils.shared_sidebar()

pg = st.navigation({
    "": [
        st.Page(Home, title="Alfred", default=True)
    ],
    "Scripts": [
        st.Page('page/analyzeAttendance.py', title='Analyze Attendance'),
        st.Page('page/analyzeGradescopeFolder.py', title='Analyze Gradescope Folder'),
        st.Page('page/calculateFinalGrades.py', title = 'Calculate/Estimate Final Grades'),
        st.Page('page/combinePSscores_Pearson.py', title='Combine PS Scores'),
        st.Page('page/combinePreAndPostLabs_Streamlit.py', title = 'Combine Lab Scores'),
        st.Page('page/getSimilarities.py', title = 'Get Turnitin Similarities'),
        st.Page('page/makeGradeHistogram.py', title = 'Make Histogram'),
        st.Page('page/transferGradesToRoster.py', title = 'Transfer Grades to Faculty Center Roster'),
        st.Page('page/updateRoster.py', title='Update Roster'),
        st.Page('page/addStudentIDsToPearson.py', title='Add Student IDs to Pearson Roster'),
        st.Page('page/changePrefs.py', title='Settings'),
    ]
})

pg.run()
