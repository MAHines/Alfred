import streamlit as st
import os
import utils
import time

st.set_page_config(layout='wide')

def Home():
    with st.container(horizontal_alignment="center"): #
        image_path = os.path.join(os.path.dirname(__file__), 'assets', 'Alfred.png')
        st.image(image_path, caption=f"{time.time()}", width=250)
    st.html('<div style="text-align: center;font-size: 44px;font-weight: bold">Welcome to Alfred </div>')
    utils.shared_sidebar()


pg = st.navigation({
    "Overview": [
        st.Page(Home, title="Alfred", default=True)
    ],
    "Scripts": [
        st.Page('page/analyzeAttendance.py', title='Analyze Attendance'),
        st.Page('page/analyzeGradescopeFolder.py', title='Analyze Grades'),
        st.Page('page/changePrefs.py', title='Settings'),
    ]
})

pg.run()
