# Import necessary libraries
import re
import os
import sys
import json
import glob
import time
import yaml
import serial
import openpyxl
import subprocess
import threading
import matplotlib.pyplot as plt
import numpy as np
from enum import Enum, auto
from openpyxl.drawing.image import Image
import xml.etree.ElementTree as ET
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font
from openpyxl.utils import get_column_letter
from pathlib import Path
from datetime import datetime
from collections import OrderedDict
from typing import Final, Tuple , Dict, OrderedDict
from typing import List, TypedDict
OFFSET_TIME: Final = 1.5
import logging
import colorlog
import pandas as pd
plot_lock = threading.Lock()

# Define a custom type for the shutdown timing information
class ShutdownInfo(TypedDict):
    process: str
    shutdown_time: datetime
    difference: float
    difference_ms: float


class ECUType(Enum):
    RCAR = "RCAR"
    PADAS = "PADAS"
    ELITE = "ELITE"
    SOC0 = "SOC0"
    SOC1 = "SOC1"

# Define a custom type for the shutdown summary information
class ShutdownSummaryInfo(TypedDict):
    process: str
    min_time: float
    max_time: float
    values: List[float]
    avg_time: float
   

# Declare global variables
local_save_path = Path(__file__).parent # Get the current file path

# Get the current date and time
current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")


# Define the column names for the application shutdown time data
application_shutdown_time_columns = ['Services/Applications', 'Time (HH:MM:SS:MS)', 'Shutdown Time (SS:MS)',
                                    'Shutdown Time (MS)']
# Define the column names for the application shutdown summary data
application_shutdown_summary_columns = ['Services/Applications', 'Minimum (sec)', 'Maximum (sec)',
                                    'Average (sec)']

# Define a border style for cells in the Excel sheet
border_style = Border(left=Side(border_style='thin'), right=Side(border_style='thin'),
                        top=Side(border_style='thin'), bottom=Side(border_style='thin'))


def setup_logging():
    # Set up colored logging configuration
    LOG_FORMAT = (
        '%(log_color)s%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s%(reset)s'
    )
    logging.root.setLevel(logging.INFO)  # Set the root logger level to INFO

    # Configure the colorlog formatter
    formatter = colorlog.ColoredFormatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    # Create a StreamHandler for console output
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)    
   

    logging.root.addHandler(stream)    

    # Return the configured logger
    return logging.getLogger(__name__)


def remove_png_files():
    # Get a list of all PNG files in the current directory
        png_files = [file for file in os.listdir() if file.endswith('.png')]

        # Delete each PNG file
        for file in png_files:
            try:
                # logger.info(file)
                os.remove(file)
            except Exception as e:
                logger.error(f"Error deleting file {file}: {e}")    




def adjust_column_width(sheet, ecu_type):
    # Special handling for merged cells in the header
    for merged_range in sheet.merged_cells.ranges:
        # Check if this is our header merged cell (usually in row 1)
        if merged_range.min_row == 1:
            # Get the text from the top-left cell of the merged range
            header_text = sheet.cell(row=merged_range.min_row, column=merged_range.min_col).value
            if header_text:
                # Calculate total width needed for the merged cell
                text_length = len(str(header_text))
                # Distribute width across merged columns
                num_columns = merged_range.max_col - merged_range.min_col + 1
                width_per_column = max(text_length / num_columns + 5, 12)  # Add padding
                # Set width for each column in the merged range
                for col_idx in range(merged_range.min_col, merged_range.max_col + 1):
                    column_letter = get_column_letter(col_idx)
                    sheet.column_dimensions[column_letter].width = width_per_column
    # Iterate through each column in the Excel sheet
    for col in sheet.columns:
        # Initialize a variable to track the maximum content length within the column
        max_length = 0
        # Extract the letter representing the label of the current column
        column_letter = get_column_letter(col[0].column)
        # Iterate through each cell in the current column, starting from the start_row
        for cell in col[0:]:
            try:
                # Check if the cell is empty
                if not cell.value:
                    continue
                # Skip cells with specific content
                if f'Startup_Time_Logs_{ecu_type}' in str(cell.value):
                    continue
                # Check if the cell is part of a merged cell
                is_merged = False
                for merged_cell in sheet.merged_cells.ranges:
                    if cell.coordinate in merged_cell:
                        is_merged = True
                        break
                # If the cell is part of a merged cell, skip it
                if is_merged:
                    continue
                # Check if the cell's alignment has wrap text enabled
                if cell.alignment.wrap_text:
                    continue
                # Attempt to retrieve the content of the cell and check its length
                cell_content = str(cell.value)
                # Update max_length if the current cell content is longer
                if len(cell_content) > max_length:
                    max_length = len(cell_content)
            except (TypeError, AttributeError, ValueError) as e:
                # Handle specific exceptions
                logger.error(f"An error occurred: {e}")
        # Calculate the adjusted width for the column based on the maximum content length with extra space
        adjusted_width = max(max_length + 10, 9)  # Ensure a minimum width of 9
        # Set the column width in the Excel sheet to the calculated adjusted width
        sheet.column_dimensions[column_letter].width = adjusted_width

def format_excel_cells(sheet, start_row):
    # Iterate over each row in the sheet, starting from the specified row
    for row in sheet.iter_rows(min_row=start_row, max_row=sheet.max_row):
       
        # Skip empty rows
        if all(cell.value is None for cell in row):
            continue
       
        # Iterate over each cell in the row
        for cell in row[0:]:  
            # Skip empty cells
            if cell.value is None:
                continue
           
            # Check if the cell value is a column header
            if cell.value in (application_shutdown_time_columns+application_shutdown_summary_columns):
               
                # Apply a green fill color and bold font to column headers
                cell.fill = PatternFill(start_color="B5E6A2", end_color="B5E6A2", fill_type="solid")
                cell.font = Font(bold=True)
                cell.border = border_style
                continue
           
            elif cell.value == "PASS":
                # If the cell value is "PASS", fill it with a light green color.
                cell.fill = PatternFill(start_color = "92D050", end_color = "92D050", fill_type = "solid")

            elif cell.value == "FAIL":
                # If the cell value is "FAIL", fill it with a light red color.
                cell.fill = PatternFill(start_color = "FF0000", end_color = "FF0000", fill_type = "solid")
               
            # Center align the cell contents horizontally and vertically
            cell.alignment = Alignment(horizontal='center', vertical='center')
           
            # Apply the defined border style to the cell
            cell.border = border_style


def plot_shutdown_times(terminated_apps, sheet, start_row, ecu_type):
    with plot_lock:
        # Extract application names and time differences
        app_names = [app['process'] for app in terminated_apps]
        time_diffs = [app['difference_ms'] for app in terminated_apps]
       
        # Create horizontal bar chart
        fig_height = max(6, len(app_names) * 0.2)
        plt.figure(figsize=(12, 8))
       
        # Create horizontal bars
        y_pos = np.arange(len(app_names))
        bars = plt.barh(y_pos, time_diffs, align='center', alpha=0.7, height=0.4)
       
        # Add value labels next to each bar
        for i, bar in enumerate(bars):
            width = bar.get_width()
            plt.text(width + 50,  # Position text slightly to the right of the bar
                    bar.get_y() + bar.get_height()/2,  # Vertical center of the bar
                    f'{time_diffs[i]:.0f} ms',  # Text with value and unit
                    ha='left',  # Horizontal alignment
                    va='center',  # Vertical alignment
                    fontsize=9)  # Font size
           
        # Set labels and title
        plt.yticks(y_pos, app_names)
        plt.xlabel('Time to terminate (ms)')
        plt.ylabel('Applications/Services')
        plt.title(f'{ecu_type} Shutdown Time (MS)')
       
        # # Set x-axis range and ticks
        # plt.xlim(0, 9000)
        # plt.xticks(range(0, 10000, 1000))

        max_time_diff = max(time_diffs)

        if max_time_diff < 10000:
            interval = 1000
        elif max_time_diff < 100000:
            interval = 10000
        else:
            interval = 100000

        plt.xlim(0, max_time_diff + interval)
        plt.xticks(np.arange(0, max_time_diff + interval * 2, interval))
       
        # Add grid lines for better readability
        plt.grid(axis='x', linestyle='--', alpha=0.7)
       
        # Tight layout to ensure everything fits
        plt.tight_layout()
        plt.subplots_adjust(left=0.25)

        # Get the current time
        timestamp = datetime.now().strftime("%M%S%f")
        plot_image = f'graph_process_shutdown_{timestamp}.png'
       
        # Save the figure
        plt.savefig(plot_image)

        # Close the plot
        plt.close()

        # Add the plot to the Excel sheet
        img = Image(plot_image)
        sheet.add_image(img, f'H{start_row}')




def get_log_file_path(ecu_type, iterations, current_timestamp, index):
    # Construct the log file name based on the ECU type and timestamp
    basename = f'{current_timestamp}_Shutdown_Time_Logs_{ecu_type}_N{index + 1}'
    # basename = f'20250602_191926_Shutdown_Time_Logs_{ecu_type}_N{index + 1}'
    logfile = basename+'.log'
    dltfile = basename+'.dlt'
    # logfile = f'{index + 1}_Shutdown_Time_Logs_RCAR_ECU_N20_20250404_173249.log'


    # Define the directory for storing logs
    logs_dir = local_save_path / "Logs"

    # Define the full path to the log file
    filename = logs_dir / logfile

    # Check if the logs directory exists, and create it if it doesn't
    if not logs_dir.exists():
        # Create the logs directory
        logs_dir.mkdir()

    # logger.info(f"filename : {filename}")
    # Return the log file path and name
    return filename, logfile, dltfile

def get_log_file_paths_for_elite(index, current_timestamp, ecu_config_list):
   
    parent_dir = local_save_path / "Logs"
    ecu_type_list = [ecu['ecu-type'] for ecu in ecu_config_list]
    logs_dir_list = [parent_dir/ecu_type for ecu_type in ecu_type_list]
    filename_list = {}
   
    for logs_dir, ecu_type in zip(logs_dir_list, ecu_type_list):
        basename = f'{current_timestamp}_Shutdown_Time_Logs_{ecu_type}_N{index + 1}'
        # basename = f'20250530_204941_Shutdown_Time_Logs_{ecu_type}_N{index + 1}'
        logfile = basename+'.log'
        dltfile = basename+'.dlt'
        filename_list[ecu_type] = tuple((logs_dir / logfile, logfile, dltfile))
        if(not logs_dir.exists()):
            logs_dir.mkdir(parents=True, exist_ok=True)
    print(f"Log files will be saved in the following directories: {filename_list}")
    return filename_list


def write_data_to_excel(welcome_timestamp: datetime, differences: List[ShutdownInfo], sheet):
    # Create a data row for the EXM_2001 termination time
    formatted_time = welcome_timestamp.strftime('%H:%M:%S.%f')[:-3]
    data_row = ['MachineFG state Shutdown', formatted_time, '-', '-']
    # Append the data row to the sheet
    sheet.append(data_row)

    # Iterate over the DLTStart timestamps and differences in parallel using zip
    for app in differences:
        # Format shutdown_time to extract only HH:MM:SS.mmm
        formatted_time = app['shutdown_time'].strftime('%H:%M:%S.%f')[:-3]
        data_row = [app['process'], formatted_time, round(app['difference'], 3), round(app['difference_ms'], 0)]
        sheet.append(data_row)


def create_header(sheet, ecu_type, app_columns):
    # Check if the sheet has existing rows and append empty rows if necessary
    if sheet.max_row > 1:
        # Append 5 empty rows to separate the header from existing data
        for _ in range(10):
            sheet.append([])

    header = ""
    columns = []
    # Determine the header text and column names based on the app_columns parameter
    if app_columns == 'shutdown_time_columns':
        # If avg_flag is False, only include Startup Time in the header
        header = f'Shutdown Time of Services/Applications on {ecu_type}'
        columns = application_shutdown_time_columns
    elif app_columns == 'shutdown_summary_columns':
        # If avg_flag is False, only include Startup Time in the header
        header = f'Services/Applications Shutdown Time from QNX Termination on {ecu_type} (Min, Max, Avg)'
        columns = application_shutdown_summary_columns

    # Append the header text to the sheet
    sheet.append([header])

    # Get the current row number (which is now the start of the header)
    start_row = sheet.max_row

    # Calculate the last column letter based on the number of columns
    last_column_letter = chr(64 + len(columns))

    # Merge the cells in the header row
    merged_range = f'A{sheet.max_row}:{last_column_letter}{sheet.max_row}'
    sheet.merge_cells(merged_range)

    # Get the merged cell object
    merged_cell = sheet.cell(row=sheet.max_row, column=1)

    # Apply formatting to the merged cell (gray fill, bold text, centered alignment)
    merged_cell.fill = PatternFill(start_color="9EB9DA", end_color="9EB9DA", fill_type="solid")
    merged_cell.alignment = Alignment(horizontal='center', vertical='center')
    merged_cell.font = Font(bold=True)

    # Append the column names for the header
    sheet.append(columns)    

    for col_idx, col_val in enumerate(columns):
        cell = sheet.cell(row=sheet.max_row, column=col_idx + 1)
        if '\n' in col_val:
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)    
        else:    
            cell.alignment = Alignment(horizontal='center', vertical='center')

    # Apply the border style to the entire merged range
    for row in sheet[merged_range]:
        for cell in row:
            cell.border = border_style

    # Return the row number where the header starts
    return start_row


def export_and_plot_average_data_to_excel(sheet, ecu_type: str, shutdown_summary: Dict[str, ShutdownSummaryInfo]):
    # Create a header in the Excel sheet for the average data
    start_row = create_header(sheet, ecu_type, 'shutdown_summary_columns')


    # Initialize an empty list to store the data
    data = [app for app in shutdown_summary.values()]

    # Sort the data based on the average time
    data.sort(key=lambda x: x['avg_time'])

    # Append the sorted data to the Excel sheet
    for data_row in data:
        sheet.append([data_row['process'], round(data_row['min_time'], 0), round(data_row['max_time'], 0), round(data_row['avg_time'], 0)])

    # Plot the average data as a graph
    terminated_apps = [{'process': app['process'], 'difference_ms': app['avg_time']} for app in data]
    plot_shutdown_times(terminated_apps, sheet, start_row, ecu_type)

    # Format the Excel cells
    format_excel_cells(sheet, start_row)
   
    # Adjust the column width of the Excel sheet
    adjust_column_width(sheet, ecu_type)


def add_logfile_hyperlink(report_path, log_path, sheet):
    # Get the next available row in the sheet
    row_no = sheet.max_row + 2
 
    # Set the text for the hyperlink
    sheet.cell(row=row_no, column=1).value = "Log File:"
   
    report_dir = os.path.dirname(report_path)  
    relative_path = os.path.relpath(log_path, report_dir)        
    relative_path = os.path.join("..", "Logs", os.path.basename(log_path))  
 
    # Use Excel's =HYPERLINK() formula with the relative path
    hyperlink_formula = f'=HYPERLINK("{relative_path}", "{log_path}")'
 
    # Insert the hyperlink formula
    sheet.cell(row=row_no + 1, column=1).value = hyperlink_formula
   
    # Set the font color of the hyperlink to blue
    sheet.cell(row=row_no + 1, column=1).font = Font(color="0000FF")



def generate_apps_shutdown_report_from_QNX_shutdown(ecu_type, sheet, welcome_timestamp, differences):
    # Create the header for the Excel sheet
    start_row = create_header(sheet, ecu_type, 'shutdown_time_columns')

    # Write the data to the Excel sheet
    write_data_to_excel(welcome_timestamp, differences, sheet)

    # Plot the differences as a graph
    # plot_process_startup_time_graph(differences, sheet, start_row, ecu_type, config.get('threshold'), False)
    plot_shutdown_times(differences, sheet, start_row, ecu_type)

    # Format the Excel cells
    format_excel_cells(sheet, start_row)

    # Adjust the column width of the Excel sheet
    adjust_column_width(sheet, ecu_type)


# Function to calculate the differences between DLTStart timestamps and the welcome timestamp
def calculate_differences(initial_shutdown_timestamp, application_shutdown_timestamps) -> Tuple[datetime, List[ShutdownInfo]]:
    # Initialize an empty dictionary to store differences
    process_shutdown_timing_info = []
    initial_shutdown_datetime = None
    # Iterate over each DLTStart timestamp
    for app_name, app_timestamp in application_shutdown_timestamps.items():
        try:
            # Parse the DLTStart timestamp and welcome timestamp to datetime objects
            app_datetime = datetime.strptime(app_timestamp, '%Y/%m/%d %H:%M:%S.%f')
            initial_shutdown_datetime = datetime.strptime(initial_shutdown_timestamp, '%Y/%m/%d %H:%M:%S.%f')
            # Calculate the difference between the two timestamps
            difference = abs((app_datetime - initial_shutdown_datetime).total_seconds())
           
            # Store the procesed objects in the list
            process_shutdown_timing_info.append({
            'process': app_name,
            'shutdown_time': app_datetime,
            'difference': difference,
            'difference_ms': difference * 1000
            })
           
        except ValueError:
            # Handle any errors parsing the timestamps
            logger.error(f"Error parsing timestamp for process {app_name}: {app_timestamp}")
    return initial_shutdown_datetime, process_shutdown_timing_info


def extract_shutdown_timing_data(lines: List[str]) -> Tuple[str, OrderedDict[str, str]]:
    # Flag to indicate if we've found the shutdown message
    shutdown_initiated = False
    mfg_timestamp=None

    # Using OrderedDict to maintain insertion order while avoiding duplicates
    terminated_apps = OrderedDict()
   
    for line in lines:
        # Check for shutdown message
        if "MachineFG State :: Shutdown" in line:
            timestamp_match = re.search(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d+)', line)
            if timestamp_match:
                shutdown_initiated = True
                mfg_timestamp=timestamp_match.group(1)
                continue
           
           
        # Check if this line contains "terminated cause:"
        if shutdown_initiated and ("terminated cause:" in line):
            # Extract timestamp
            timestamp_match = re.search(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d+)', line)
         
            app_match = re.search(r'Process termination based on request:\s*([^\s]+)\s+terminated cause:', line)
           
            if timestamp_match and app_match:
                app_name = app_match.group(1)
               
                # Remove any .0 or version suffix
                app_name = app_name.rstrip('.0')
               
                app_timestamp = timestamp_match.group(1)
               
                # Store in dictionary (will overwrite if app_name already exists)
                # For duplicates, the last occurrence's timestamp will be kept
                terminated_apps[app_name] = app_timestamp
    print("MachineFG Timestamp ::", mfg_timestamp)
    print("Terminated Applications (duplicates removed):")
    print("-------------------------------------------")
    for app_name, app_timestamp in terminated_apps.items():
        print(f"{app_name} -> Timestamp: {app_timestamp}")
    print("-------------------------------------------")
       
    return (mfg_timestamp, terminated_apps)


def RCAR_ON_OFF_Relay():
    try:
        logger.info("Turning OFF relay...")
        subprocess.run(["usbrelay", "BITFT_1=0"])
        time.sleep(3)  #  delay

        logger.info("Turning ON relay...")
        subprocess.run(["usbrelay", "BITFT_1=1"])
        time.sleep(0.2)  #  delay

    except Exception as e:
        logger.error(f"Error executing usbrelay commands: {e}")
        sys.exit(1)(1)        


def power_ON_OFF_Relay(serial_port_Relay, baudrate_Relay):
    try:
        #set up your serial port with the desire COM port and baudrate.
        signal = serial.Serial(serial_port_Relay, baudrate_Relay, timeout=1)
        if not signal.is_open:
            logger.error(f"Failed to open serial port: {serial_port_Relay}")
            sys.exit(1)(1)
       
        logger.info("Turning OFF relay...")
        signal.write("AT+CH1=0".encode())   # Relay OFF
        time.sleep(15)
       
        logger.info("Turning ON relay...")
        signal.write("AT+CH1=1".encode())   # Relay ON
        time.sleep(0.1)  # 100ms delay
    except Exception as e:
        logger.error(f"Failed to open serial port: {e}")
        sys.exit(1)


def create_workBook(ecu_type, iterations):
    try:
        # Create the report file name based on the ECU type and current timestamp
        reportName = f"Application_Shutdown_Time_{ecu_type}_N{iterations}_{current_timestamp}.xlsx"
       
        # Define the directory where the report will be saved
        report_dir = local_save_path / "Reports"
       
        # Define the full path of the report file
        report_file = report_dir / reportName
       
        # Check if the report directory exists
        if not report_dir.exists():
            # If the directory does not exist, create it
            report_dir.mkdir()
       
    except OSError as e:
        # If an error occurs while creating the directory, logger. the error message and return None
        logger.error(f"Error creating directory: {e}")
        return None, None, None
   
    except Exception as e:
        # If any other exception occurs, logger. the error message and return None
        logger.error(f"An unexpected error occurred: {e}")
        return None, None, None

    try:
        # Create a new Excel workbook
        workbook = openpyxl.Workbook()

        # Get the active sheet in the workbook
        summary_sheet = workbook.active

        # Set the title of the sheet
        summary_sheet.title = 'Summary'

        # Create a list to store the sheets
        sheets = []

        # Create each sheet and add it to the list
        for i in range(1, iterations + 1):
            sheet_title = f"GEN3_ShutdownTime_{i:02d}"
            sheet = workbook.create_sheet(title=sheet_title)
            sheets.append(sheet)

        # Remove gridlines from all the sheets in the workbook
        for sheet_exl in sheets:
            # Hide the grid lines in the sheet
            sheet_exl.sheet_view.showGridLines = False

        summary_sheet.sheet_view.showGridLines = False

       
       
        # Return the report file path, workbook object, and active sheet object
        return report_file, workbook, sheets, summary_sheet
   
    except Exception as e:
        # If any exception occurs while creating the workbook or sheet, logger. the error message and return None
        logger.error(f"An error occurred while creating the workbook or sheet: {e}")
        return None, None, None, None


def load_config(file_path):
    try:
        config_path = Path(__file__).parent.joinpath(file_path)
        root, ext = os.path.splitext(config_path)
        with open(config_path, 'r') as file:
            if ext == '.json':
                config = json.load(file)
            elif ext in ('.yml', '.yaml'):
                config = yaml.safe_load(file)
            else:
                logger.error(f"'{file_path}' is not a valid config file")        
                return None

        return config
    except (FileNotFoundError, PermissionError, yaml.YAMLError, IOError) as e:
        logger.error(f"An error occurred while reading the file '{file_path}': {e}")
        return None

   
def create_dlp_files(ecu_config_list, setup_type):
    output_dir = 'DLP'
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir_path = os.path.join(script_dir, output_dir)
    dlp_files = {}
    # Create output directory if it doesn't exist or clear it if it does
    if os.path.exists(output_dir_path):
        # Clear all files in the directory
        for file in os.listdir(output_dir_path):
            file_path = os.path.join(output_dir_path, file)
            if os.path.isfile(file_path):
                os.unlink(file_path)
    else:
        os.makedirs(output_dir_path)
    # Use the script directory to find the proj.dlp file
    proj_path = os.path.join(script_dir, 'proj.dlp')
    tree = ET.parse(proj_path)
    root = tree.getroot()
    for ecu in ecu_config_list:
        project_name = f"{setup_type}_{ecu['ecu-type']}.dlp"
        # Set hostname text to the IP address
        hostname = root.find('ecu/hostname')
        if hostname is not None:
            hostname.text = ecu['ip-address']
        else:
            print(f"Warning: 'hostname' not found for ECU {ecu['ecu-type']}")
            continue
        # Set description text to the ECU type
        description = root.find('ecu/description')
        if description is not None:
            description.text = ecu['ecu-type']
        else:
            print(f"Warning: 'description' not found for ECU {ecu['ecu-type']}")
        # Write updated XML to file
        output_path = os.path.join(output_dir_path, project_name)
        dlp_files[ecu['ecu-type']] = output_path
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
   
    return dlp_files

def update_shutdown_summary(shutdown_summary: Dict[str, ShutdownSummaryInfo], shutdown_app_timings: List[ShutdownInfo]):
    if shutdown_summary is None or len(shutdown_summary) == 0:
        # If the shutdown summary is empty, initialize it with the first set of data
        for app in shutdown_app_timings:
            shutdown_summary[app['process']] = {
                'process': app['process'],
                'min_time': app['difference_ms'],
                'max_time': app['difference_ms'],
                'values': [app['difference_ms']],
                'avg_time': app['difference_ms']
            }
    else:
        # Update the shutdown summary with the new data
        for app in shutdown_app_timings:
            # Check if the process already exists in the summary
            if app['process'] in shutdown_summary:
                # Update the min, max, and running average
                current_summary = shutdown_summary[app['process']]
                current_summary['min_time'] = min(current_summary['min_time'], app['difference_ms'])
                current_summary['max_time'] = max(current_summary['max_time'], app['difference_ms'])
                current_summary['values'].append(app['difference_ms'])
                # Update the average with new value
                current_summary['avg_time'] = sum(current_summary['values']) / len(current_summary['values'])
            else:
                # Add new process to summary
                shutdown_summary[app['process']] = {
                    'process': app['process'],
                    'min_time': app['difference_ms'],
                    'max_time': app['difference_ms'],
                    'values': [app['difference_ms']],
                    'avg_time': app['difference_ms']
                }


def validate_ip_address(ecu_config_list):
    for ecu in ecu_config_list:
        if is_valid_ip(ecu['ip-address']):
            continue
        else:
            logger.info(f"Entered IP address for {ecu['ecu-type']} is not valid.")
            return False
    return True

def capture_logs_from_dlt_viewer(log_file_name, dlt_file_name, project_file_name, config):
    print("capture_logs_from_dlt_viewer :: START")
    timeout = config['script-execution-time-in-seconds']

    if sys.platform.startswith("win"):
        isPathSet = config['windows']['isPathSet']
        if isPathSet:
            subprocess.call([r"dlt-viewer.bat", "dlt-viewer.exe", str(timeout), log_file_name, dlt_file_name, project_file_name])
        else:
            dlt_viewer_path = config['windows']['dltViewerPath']
            dlt_viewer_path = os.path.join(dlt_viewer_path, "dlt-viewer.exe")
            log_file_name = os.path.join(log_file_name)
            logger.info(f"dlt_viewer_path: {dlt_viewer_path}")
            logger.info(f"log_file_name : {log_file_name}")
            # subprocess.call([r"dlt-viewer.bat", dlt_viewer_path + "\\", str(timeout), log_file_name])
            subprocess.call([r"dlt-viewer.bat", dlt_viewer_path, str(timeout), log_file_name, dlt_file_name, project_file_name])
    elif sys.platform.startswith("linux"):
        subprocess.run("timeout " + str(timeout) + " dlt-viewer -p "+project_file_name+" -l "+dlt_file_name+" -v", shell=True)
        print("Converting *.dlt to *.txt...")
        subprocess.run("dlt-viewer -c  "+str(dlt_file_name)+" "+str(log_file_name), shell=True)
        print("Conversion done, successfully...")


 

def process_log_file(i, ecu_type, log_file_details, dlp_file, config, sheet, shutdown_summary):
    filename, logfile, dltfile = log_file_details
    capture_logs_from_dlt_viewer(filename, dltfile, dlp_file, config)
    # Attempt to open the log file in read mode with error handling for encoding issues
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
            time.sleep(2)
    except FileNotFoundError:
        logger.error(f"File not found: {filename}")
        return
    except UnicodeDecodeError as e:
        logger.error(f"Unicode decode error: {e}")
        return
           
    # Extract the shutdown timing data from the log file
    mfg_timestamp, terminated_apps = extract_shutdown_timing_data(lines)
    if mfg_timestamp is None:
        logger.error("Error: Unable to extract shutdown timing data.")
        return
   
    if (terminated_apps is None) or (len(terminated_apps) == 0):
        logger.error("Error: No terminated applications found.")
        return
   
    mfg_datetime, shutdown_app_timings = calculate_differences(mfg_timestamp, terminated_apps)
    print("differences::"+str(shutdown_app_timings))
   
    # Check if the differences were calculated
    if shutdown_app_timings is None or len(shutdown_app_timings) == 0:
        logger.error("Found error in measuring time differences from EXM termination to applications termination time")
        return
           
    update_shutdown_summary(shutdown_summary, shutdown_app_timings)

    generate_apps_shutdown_report_from_QNX_shutdown(ecu_type, sheet, mfg_datetime, shutdown_app_timings)
   
    # Add a hyperlink to the log file in the Excel sheet
    add_logfile_hyperlink(filename, logfile, sheet)            


def main():
    script_start_time = time.perf_counter()
    try:
        # Set the ECU type (this will be used to determine the configuration and reporting)
        ecu_type = "PADAS_ECU"

        # Load the configuration
        config_file_path = 'ECU_config.yml'
        config = load_config(config_file_path)

        # Check if the configuration is empty
        if config is None:
            logger.error(f"File '{config_file_path}' not found.")
            return
       
        if config['windows']['dltViewerPath'] and not os.path.isfile(os.path.join(config['windows']['dltViewerPath'], 'dlt-viewer.exe')):
            logger.error("Configured dlt-viewer path is not valid.")
            return False

        # Retrieve the number of iterations from the configuration
        try:
            iterations = config["iterations"]
        except KeyError:
            logger.error("Error: 'iterations' key not found in the configuration file.")
            return
       
        try:
            duration = config["script-execution-time-in-seconds"]
            if not isinstance(duration, int):
                logger.error("Error: 'duration' must be an integer.")
                return
        except KeyError:
            logger.error("Error: 'duration' key not found in the configuration file.")
            return

        workbook_map = {}
        # Initialize a dictionary to store the shutdown summary data
        shutdown_summary_map = {}
        setup_type = None
        enabled_ecu_list = set()
        for setup in config['setup-config']:
            if setup['setup-enabled']:
                setup_type = setup['setup-type']
                enabled_ecu_list = set([ecu['ecu-type'] for ecu in setup['ecu-list-config'] if ecu['ecu-enabled']])
                break
        if setup_type is None or len(enabled_ecu_list) == 0:
            logger.error("No enabled ECU found in the configuration.")
            return

       
        ecu_config_list = [ecu for ecu in config['ecu-config'] if ecu['ecu-type'] in enabled_ecu_list]
        for ecu in ecu_config_list:
            workbook_map[ecu['ecu-type']] = tuple(create_workBook(ecu['ecu-type'], iterations))

            if workbook_map[ecu['ecu-type']][2] is None:
                logger.error("Error: Unable to create workbook.")
                return

            shutdown_summary_map[ecu['ecu-type']] = {}

        if not validate_ip_address(ecu_config_list):
            return False
           
        dlp_files = create_dlp_files(ecu_config_list, setup_type)

        for i in range(iterations):
           
            if setup_type == ECUType.RCAR.value:
                RCAR_ON_OFF_Relay()
            else:
                power_ON_OFF_Relay(config.get('serial-port-relay'), config.get('baudrate-relay'))

            threads = []
           
            for ecu_type, (report_file, workbook, sheets, summary_sheet) in workbook_map.items():
                print("Thread: ", ecu_type, ": Started")
               
                filename_list = {}
                if setup_type == ECUType.ELITE.value:
                    filename_list = get_log_file_paths_for_elite(i, current_timestamp, ecu_config_list)
                else:
                    filename_list[ecu_type] = tuple(get_log_file_path(ecu_type, iterations, current_timestamp, i))
                if any(not filename for (filename, logfile, dltfile) in filename_list.values()):
                    logger.error("Log file not created")
                    return
                thread = threading.Thread(
                    target=process_log_file,
                    args=(
                        i,
                        ecu_type,
                        filename_list[ecu_type],
                        dlp_files[ecu_type],
                        config,
                        sheets[i],
                        shutdown_summary_map[ecu_type]
                     )
                )

                threads.append(thread)
                thread.start()
               
            # Wait for all threads to complete
            for thread in threads:
                thread.join()

        # Save workbooks and generate reports for each ECU type
        for ecu_type, (report_file, workbook, sheets, summary_sheet) in workbook_map.items():
           
            print("shutdown_summary::"+str(shutdown_summary_map[ecu_type]))
            # Check if the workbook creation was successful
            if summary_sheet is None:
                logger.error("Error: Unable to create workbook.")
                return

            # Export the average data to the Excel sheet
            export_and_plot_average_data_to_excel(summary_sheet, ecu_type, shutdown_summary_map[ecu_type])

            # Save the Excel workbook
            workbook.save(report_file)

        remove_png_files()

       

        # logger. a success message
        logger.info(f"Test report is created successfully {report_file}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        script_end_time = time.perf_counter()
        logger.info(f"Total script execution time: {(script_end_time-script_start_time):.3f} seconds")



# Run the main function if the script is executed directly
if __name__ == "__main__":
    logger = setup_logging()
    main()