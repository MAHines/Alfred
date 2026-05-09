import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import numpy as np
from pathlib import Path
import math
from datetime import datetime, timedelta, date, time
import utils
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio


def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    ss['canvasGrades_df'] = None
    ss.assignments_df = None
    ss.categorized = False

def read_canvas_csv():
    """ Reads the grades from a Canvas csv, producing 3 dataframes
        
        canvasGrades_df     Canvas gradebook data
        assignments_df      Assignment names and their categorization
        rubric_df           Weights for each assignment type. Will normalize to sum to 1
    """
    if ss['canvasGrades_df'] is None:
  
        # Read the csv, geting rid of Test Student. 
        canvasGrades_df = pd.read_csv(ss['canvas_key'],
                             dtype=str,
                             skiprows=[1,2])
        canvasGrades_df = canvasGrades_df[~canvasGrades_df['Student'].str.contains('Student, Test', na=False)]
        
        canvasGrades_df = canvasGrades_df.loc[:, ~canvasGrades_df.columns.str.startswith('Assignments')]
        cols_to_delete = ['Current Points','Final Points', 'Current Score','Unposted Current Score', 'Final Score', 'Unposted Final Score']
        canvasGrades_df = canvasGrades_df.drop(columns = cols_to_delete, errors = 'ignore')
        
        # Get rid of annoying Canvas numbers in assignment names
        canvasGrades_df.columns = canvasGrades_df.columns.str.replace(r'\s*\(\d+\)$', '', regex=True)

        # Make the assignments_df
        assignments_df = pd.DataFrame(canvasGrades_df.columns, columns=['Assignments'])
        rows_to_delete = ['Student', 'ID', 'SIS User ID', 'SIS Login ID', 'Section', 'Notes']
        assignments_df = assignments_df[~assignments_df['Assignments'].isin(rows_to_delete)]
        
        # Guess the identity of the Assignments
        assignments_df['PSs'] = assignments_df['Assignments'].str.startswith('PS')
        assignments_df['Prelims'] = assignments_df['Assignments'].str.startswith('Prelim')
        assignments_df['Final'] = assignments_df['Assignments'].str.startswith('Final')
        assignments_df['Labs'] = assignments_df['Assignments'].str.contains('Post-lab|Report', case=False, na=False)
        assignments_df['User1'] = False
        assignments_df['User2'] = False
        
        # Guess the rubric
        default_rubric = [0.10, 0.45, 0.20, 0.25, 0.0, 0.0]
        rubric_df = pd.DataFrame([default_rubric], columns = ss.categoryList)
        
        ss.canvasGrades_df = canvasGrades_df
        ss.assignments_df = assignments_df
        ss.rubric_df = rubric_df
        ss.categorized = False

def check_for_missing_grades():
    """ Takes care of blank/whitespace grades by assignment type according to user preference
        If requested, replace blanks with 0.
        If not requested, inform user of missing grades, then quit
        Final exam is special. Replace with INC if missing.
    """
    
    abort_script = False
    ss.canvasGrades_df['INC'] = False
    for gradeCategory in ss.categoryList:
        gradeCategory_list = ss.assignments_df.loc[ss.assignments_df[gradeCategory] == True, 'Assignments'].tolist()
        if ss.subZeroes_df[gradeCategory][0]:
            for assignment in gradeCategory_list:
                ss.canvasGrades_df[assignment] = ss.canvasGrades_df[assignment].fillna(0)
        elif gradeCategory == 'Final' and ss.rubric_df[gradeCategory][0] > 0.0: # Finals are special
            for assignment in gradeCategory_list:
                ss.canvasGrades_df.loc[ss.canvasGrades_df[assignment].isna(), 'INC'] = True
                ss.canvasGrades_df[assignment] = ss.canvasGrades_df[assignment].fillna('INC')
        elif ss.rubric_df[gradeCategory][0] > 0.0:
            missing_grades = ss.canvasGrades_df[gradeCategory_list].isnull().sum()
            if sum(missing_grades) > 0:
                mask = ss.canvasGrades_df[gradeCategory_list].isna().any(axis=1) | ss.canvasGrades_df[gradeCategory_list].apply(lambda x: x.astype(str).str.strip().eq('')).any(axis=1)
                students_with_missing_grades = ss.canvasGrades_df.loc[mask, 'Student'].tolist()
                error_msg = f'Missing {gradeCategory} grades for {students_with_missing_grades}'
                st.error(error_msg)
                abort_script = True
    
    if abort_script:
        st.stop()
    
def calc_grades_from_list(assignmentList):
    """ Calculates the z grade for each assignment in assignmentList, clipping result to 
            be no lower than ss.lowest_z
    """
    
    # Ignore any text entries
    numeric_df =  ss.canvasGrades_df[assignmentList].apply(pd.to_numeric, errors='coerce')
    for col in assignmentList:
        if ss.use_mean:
            ctr = numeric_df[col].mean()
        else:
            ctr = numeric_df[col].median()
        sdev = numeric_df[col].std()
        ss.canvasGrades_df[f'z_{col}'] = ((numeric_df[col] - ctr) / sdev).clip(lower = ss.lowest_z)

def calc_grades():
    """ The actual grade calculation.
    """
        
    # Go through each type of grade (e.g., PSs, labs), calculate z grade, then calculate category avg
    for gradeCategory in ss.categoryList:
        gradeCategory_list = ss.assignments_df.loc[ss.assignments_df[gradeCategory] == True, 'Assignments'].tolist()
        new_col_name = f'{gradeCategory}_avg'
        if len(gradeCategory_list) > 0:
            z_grade_list = ['z_' + str(item) for item in gradeCategory_list]
            calc_grades_from_list(gradeCategory_list)
            ss.canvasGrades_df[new_col_name] = ss.canvasGrades_df[z_grade_list].apply(pd.to_numeric, errors='coerce').mean(axis=1)
        else:
            ss.canvasGrades_df[new_col_name] = 0
            if ss.rubric_df[gradeCategory][0] > 0:
                st.error(f'Error! The weighting of {gradeCategory} is > 0, but there are no {gradeCategory} assignments. I suggest a rubric change and recalculation.')
    
    # Calculate weighted average of categories
    ss.canvasGrades_df['Grade'] = ''
    
    # If the final grade is present
    ss.canvasGrades_df.loc[ss.canvasGrades_df['INC'] == False, 'Wt Avg'] = (
                                    ss.rubric_df['Prelims'][0] * ss.canvasGrades_df['Prelims_avg']
                                    + ss.rubric_df['Final'][0] * ss.canvasGrades_df['Final_avg']
                                    + ss.rubric_df['Labs'][0] * ss.canvasGrades_df['Labs_avg']
                                    + ss.rubric_df['PSs'][0] * ss.canvasGrades_df['PSs_avg']
                                    + ss.rubric_df['User1'][0] * ss.canvasGrades_df['User1_avg']
                                    + ss.rubric_df['User2'][0] * ss.canvasGrades_df['User2_avg'])
    
    # Deal with missing final grades
    ss.canvasGrades_df.loc[ss.canvasGrades_df['INC'] == True, 'Wt Avg'] = (
                                    (ss.rubric_df['Prelims'][0] + ss.rubric_df['Final'][0]) * ss.canvasGrades_df['Prelims_avg']
                                    + ss.rubric_df['Labs'][0] * ss.canvasGrades_df['Labs_avg']
                                    + ss.rubric_df['PSs'][0] * ss.canvasGrades_df['PSs_avg']
                                    + ss.rubric_df['User1'][0] * ss.canvasGrades_df['User1_avg']
                                    + ss.rubric_df['User2'][0] * ss.canvasGrades_df['User2_avg'])
    ss.canvasGrades_df.loc[ss.canvasGrades_df['INC'] == True, 'Grade'] = 'INC'

    # Calculate each student's percentile (rank), then use to calculate department recommended grade
    ss.canvasGrades_df['Percentile'] = ss.canvasGrades_df['Wt Avg'].rank(pct=True)
    ss.canvasGrades_df['Est Grade'] = ss.canvasGrades_df['Percentile'].apply(get_grade)
    ss.canvasGrades_df = ss.canvasGrades_df.sort_values(by='Percentile', ascending=False)
    
    # Sort the columns in a readable way
    sort_order = ['Student', 'SIS User ID', 'SIS Login ID', 'Notes', 'Grade', 'Est Grade', 'Percentile',
                    'Wt Avg', 'Final_avg', 'Prelims_avg', 'Labs_avg', 'PSs_avg', 
                    'User1_avg', 'User2_avg', 'INC']
    additional_cols = [col for col in ss.canvasGrades_df.columns if col not in sort_order]
    sort_order += additional_cols
    ss.canvasGrades_df = ss.canvasGrades_df[sort_order]
    
    ss.grades_calculated = True
    
def histogram_scores():
    """ Prepare the histogram """
    
    # Set the default template to ensure colors are used when exporting as png
    pio.templates.default = "plotly_white" #
    
    # Bin width and number logic
    bin_start = ss.canvasGrades_df['Wt Avg'].min()
    bin_end = ss.canvasGrades_df['Wt Avg'].max()
    bin_width = (bin_end - bin_start)/ss.num_bins
    
    # Create the histogram
    fig = go.Figure(go.Histogram(
        x = ss.canvasGrades_df['Wt Avg'],
        nbinsx = ss.num_bins,
        xbins=dict(
            start = bin_start,
            end = bin_end,
            size = bin_width
        ),
        autobinx = False # Disable automatic binning to use custom settings
    ))

    if ss.median_grade > 0:
        grades_letter = ['A+','A','A-', 'B+','B','B-','C+','C','C-', 'D/F']
        grades_cutoffGPA = [4.15, 3.85, 3.5, 3.15, 2.85, 2.5, 2.15, 1.85, 1.5, 0]
        
        major_cutoff_gpas = [3.5, 2.5, 1.5]
        minor_cutoff_gpas = [4.15, 3.85, 3.15, 2.85, 2.15, 1.85]
        major_cutoffs = [cutoffAverage(gpa) for gpa in major_cutoff_gpas]
        minor_cutoffs = [cutoffAverage(gpa) for gpa in minor_cutoff_gpas]
        for x_pos in major_cutoffs:
            fig.add_vline(
                x=x_pos, 
                line_width=2, 
                line_dash="dash", 
                line_color="black"
            )
        for x_pos in minor_cutoffs:
            fig.add_vline(
                x=x_pos, 
                line_width=2, 
                line_dash="dash", 
                line_color="red"
            )

    # Customize the layout (optional)
    fig.update_xaxes(title_text = 'Weighted Grade (σ)', 
                        title_font=dict(size=18, color = 'black'), 
                        tickfont = dict(size = 18, color = 'black'),
                        showline = True,
                        linewidth = 2,
                        linecolor = 'black',
                        mirror = True,
                        showgrid=False)
    fig.update_yaxes(title_text='Number of Students', 
                        title_font=dict(size=18, color = 'black'), 
                        tickfont = dict(size = 18, color = 'black'),
                        mirror = True,
                        showline = True,
                        linewidth = 2,
                        linecolor = 'black',
                        showgrid=False)
    fig.update_layout(
        height = 633,
        width = 824,
        margin = dict(r = 25), # Prevents right side from being cut off
        bargap=0.05, # Optional: add a small gap between bars
        font = dict(
               family = 'Arial',
               size = 18,
               color = 'black'))
    
    return fig

def cutoffAverage(gpa):
    """Function that returns the cutoff weighted average for a given gpa"""
    
    percentile = cutoffPercentile(gpa)
    closest_idx = (ss.canvasGrades_df['Percentile'] - percentile).abs().idxmin()
    return ss.canvasGrades_df.loc[closest_idx, 'Wt Avg']

def cutoffPercentile(gpa):
    """Function derived from departmental distributions for median = 2.8, 2.9, 3.0, and 3.3."""

    medianGPA = ss['median_grade']
    if medianGPA > 0:
        spread = 1.8286 - 0.85545 * medianGPA + 0.1709 * medianGPA**2
        return(0.5 + 0.5 * math.erf(spread * (gpa - medianGPA)))
    else:
        return float('nan')
    
def initialize_cutoffs():
    """ Calculate the cutoff percentile for each letter grade """
   
    grades_letter = ['A+','A','A-', 'B+','B','B-','C+','C','C-', 'D/F']
    grades_cutoffGPA = [4.15, 3.85, 3.5, 3.15, 2.85, 2.5, 2.15, 1.85, 1.5, 0]
    grades_cutoffPercentile = [cutoffPercentile(gpa) for gpa in grades_cutoffGPA]
    ss.thresholds = sorted(zip(grades_cutoffPercentile, grades_letter), reverse = True)
    
def get_grade(percentile):
    """ Returns department recommended grade for each percentile. If ss.median_grade < 0,
            user has not selected a course / median grade, so an empty string is returned 
    """

    if ss.median_grade < 0:
        return ''
        
    for cutoff, grade in ss.thresholds:
        if percentile >= cutoff:
            return grade

def handle_median_change():
    """ Callback function that handles change in selected course / median """

    selected_value = ss['selected_course']
    selected_course_index = ss['course_select_list'].index(selected_value)
    ss['median_grade'] = ss['median_grade_list'][selected_course_index]
    if ss.median_grade > 0:
        initialize_cutoffs()

def handle_use_mean():
    """ Callback function that handles checkbox to use mean as center grade """

    ss.use_mean = ss.use_mean_key
    st.write(ss.use_mean)
    
def handle_lowest_z():
    """ Callback function that handles change in lowest_z """

    ss.lowest_z = ss.lowest_z_entry

def handle_num_bins():
    """ Callback function that handles change in ss.num_bins """
    ss.num_bins = ss.num_bins_key

# Initialization 
keys = ['canvasGrades_df', 'assignments_df', 'rubric_df', 'subZeroes_df', 'thresholds']
for key in keys:
    ss.setdefault(key, None)

keys = ['categorized', 'use_mean', 'grades_calculated']
for key in keys:
    ss.setdefault(key, False)

if 'categoryList' not in ss:
    ss.categoryList = ['PSs', 'Prelims', 'Final', 'Labs', 'User1', 'User2']
if 'lowest_z' not in ss:
    ss.lowest_z = -5.0
if 'course_select_list' not in ss:
    ss['course_select_list'] = ['None', 'Chem 2070/2080 (median = 2.9)',
        'Chem 1570 (median = 2.8)', 'Chem 2090/2510/3570/3580 (median = 3.0)',
        'Chem 2150/3590/3600 (median = 3.3)']
if 'median_grade_list' not in ss:
    ss['median_grade_list'] = [-1, 2.9, 2.8, 3.0, 3.3]
if 'median_grade' not in ss:    
    ss['median_grade'] = -1
    initialize_cutoffs()
if 'num_bins' not in ss:
    ss.num_bins = 20

st.title('Calculate/Estimate Final Grades')

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

text_str = '**Note 1:** This module can be used to estimate the current grade midway through the '
text_str += 'semester; **however,** there must be at least one graded assignment of every type '
text_str += 'except final. If there are no grades of a particular type (e.g., labs), you '
text_str += 'should zero out that rubric item. The grade on the final will be estimated from the '
text_str += 'current prelim average.'
st.write(text_str)

text_str = '**Note 2:** The lowest z value below limits the effect of 0\'s. For example, if the median grade is '
text_str += '90 and the std dev is 5, a 0 corresponds to z = -18, which will not average well. I typically use '
text_str += 'z cutoff of – 5.0 σ. Note that –4 σ = 0.003% in a normal distribution.'
st.write(text_str)

col1, col2, col3 = st.columns(3)
with col1:
    st.selectbox(
        'Select course / grade median for estimated grades.', # Label for the dropdown
        ss['course_select_list'],      # The options to display
        key = 'selected_course', 
        on_change=handle_median_change)

with col2:
    st.number_input(
                'Enter lowest z value (suggested = -5.0)',
                max_value = -3.0,
                value = -5.0,
                key = 'lowest_z_entry',
                on_change = handle_lowest_z)

with col3:
    st.checkbox(
        label = "Use mean as center, not median.",
        value = ss.use_mean,
        key="use_mean_key",
        on_change = handle_use_mean
    )

# Logic to display the Canvas file uploader or histogram
if ss['canvasGrades_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Canvas grades csv here.",
        type=['csv'],
        accept_multiple_files=False,
        key = 'canvas_key',
        on_change = read_canvas_csv
    )
else:
    st.write('#### :gray[Canvas grades already uploaded.]')
    
    # Displays editable dfs to collect info on assignments, rubric, and zero handling
    with st.form("assignment_edit_form"):
        st.write("#### Categorize the assignments, enter rubric, select zero handling, then click Submit")
        
        edited_df = st.data_editor(ss.assignments_df,
                                    num_rows = "static",
                                    hide_index = True)
        st.write('#### Rubric')
        text_str = 'The rubric will be normalized to sum to 1.0 after submission.'
        st.write(text_str)
        edited_rubric_df = st.data_editor(ss.rubric_df,
                                            num_rows = 'static',
                                            hide_index = True)
                                            
        st.write('#### Zero Handling')
        text_str = 'The best practice is to enter 0 or \'Ex\' for every missing grade in Canvas. '
        text_str += 'Alfred will automatically enter 0 for missing grades in the selected categories below. '
        text_str += 'Unless selected below, Alfred will enter \'INC\' for a missing final and estimate the final '
        text_str += 'using the prelim average. '
        text_str += 'For other missing grades, Alfred with generate an error message until you correct the Canvas gradebook.'
        st.write(text_str)
        
        default = [True, False, False, False, False, False]  # Default only PSs
        subZeroes_df = pd.DataFrame([default], columns = ss.categoryList)
        edited_subZeroes_df = st.data_editor(subZeroes_df,
                                                num_rows = 'static',
                                                hide_index = True) 
        
        # After user finishes editing, store the data
        submitted = st.form_submit_button("Submit / Change Selections",
                                            type = 'primary')
    
        if submitted:
            # Update the session state with the new data
            ss.assignments_df = edited_df
            edited_rubric_df = edited_rubric_df.div(edited_rubric_df.sum(axis=1), axis=0) # Normalize rubric
            ss.rubric_df = edited_rubric_df
            ss.subZeroes_df = edited_subZeroes_df
            st.success("Assignments categorized ard rubric entered!")
            ss.categorized = True
            check_for_missing_grades()
            st.rerun()

    # After the user has categorized assignments, display button to calculate grades 
    if ss.categorized:
        if st.button("Calculate Grades",
                        type = 'primary'):
            calc_grades()
            
    if ss.grades_calculated:
        st.write('#### Histogram')
        text_str = 'The vertical black lines represent the estimated C–/D, B–/C+, and A–/B+ cutoffs. '
        text_str += 'The vertical red lines represent the estimated G–/G and G/G+ borders for '
        text_str += 'G = [A, B, C].'
        st.write(text_str)
        
        fig = histogram_scores()
        st.plotly_chart(fig, width = 'content')

        st.markdown('#### Histogram Tweaks')
        
        col1, col2 = st.columns(2)
        with col1:
            st.number_input(label="Number of bins",
                            min_value=10,
                            value=20,
                            step=1,
                            key = 'num_bins_key',
                            on_change = handle_num_bins
                            )

        st.dataframe(ss.canvasGrades_df,
                        hide_index = 'True')

        grades_data = ss.canvasGrades_df.to_csv(index = False, header = True).encode('utf-8')
        st.download_button(label = 'Save Grades as csv',
            data = grades_data,
            file_name = 'Grades.csv',
            mime = 'text/csv',
            type = 'primary')

utils.shared_sidebar()
            
