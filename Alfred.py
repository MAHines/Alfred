import streamlit as st
import os
import utils

st.set_page_config(layout='wide')

def Home():
    with st.container(horizontal_alignment="center"): #
        st.image("assets/Alfred.png", width=250)
    st.html('<div style="text-align: center;font-size: 44px;font-weight: bold">Welcome to Alfred </div>')
    utils.shared_sidebar()


def main():
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

    try:
        pg.run()
    except Exception as e:
        st.error(f"Something went wrong: {str(e)}", icon=":material/error:")


if __name__ == '__main__':
    main()
