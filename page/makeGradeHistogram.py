# This module produces a histogram of grades from a Gradescope csv and optionally 
#   calculates the estimated grade cutoffs based on the course median. This module
#   requires Chrome be installed on your computer for the png output.

import streamlit as st
from streamlit import session_state as ss
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import io
import math
import utils
import re


# Initialization 
def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    ss['exam_df'] = None
    ss['cutoffs_df'] = None
    ss['median_grade'] = -1
    initialize_cutoffs()
    ss['xaxis_label'] = 'Score'
    ss['selected_course'] = ss['course_select_list'][0]
    ss['xaxis_max'] = 100
    ss['bin_width'] = 5
    ss['annotation_x_pos'] = 0.02

def read_exam_csv():
    """ Reads the Gradescope grades from a csv, ignoring everything else """
    if ss['exam_df'] is None:
  
        # The Gradescope csv's have a bunch of columns that are not useful to us. 
        columns = ['Total Score']
        exam_df = pd.read_csv(ss['exam_key'],
                                 dtype=float,
                                 usecols = columns
                                 )
        ss['exam_df'] = exam_df

def cutoffPercentile(gpa):
    """Function derived from departmental distributions for median =2.8, 2.9, 3.0, and 3.3."""

    medianGPA = ss['median_grade']
    if medianGPA > 0:
        spread = 1.8286 - 0.85545 * medianGPA + 0.1709 * medianGPA**2
        return(0.5 + 0.5 * math.erf(spread * (gpa - medianGPA)))
    else:
        return float('nan')
    
def initialize_cutoffs():
    
    grades_letter = ['A+','A','A-', 'B+','B','B-','C+','C','C-']
    grades_cutoffGPA = [4.15, 3.85, 3.5, 3.15, 2.85, 2.5, 2.15, 1.85, 1.5]
    grades_cutoffPercentile = [cutoffPercentile(gpa) for gpa in grades_cutoffGPA]

    data = {'Grade': grades_letter, 'Cutoff GPA': grades_cutoffGPA, 'Cutoff Percentile': grades_cutoffPercentile}
    cutoffs_df = pd.DataFrame(data)
    ss['cutoffs_df'] = cutoffs_df

def update_xaxis_label():
    
    new_label = ss['xaxis_label_key']
    ss['xaxis_label'] = new_label

def update_annotate_x_pos():
    
    new_annotate_x = ss['annotate_x_key']
    ss['annotation_x_pos'] = new_annotate_x

def update_xaxis_max():

    new_max = ss['xaxis_max_key']
    ss['xaxis_max'] = new_max
    
def update_bin_width():

    new_width = ss['bin_width_key']
    ss['bin_width'] = new_width

def histogram_scores():
    """ Prepare the histogram """
    
    # Set the default template to ensure colors are used when exporting as png
    pio.templates.default = "plotly_white" #
    exam_df = ss['exam_df']
    
    # Bin width and number logic
    bin_start = 0.5
    bin_width = float(ss['bin_width'])
    exam_max = exam_df['Total Score'].max()
    if exam_max > float(ss['xaxis_max']):
        num_bins = math.ceil(exam_max/bin_width)
        ss['xaxis_max'] = f"{num_bins * bin_width:.0f}"
    num_bins = math.ceil(float(ss['xaxis_max'])/bin_width)
    bin_end = bin_start + (bin_width * num_bins) # This calculates the end point as 100.5
    
    # Create the histogram
    fig = go.Figure(go.Histogram(
        x = exam_df['Total Score'],
        xbins=dict(
            start = bin_start,
            end = bin_end,
            size = bin_width
        ),
        autobinx = False # Disable automatic binning to use custom settings
    ))

    # Calculate the annotation. Grades cutoffs are not displayed if course is None. 
    info_text = 'Median = ' + f"{exam_df['Total Score'].quantile(0.50):.1f}" + '<br>'
    info_text += 'Std Dev = ' + f"{exam_df['Total Score'].std():.1f}" + '<br>'
    info_text += 'Max = ' + f"{exam_df['Total Score'].max():.1f}" + '<br>'
    info_text += 'Min = ' + f"{exam_df['Total Score'].min():.1f}"
    if ss['median_grade'] > 0:
        score_cutoffs = calcGradeCutoffs()
        info_text += '<br><br>Estimated Grades <br>'
        info_text += 'A\'s      ≥  ' + f"{score_cutoffs[0]:.0f}" + '<br>'
        info_text += 'B\'s      ' + f"{score_cutoffs[1]:.0f}" + ' – ' + f"{score_cutoffs[0]-1:.0f}" + '<br>'
        info_text += 'C/C+  ' + f"{score_cutoffs[2]:.0f}" + ' – ' + f"{score_cutoffs[1]-1:.0f}" + '<br>'
        info_text += 'C–      ' + f"{score_cutoffs[3]:.0f}" + ' – ' + f"{score_cutoffs[2]-1:.0f}" + '<br>'
        info_text += 'D/F     Below ' + f"{score_cutoffs[3]:.0f}"

    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=ss['annotation_x_pos'],  # X position relative to plot area (0=left, 1=right)
        y=0.99,  # Y position relative to plot area (0=bottom, 1=top)
        text = info_text,
        showarrow=False,
        #bgcolor="white", # Optional: adds a white background to the text box
        align="left" # Aligns the text within the box
    )

    # Customize the layout (optional)
    fig.update_xaxes(title_text = ss['xaxis_label'], 
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
               color = 'black'),
        xaxis=dict(range=[0, float(ss['xaxis_max'])])
    )
    
    return fig

def calcGradeCutoffs():
    
    cutoffs_df = ss['cutoffs_df']
    exam_df = ss['exam_df']
    grade_cutoffs = ['A-', 'B-', 'C','C-']
    pct_cutoffs = [cutoffs_df.loc[cutoffs_df['Grade'] == grade, 
                    'Cutoff Percentile'].values[0] for grade in grade_cutoffs]
    score_cutoffs = [round(exam_df['Total Score'].quantile(pct_cutoff)) for pct_cutoff in pct_cutoffs]
    return score_cutoffs

def handle_course_change():
    selected_value = ss['selected_course']
    selected_course_index = ss['course_select_list'].index(selected_value)
    ss['median_grade'] = ss['median_grade_list'][selected_course_index]
    initialize_cutoffs()

# Initialization 
if 'exam_df' not in ss:
    ss['exam_df'] = None
if 'course_select_list' not in ss:
    ss['course_select_list'] = ['None', 'Chem 2070/2080 (median = 2.9)',
        'Chem 1570 (median = 2.8)', 'Chem 2090/2510/3570/3580 (median = 3.0)',
        'Chem 2150/3590/3600 (median = 3.3)']
if 'median_grade_list' not in ss:
    ss['median_grade_list'] = [-1, 2.9, 2.8, 3.0, 3.3]
if 'median_grade' not in ss:    
    ss['median_grade'] = -1
    initialize_cutoffs()
if 'xaxis_label' not in ss:
    ss['xaxis_label'] = 'Score'
    ss['xaxis_max'] = 100
    ss['bin_width'] = 5
    ss['annotation_x_pos'] = 0.02

st.markdown('## Produce Grade Histogram')

st.button("Reset or work on a different course.", 
            on_click=reset_uploader,
            type = 'primary')

st.selectbox(
    'Select appropriate course or grade median. Select \'None\' to suppress estimated grades.', # Label for the dropdown
    ss['course_select_list'],      # The options to display
    key = 'selected_course', 
    on_change=handle_course_change
)

# Logic to display the Gradescope file uploader or histogram
if ss['exam_df'] is None:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload Gradescope grade csv here:",
        type=['csv'],
        accept_multiple_files=False,
        key = 'exam_key',
        on_change = read_exam_csv
    )
else:
    st.write('#### :gray[Gradescope grades already uploaded.]')
    fig = histogram_scores()
    st.plotly_chart(fig, width = 'content')
    
    st.markdown('#### Histogram Tweaks')
    
    col1, col2 = st.columns(2)
    with col1:
        st.text_input(
            label = 'X axis label',
            value = ss['xaxis_label'],
            key="xaxis_label_key",          # Unique key to reference the widget's value in session state
            on_change = update_xaxis_label  # The callback function to call when the value changes
        )
    with col2:
        st.text_input(
            label = 'Annotation X position (0 - 1.0)',
            value = ss['annotation_x_pos'],
            key="annotate_x_key",          # Unique key to reference the widget's value in session state
            on_change = update_annotate_x_pos  # The callback function to call when the value changes
        )
    with col1:
        st.text_input(
            label = 'X axis max (Full data range always shown)',
            value = ss['xaxis_max'],
            key = "xaxis_max_key",          # Unique key to reference the widget's value in session state
            on_change = update_xaxis_max  # The callback function to call when the value changes
        )
    with col2:
        st.text_input(
            label = 'Bar width',
            value = ss['bin_width'],
            key = "bin_width_key",          # Unique key to reference the widget's value in session state
            on_change = update_bin_width  # The callback function to call when the value changes
        )
    
    # in-memory buffer for image
    buffer = io.BytesIO()    
    
    # Save the figure to the buffer as a PNG image. Kaleido is required for this step.
    # write_image can take a file-like object (like the BytesIO buffer).
    fig.write_image(file = buffer, format = "png")
    
    # Add a download button that uses the buffer content
    st.download_button(
        label = "Download histogram as PNG",
        data = buffer.getvalue(),
        file_name = "histogram.png",
        mime = "image/png",
        type = 'primary'
    )

# st.markdown('### Gradescope grades')
# st.dataframe(ss['exam_df'])
# st.markdown('### Cutoffs')
# st.dataframe(ss['cutoffs_df'])
# st.markdown('### Grade Cutoffs')
# st.dataframe(ss['approxGrades_df'])
        
utils.shared_sidebar()
