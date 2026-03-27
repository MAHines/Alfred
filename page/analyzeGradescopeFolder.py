import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components
from streamlit import session_state as ss
import utils

def read_gradescope_csv(file_str):
    """ Reads a folder of csv's or a single csv of created by Gradescope's Export Evaluations."""
    
    # The Gradescope csv's have a bunch of columns that are not useful to us. We avoid loading them
    columns = ['SID', 'Score', 'Grader']
    usecols = lambda x: (x in columns)

    # Read the csv's dragged onto the file opener
    gs_df = pd.read_csv(file_str,
                        usecols = usecols,
                        skipfooter=4,   # Skips crap at end of file
                        engine='python'
                        )
    
    # Need to give the Score and Grade columns unique names based on the problem's file name
    problemName = file_str.name.removesuffix('.csv')
    
    # Rename the columns
    columnsToRename = ['Score', 'Grader']
    gsRenamedColumns = []
    for oldName in columnsToRename:
        newName = oldName + '_' + problemName
        gs_df.rename(columns={oldName: newName}, inplace=True)
        gsRenamedColumns.append(newName)
    
    return problemName, gs_df, gsRenamedColumns


def summarize_by_grader(df, scoreCol, graderCol):
    """Analyzes a dataframe of grades to produce statistical analysis by grader. Returns a new dataframe. """
    
    # Perform the analysis by grader
    new_df = df[[scoreCol, graderCol]].groupby(graderCol).describe()
    
    # Get rid of the multilevel column headers
    new_df.columns = new_df.columns.droplevel(level=0)    
    
    # Perform an analysis of all of the grades. This will appear as the grader " All"
    all_df = df[[scoreCol]].describe()
    all_df = all_df.T
    all_df.rename(index={scoreCol: 'All'}, inplace=True)
    all_df.index.name = graderCol
    
    # Combine the ' All' data with the grader data
    new_df = pd.concat([all_df, new_df])
    
    # Get rid of extranous columns, then reorder
    new_df = new_df.rename(columns={'std': 'std dev', '50%': 'median'})
    cols_to_drop = ['min', '25%', '75%', 'max']
    new_df = new_df.drop(columns = cols_to_drop)
    dataCols = ['median', 'mean', 'std dev', 'count']
    newOrder = ['median', 'mean', 'std dev', 'count']
    new_df = new_df[newOrder]
    
    # Rename columns if working on subquestions
    if scoreCol != 'Total':
        string_to_append = '_' + scoreCol
        new_names = [item + string_to_append for item in dataCols]
        new_df.columns = new_names
     
    return new_df 
    
def loadAllData():

    if ss.uploaded_file_data is None:
        return
        
    firstFile = True
    for uploaded_file in ss['uploaded_file_data']:
                
        # Read a file and generate a number of dataframes
        #   rawData_df            This contains all of the data 
        #   comboGrader_df      This contains all of the data by primary grader
        #   primaryGrader_df    This contains the analysis by primary grader
        # The primary grader is defined to be the grader who grades the most of the assignment
        
        probName, gs_df, gsCols = read_gradescope_csv(uploaded_file)
        
        if not firstFile:
            rawData_df = pd.merge(rawData_df, gs_df, on='SID', how='left')
            scoreCols.append(gsCols[0])
            graderNameCols.append(gsCols[1])
            probNameList.append(probName)
        else:
            rawData_df = gs_df
            scoreCols = [gsCols[0]]
            graderNameCols = [gsCols[1]]  # Columns containing grader names
            probNameList = [probName]
            firstFile = False          
         
    rawData_df['Primary Grader'] = rawData_df[graderNameCols].mode(axis=1)[0]
    rawData_df['Total'] = rawData_df[scoreCols].sum(axis=1)

    # Reorder columns and store in ss
    first_cols = ['SID', 'Total', 'Primary Grader']
    remaining_cols = [col for col in rawData_df.columns if col not in first_cols]
    rawData_df = rawData_df[first_cols + remaining_cols] 
    ss.rawData_df = rawData_df
    
    scoreCols.reverse() # To keep same order after processing
    ss.scoreCols = scoreCols
    graderNameCols.reverse()
    ss.graderNameCols = graderNameCols

    probNameList.sort()
    ss.probNameList = ['All'] + probNameList


def analyzeAllData():   
    # Analyze the full data set
    if ss.include_zeroes:
        ss.allData_df = ss.rawData_df
    else:
        ss.allData_df = ss.rawData_df[ss.rawData_df['Total'] != 0]
    
    allGraderData_df = summarize_by_grader(ss.allData_df, 'Total', 'Primary Grader')
    allGraderData_df.reset_index(inplace=True)
    ss.primaryGrader_df = allGraderData_df
    
    # Analyze each question, appending the info to allGradeData_df
    for score, grader in zip(ss.scoreCols, ss.graderNameCols):
        new_df = summarize_by_grader(ss.allData_df, score, grader)
        allGraderData_df = pd.merge(allGraderData_df, new_df, left_on='Primary Grader', right_on=grader, how='left')
    
    ss.allGraderData_df = allGraderData_df
    
    ss.fig = prepare_graph()

def prepare_graph():
   
    if ss.problem_select_box == 'All':
        ss['current_problem'] = 'Analysis of All Problems'
        ss.primaryGrader_df = summarize_by_grader(ss.allData_df, 'Total','Primary Grader')
    else:
        ss['current_problem'] = 'Analysis of ' + ss.problem_select_box
        score_col = 'Score_' + ss.problem_select_box
        grader_col = 'Grader_' + ss.problem_select_box
        ss.primaryGrader_df = summarize_by_grader(ss.allData_df, score_col, grader_col)
        cols = ['median', 'mean', 'std dev', 'count']
        ss.primaryGrader_df.columns = cols
       
    if ss.use_mean:
        fig = prepare_mean_graph(ss.primaryGrader_df)
    else:
        fig = prepare_median_graph(ss.primaryGrader_df)
    return fig

def prepare_mean_graph(df):
    """Create a bar chart with error bars and a horizontal line showing the mean."""
    
    # Copy the dataframe for graphing
    plt_df = df.copy()
    plt_df['Grader'] = plt_df.index
    plt_df['sum_mean_sd'] = plt_df['mean'] + plt_df['std dev']
    plt_df['diff_mean_sd'] = plt_df['mean'] - plt_df['std dev']
    
    # Now put the columns in order of mean. Split off the first (' All') column, alphabetize, then recombine
    df_header = plt_df.iloc[[0]]
    df_rest = plt_df.iloc[1:]
    df_rest = df_rest.sort_values(by='mean', ascending=True)
    plt_df = pd.concat([df_header, df_rest])
    
    # Figure generation
    fig = px.bar(
        plt_df,
        x='Grader',
        y="mean",
        error_y="std dev",
        color_discrete_sequence=['darkkhaki'],
        title="Mean and Std Dev by Grader"
    )
    fig.update_yaxes(range=[plt_df['diff_mean_sd'].min(), plt_df['sum_mean_sd'].max()])
    fig.add_hline(y=plt_df['mean'].iloc[0], annotation_text="mean", 
          line_dash="dot", line_color='black')
    return fig

def prepare_median_graph(df):
    """Create a bar chart with error bars and a horizontal line showing the mean."""
    
    # Copy the dataframe for graphing
    plt_df = df.copy()
    plt_df['Grader'] = plt_df.index
    plt_df['sum_median_sd'] = plt_df['median'] + plt_df['std dev']
    plt_df['diff_median_sd'] = plt_df['median'] - plt_df['std dev']
    
    # Now put the columns in order of mean. Split off the first (' All') column, alphabetize, then recombine
    df_header = plt_df.iloc[[0]]
    df_rest = plt_df.iloc[1:]
    df_rest = df_rest.sort_values(by='median', ascending=True)
    plt_df = pd.concat([df_header, df_rest])
    
    # Figure generation
    fig = px.bar(
        plt_df,
        x='Grader',
        y="median",
        error_y="std dev",
        color_discrete_sequence=['darkkhaki'],
        title="Median and Std Dev by Grader"
    )
    fig.update_yaxes(range=[plt_df['diff_median_sd'].min(), plt_df['sum_median_sd'].max()])
    fig.add_hline(y=plt_df['median'].iloc[0], annotation_text="median", 
          line_dash="dot", line_color='black')
    return fig

@st.dialog('Enter string')
def nameOfAnalysis_dialog():
    """ Use a modal dialog to ask the user for a name for the analysis. This will appear at the top of the main page"""

    user_input = st.text_input('Name of data being analyzed:',
                                key="dialog_input")
    
    # Check if the user clicked the 'Submit' button inside the form
    if st.button('Submit'):
        if user_input:
            # Store the input in session state to access it in the main app
            st.session_state['analysis_name'] = user_input
            st.rerun() # Rerun the app to close the dialog and update the main view
        else:
            st.warning("Please enter a non-empty string.")

def reset_uploader():
    """Function to clear the uploaded file data and show the uploader again."""
    ss['file_uploaded'] = False
    ss['uploaded_file_data'] = None
    ss['analysis_done'] = False
    ss['analysis_name'] = 'Analyze Exported Evaluations'
    ss['current_problem'] = 'Analysis of All Problems'
    ss.problem_select_box = 'All'
    ss.include_title = False
    ss.include_title_key = False

def handle_upload_change():
    """Callback function to update session state after a file/folder is uploaded. Used to remove file upload input."""
    # Check if a file was actually uploaded in the callback
    if ss['uploader_key'] is not None:
        ss['file_uploaded'] = True
        # Store the file details for later use
        ss['uploaded_file_data'] = ss['uploader_key']
        loadAllData()

def handle_problem_change():
    """ Function to update session state when the problem to be analyzed is changed."""
    ss.fig = prepare_graph()

def handle_use_mean():
    ss.use_mean = ss.use_mean_key
    analyzeAllData()

def handle_include_zeroes_change():
    ss.include_zeroes = ss.include_zeroes_key
    analyzeAllData()

def handle_include_title_change():
    ss.include_title_key = False
    nameOfAnalysis_dialog()
    analyzeAllData()

# Initialization 
if 'uploaded_files_list' not in ss:
    ss.uploaded_files_list = []
if 'analysis_done' not in ss:
    ss.analysis_done = False
if 'file_uploaded' not in ss:
    ss['file_uploaded'] = False
if 'uploaded_file_data' not in ss:
    ss['uploaded_file_data'] = None
if 'probNameList' not in ss:
    ss.probNameList = [' All']
if 'analysis_name' not in ss:
    ss['analysis_name'] = 'Analyze Exported Evaluations'
if 'current_problem' not in ss:
    ss['current_problem'] = 'Analysis of All Problems'
if 'include_zeroes' not in ss:
    ss.include_zeroes = False
if 'include_title' not in ss:
    ss.include_title = False
if 'use_mean' not in ss:
    ss.use_mean = False
if 'problem_select_box' not in ss:
    ss.problem_select_box = 'All'

# Display the name of the analysis and the problem currently being analyzed
st.title(ss['analysis_name'])
st.header(ss['current_problem'])

col1, col2, col3 = st.columns(3)
with col1:
    st.checkbox(
        label = "Use mean, not median",
        value = ss.use_mean, # Set default from session state
        key="use_mean_key",                      # Unique key for session state access
        on_change = handle_use_mean             # Callback function
    )
with col2:
    st.checkbox(
        label = "Include papers with a zero",
        value = ss.include_zeroes, # Set default from session state
        key="include_zeroes_key",                      # Unique key for session state access
        on_change = handle_include_zeroes_change             # Callback function
    )
with col3:
    st.checkbox(
        label = "Change title",
        value = ss.include_title, # Set default from session state
        key="include_title_key",                      # Unique key for session state access
        on_change = handle_include_title_change             # Callback function
    )

# Logic to display the file uploader or the "Analyze a different file/folder" button
if not ss['file_uploaded']:
    # Display the uploader only if no file has been uploaded yet
    st.file_uploader(
        "Upload your file(s) here:",
        type=['csv'],
        accept_multiple_files=True,
        key = 'uploader_key',
        on_change=handle_upload_change
    )
else:
    st.sidebar.button("Analyze a different file/folder.", on_click=reset_uploader)


allData = st.sidebar.checkbox('Show all data.', key = 'all_data_checkbox')
allGraderData = st.sidebar.checkbox('Show all grader data', key = 'all_grader_data_checkbox')

# Performs the analysi if an unanalyzed file/folder of data exists
if ss['file_uploaded'] and not ss['analysis_done']:

    analyzeAllData()
    
    ss.analysis_done = True
    ss.combinedData = st.empty()

# Performs the necessary display tasks after the data have been analyzed
if ss['file_uploaded'] and ss['analysis_done']:
    with ss.combinedData.container():
        
        # Display the chart and the data in the Streamlit app
        st.plotly_chart(ss.fig, width = 'stretch')
        
        st.dataframe(ss.primaryGrader_df)

        st.download_button(
            "Download Primary Grader Analysis",
            ss.primaryGrader_df.to_csv().encode("utf-8"),
            'PrimaryGraderAnalysis.csv',
            "text/csv",
            key = 'primary_grader_download',
            type = 'primary'
        )
        
        # If requested, display the allData_df and/or allGraderData_df dataframes and allow download to csv
        if allData:
            st.dataframe(ss.allData_df)
            st.download_button(
                "Download All Data",
                ss.allData_df.to_csv().encode("utf-8"),
                'AllData.csv',
                "text/csv",
                key = 'all_data_download',
                type = 'primary'
            )
        if allGraderData:
            st.dataframe(ss.allGraderData_df)
            st.download_button(
                "Download All Grader Data",
                ss.allGraderData_df.to_csv().encode("utf-8"),
                'AllGraderData.csv',
                "text/csv",
                key = 'all_grader_data_download',
                type = 'primary'
            )
        
        # Display the name of the problem being analyzed
        selected_problem = st.sidebar.selectbox(
                            'Problem to be analyzed:',
                            ss.probNameList,
                            key = 'problem_select_box',
                            on_change=handle_problem_change)
        
utils.shared_sidebar()


