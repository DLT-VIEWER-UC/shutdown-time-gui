from imports_utils import *

class CustomIntValidator(QIntValidator):
    def __init__(self, min_value, max_value, parent=None):
        super().__init__(min_value, max_value, parent)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, input_str, pos):
        if input_str == "":
            return (QIntValidator.Intermediate, input_str, pos)

        if input_str.isdigit():
            # Reject leading zeros unless the value is zero itself
            if input_str.startswith('0') and len(input_str) > 1:
                return (QIntValidator.Invalid, input_str, pos)

            value = int(input_str)
            if self.min_value <= value <= self.max_value:
                return (QIntValidator.Acceptable, input_str, pos)
            else:
                return (QIntValidator.Invalid, input_str, pos)
        else:
            return (QIntValidator.Invalid, input_str, pos)

class LimitedTextEdit(QTextEdit):
    def __init__(self, max_length):
        super().__init__()
        self.max_length = max_length

    def keyPressEvent(self, event):
        current_text = self.toPlainText()
        if len(current_text) >= self.max_length and event.text() and event.key() != Qt.Key_Backspace:
            event.ignore()
            return
       
        super().keyPressEvent(event)

    def insertPlainText(self, text):
        current_text = self.toPlainText()        
        if len(current_text) + len(text) > self.max_length:
            text = text[:self.max_length - len(current_text)]
           
        super().insertPlainText(text)

    def insertFromMimeData(self, source):
        current_text = self.toPlainText()
        new_text = source.text()
       
        if len(current_text) + len(new_text) > self.max_length:
            new_text = new_text[:self.max_length - len(current_text)]
           
        super().insertPlainText(new_text)

class CyclicTurnaroundConfig(QDialog):
    def __init__(self, main_window, is_Checked):
        super().__init__()

        # Initialize message box reference (used for showing warnings)
        self.msg_box = None

        # Store reference to the main window for accessing shared data and methods
        self.main_window = main_window

        # Flag indicating whether any ECU is selected in the main window
        self.is_any_ecu_selected_flag = main_window.is_any_ecu_selected_flag

        # Define subfolder names relevant to SoC configurations
        self.SOC_SUBFOLDERS = ['RCAR', 'SoC0', 'SoC1']

        # Default ECU selection status for different platforms
        self.ecu_selection_status = {
            "PADAS": {
                "RCAR": True
            },
            "Elite": {
                "RCAR": True,
                "SoC0": True,
                "SoC1": True
            }
        }

        # Override default ECU selection status if any ECU is selected in the main window
        if self.is_any_ecu_selected_flag and is_Checked:
            self.ecu_selection_status = main_window.ecu_selection_status

        # Set dialog window properties (e.g., title, size, modality)
        self.set_window_properties()

        # Create and arrange UI components in the main layout
        self.create_main_layout()

        # Load initial data into the UI (e.g., dropdowns, fields)
        self.load_data()

        # Set up file system watcher to monitor changes in relevant folders
        self.setup_file_watcher()

        # Refresh UI borders to reflect validation status or selection highlights
        self.refresh_all_borders()
       
    def done(self, result):
        # py_logger.info("Cyclic and Turnaround Time configuration window closed successfully")
        super().done(result)
   
    def set_window_properties(self):
        # Set the window title and icon
        self.setWindowTitle('Cyclic and Turnaround Time Configuration')
        self.setWindowIcon(QIcon('KPIT_logo.png'))

        # Get the position and size of the main window to help center this dialog
        main_window_x = self.main_window.x()
        main_window_y = self.main_window.y()
        main_window_width = self.main_window.width()
        main_window_height = self.main_window.height()

        # Define fixed dimensions for this dialog window
        window_width = 1000
        window_height = 650

        # Calculate the top-left coordinates to center the dialog over the main window
        x = main_window_x + (main_window_width - window_width) // 2
        y = main_window_y + (main_window_height - window_height) // 2

        # Set the geometry and fix the size of the dialog window
        self.setGeometry(x, y, window_width, window_height)
        self.setFixedSize(window_width, window_height)

    def create_main_layout(self):
        main_layout = QVBoxLayout()        
        top_layout = QVBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QHBoxLayout()
       
        self.qnx_project_workspace_input(left_layout)
        self.configure_kev(right_layout)
        self.test_report_name_field(right_layout)

        top_layout.addLayout(left_layout)
        top_layout.addLayout(right_layout)
       
        main_layout.addLayout(top_layout)

        self.create_table_section(main_layout)
        self.setLayout(main_layout)

    def configure_kev(self, layout):
        kev_groupbox = QGroupBox("Kev Info")
        kev_groupbox.setStyleSheet(common_groupbox_style)
        kev_groupbox.setFixedWidth(360)

        kev_layout = QFormLayout()
        kev_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.kev_generation_dropdown = QComboBox()
        self.kev_generation_dropdown.addItem("True", True)
        self.kev_generation_dropdown.addItem("False", False)
        self.kev_generation_dropdown.setFixedSize(100, 35)
        self.kev_generation_dropdown.currentIndexChanged.connect(self.validate_all_fields)

        gen_layout = QHBoxLayout()
        gen_layout.addWidget(self.kev_generation_dropdown)

        kev_layout.addRow(QLabel("Generate KEV File"), gen_layout)
       
        self.folder_button = QPushButton()
        self.folder_button.setFixedWidth(30)
        # self.folder_button.setFixedHeight(30)
        self.folder_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self.open_file_manager)
        gen_layout.addWidget(self.folder_button)
     
        # Kev Duration
        duration_layout = QHBoxLayout()
        self.kev_duration_input = QLineEdit()
        self.kev_duration_input.textChanged.connect(self.validate_all_fields)
        self.kev_duration_input.setFixedSize(100, 35)
        self.kev_duration_input.setValidator(CustomIntValidator(1, 3))

        duration_layout = QHBoxLayout()
        duration_layout.addWidget(self.kev_duration_input)
        # duration_layout.addWidget(QLabel("1-5 (sec)"))
        # duration_layout.addWidget(QLabel("1-5 sec (Integer)"))
        duration_layout.addWidget(QLabel("sec:1-3 (Int)"))

        kev_layout.addRow(QLabel("Kev Generation\nDuration"), duration_layout)      

        kev_groupbox.setLayout(kev_layout)

        layout.addWidget(kev_groupbox)  
           
    def qnx_project_workspace_input(self, layout):
        qnx_groupbox = QGroupBox("QNX Info")
        qnx_groupbox.setStyleSheet(common_groupbox_style)
       
        qnx_layout = QFormLayout()
        qnx_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # QNX Installed Path
        self.qnx_path_input = QLineEdit()
        self.qnx_path_input.setFixedHeight(40)
        self.qnx_path_input.textChanged.connect(self.validate_all_fields)
        self.qnx_path_input.setReadOnly(True)
       
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self.browse_qnx_path)
       
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.qnx_path_input)
        path_layout.addWidget(browse_btn)
       
        qnx_layout.addRow(QLabel("QNX Installed Path"), path_layout)

        # Workspace Path
        self.workspace_path_input = LimitedTextEdit(250)
        self.workspace_path_input.setFixedHeight(50)
        self.workspace_path_input.textChanged.connect(self.validate_all_fields)
        self.workspace_path_char_count = QLabel("0/250")
        self.workspace_path_input.textChanged.connect(
            lambda: self.workspace_path_char_count.setText(f"{len(self.workspace_path_input.toPlainText())}/250")
        )
       
        workspace_layout = QHBoxLayout()
        workspace_layout.addWidget(self.workspace_path_input)
        workspace_layout.addWidget(self.workspace_path_char_count)
       
        qnx_layout.addRow(QLabel("Workspace Path"), workspace_layout)

        qnx_groupbox.setLayout(qnx_layout)
       
        layout.addWidget(qnx_groupbox)

    def test_report_name_field(self, layout):
        report_groupbox = QGroupBox("Report Details")
        report_groupbox.setStyleSheet(common_groupbox_style)
       
        report_layout = QFormLayout()
        report_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        total_path = os.path.join(os.getcwd(),'Reports/04_Cyclic_and_Turnaround_Time/2025-07-28_09-47-27/')
       
        # Report Name
        report_name_label = QLabel("Report Name")

        self.test_report_name_input = LimitedTextEdit(250 - len(total_path))
        self.test_report_name_input.setFixedHeight(45)
        self.test_report_name_input.textChanged.connect(self.validate_all_fields)
        self.test_report_name_char_count = QLabel(f"{len(total_path)}/250")
        self.test_report_name_input.textChanged.connect(
            lambda: self.test_report_name_char_count.setText(f"{len(self.test_report_name_input.toPlainText()) + len(total_path)}/250")
        )
       
        report_name_layout = QHBoxLayout()        
        report_name_layout.addWidget(report_name_label)
        report_name_layout.addWidget(self.test_report_name_input)
        report_name_layout.addWidget(self.test_report_name_char_count)
       
        report_layout.addRow(report_name_layout)

        # Margin Cyclic
        margin_label = QLabel("Margin Cyclic")

        self.margin_cyclic_input = QLineEdit()
        self.margin_cyclic_input.setValidator(CustomIntValidator(0, 100))
        self.margin_cyclic_input.setFixedWidth(100)
        self.margin_cyclic_input.textChanged.connect(self.validate_all_fields)

        # margin_unit_label = QLabel("0-100 (%)")
        margin_unit_label = QLabel("0-100% (Int)")

        margin_layout = QHBoxLayout()
        margin_layout.addWidget(margin_label)
        margin_layout.addWidget(self.margin_cyclic_input)
        margin_layout.addWidget(margin_unit_label)
        margin_layout.addStretch()
       
        report_layout.addRow(margin_layout)

        report_groupbox.setLayout(report_layout)
       
        layout.addWidget(report_groupbox)

    def browse_qnx_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select QNX Installed File", '', 'Executable files (*.exe)')        
        if path:
            self.qnx_path_input.setText(path)

    def create_table_section(self, layout):
        table_groupbox = QGroupBox("Application Settings")
        table_groupbox.setStyleSheet(common_groupbox_style)
       
        table_layout = QVBoxLayout()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "AppName", "Cyclic\nThreshold", "Turnaround\nThreshold", "SoC", "Delete\nRow"
        ])
       
        # Column resizing
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
       
        self.table.setColumnWidth(0, 500)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(4, 60)

        table_layout.addWidget(self.table)

        # OK, Cancel and Add buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
       
        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.ok_clicked)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
       
        self.add_button = QPushButton("Add Row")
        self.add_button.clicked.connect(self.add_row)

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
       
        table_layout.addLayout(button_layout)

        table_groupbox.setLayout(table_layout)
       
        layout.addWidget(table_groupbox)

        self.add_row()
   
    def add_row(self):
        row_position = self.table.rowCount()
       
        self.table.insertRow(row_position)

        # App Name input
        app_name = QLineEdit()
        app_name.textChanged.connect(self.validate_all_fields)
       
        self.table.setCellWidget(row_position, 0, app_name)

        # Cyclic Threshold input
        cyclic_input = QLineEdit()
        cyclic_input.setValidator(CustomIntValidator(0, 100))
        cyclic_input.textChanged.connect(self.validate_all_fields)
       
        self.table.setCellWidget(row_position, 1, cyclic_input)

        # Turnaround Threshold input
        turnaround_input = QLineEdit()
        turnaround_input.setValidator(CustomIntValidator(0, 100))
        turnaround_input.textChanged.connect(self.validate_all_fields)
       
        self.table.setCellWidget(row_position, 2, turnaround_input)
       
        soc_combo = QComboBox()
        soc_combo.addItems(["Select SoC"])
        soc_combo.model().item(0).setEnabled(False)

        # if self.is_any_ecu_selected_flag:
        #     if "RCAR" in self.ecu_selection_status["PADAS"] and self.ecu_selection_status["PADAS"]["RCAR"]:
        #         soc_combo.addItem("PADAS")
       
        #     for soc in self.ecu_selection_status["Elite"]:
        #         if self.ecu_selection_status["Elite"][soc]:
        #             soc_combo.addItem(soc)
        # else:
        soc_combo.addItems(["PADAS", "RCAR", "SoC0", "SoC1"])

        soc_combo.currentTextChanged.connect(self.validate_all_fields)
        self.table.setCellWidget(row_position, 3, soc_combo)

        # Remove Row Button
        remove_btn = QPushButton()
        remove_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        remove_btn.clicked.connect(self.handle_remove_button)
       
        self.table.setCellWidget(row_position, 4, remove_btn)

        self.update_remove_buttons()
        self.validate_all_fields()
   
    def handle_remove_button(self):
        button = self.sender()
       
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 4) == button:
                self.remove_row(row)
                break

    def remove_row(self, row):
        if self.table.rowCount() > 1:
            self.table.removeRow(row)
            self.update_remove_buttons()
            self.validate_all_fields()

    def update_remove_buttons(self):
        for row in range(self.table.rowCount()):
            remove_btn = self.table.cellWidget(row, 4)
            remove_btn.setEnabled(self.table.rowCount() > 1)    

    def get_soc_folder_paths(self):
        """
        Returns full paths to all SoC subfolders.        
        This method constructs the full paths to the SoC subfolders by joining the base path with the subfolder names.
        """
        # Define the base path to the Pre_KEV_Files directory
        base_path = os.path.join(os.path.dirname(__file__), 'Cyclic_Turnaround_Time_Scripts', 'Pre_KEV_Files')
       
        # Use a list comprehension to construct the full paths to the SoC subfolders
        return [os.path.join(base_path, subfolder) for subfolder in self.SOC_SUBFOLDERS]

    def ensure_soc_folders_watched(self):
        """
        Ensures all SoC folders exist and are added to the file watcher.        
        This method creates the SoC folders if they do not exist and adds them to the file watcher to monitor for changes.
        """
        # Iterate over the SoC folder paths
        for folder in self.get_soc_folder_paths():
            # Create the folder if it does not exist, using exist_ok=True to avoid raising an exception if the folder already exists
            os.makedirs(folder, exist_ok=True)
           
            # Check if the folder is already being watched by the file watcher
            if folder not in self.file_watcher.directories():
                # Add the folder to the file watcher if it is not already being watched
                self.file_watcher.addPath(folder)

    def get_folders_with_multiple_files(self, extension=".kev"):
        """
        Returns a list of SoC folders that contain more than one file with the given extension.        
        Args:
            extension (str): The file extension to check for (defaults to ".kev").        
        Returns:
            list: A list of SoC folder names that contain more than one file with the given extension.
        """
        # Initialize an empty list to store the SoC folders with multiple files
        multiple_file_folders = []
       
        # Iterate over the SoC folder paths
        for folder in self.get_soc_folder_paths():
            # Check if the folder exists
            if os.path.exists(folder):
                # Use a list comprehension to get a list of files in the folder that match the given extension
                files = [f for f in os.listdir(folder)
                        if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(extension)]
               
                # Check if there is more than one file in the folder
                if len(files) > 1:
                    # Get the name of the SoC folder
                    folder_name = os.path.basename(folder)
                   
                    # Add the SoC folder name to the list of folders with multiple files
                    multiple_file_folders.append(folder_name)
       
        # Return the list of SoC folders with multiple files
        return multiple_file_folders

    def setup_file_watcher(self):
        """
        Initializes the file watcher and connects change signals to validation.        
        This method sets up the file watcher to monitor the SoC folders for changes and connects the change signals to the validation method.
        """
        # # Import the QFileSystemWatcher class from PyQt5
        # from PyQt5.QtCore import QFileSystemWatcher
       
        # Initialize the file watcher
        self.file_watcher = QFileSystemWatcher()
       
        # Ensure that the SoC folders exist and are being watched by the file watcher
        self.ensure_soc_folders_watched()
       
        # Connect the directoryChanged signal to the validation method
        self.file_watcher.directoryChanged.connect(self.validate_all_fields)
       
        # Connect the fileChanged signal to the validation method
        self.file_watcher.fileChanged.connect(self.validate_all_fields)
   
    def open_file_manager(self):
        """
        Opens the file manager at the Pre_KEV_Files directory.
        Warns if multiple files exist in any SoC folder.
        """        
        try:
            # Define the base path to the Pre_KEV_Files directory
            base_path = os.path.join(os.path.dirname(__file__), 'Cyclic_Turnaround_Time_Scripts', 'Pre_KEV_Files')
           
            # Ensure that the SoC folders are being watched for changes
            self.ensure_soc_folders_watched()

            # Check if there are any folders with multiple files
            multiple_file_folders = self.get_folders_with_multiple_files()
           
            # If multiple files are found, highlight the folder button and display a warning message
            if multiple_file_folders:
                # Highlight the folder button with a red border
                self.folder_button.setStyleSheet("border: 2px solid red;")
               
                # Create a comma-separated list of folders with multiple files
                folder_list = ", ".join(multiple_file_folders)
               
                # Display a warning message to the user
                self.show_warning_once(folder_list)

            # Open the Pre_KEV_Files directory in the system file manager
            if os.path.exists(base_path):
                # Check the operating system to determine the correct command to open the file manager
                if os.name == 'nt':  # Windows
                    # Use the os.startfile function to open the directory
                    os.startfile(base_path)
                elif os.name == 'posix':  # Linux or macOS
                    # Use the os.system function to open the directory
                    os.system(f'open "{base_path}"' if sys.platform == 'darwin' else f'xdg-open "{base_path}"')
            else:
                # If the directory does not exist, display an error message to the user
                QMessageBox.warning(self, "Path Not Found", f"The path '{base_path}' does not exist.")

        except Exception as e:
            # Log any exceptions that occur during the execution of this method
            py_logger.error(self, "Error", f"An error occurred: {str(e)}")
        finally:
            # Validate all fields after attempting to open the file manager
            self.validate_all_fields()
   
    def show_warning_once(self, folder_list):
        """
        Displays a warning message box to the user if multiple files exist in the specified folders.
       
        Args:
            folder_list (str): A comma-separated list of folder paths where multiple files were found.
        """
       
        # Check if a message box is already open to prevent multiple warnings from being displayed
        if hasattr(self, 'msg_box') and self.msg_box is not None and self.msg_box.isVisible():
            return  # Don't show again if already visible

        # Create a new message box instance
        self.msg_box = QMessageBox(self)
       
        # Set the message box icon to warning
        self.msg_box.setIcon(QMessageBox.Warning)
       
        # Set the title of the message box
        self.msg_box.setWindowTitle("Multiple .kev Files Warning")
       
        # Set the text of the message box with the list of folders where multiple files were found
        self.msg_box.setText(
            "More than one `.kev` file exists in the following folder(s):\n"
            f"{folder_list}\n"
            "Please ensure only one `.kev` file is present in each folder."
        )
       
        # Set the standard buttons for the message box (in this case, only the OK button)
        self.msg_box.setStandardButtons(QMessageBox.Ok)

        # Show the message box modally and wait for user interaction
        # The exec_() method runs the message box event loop and returns when the user closes the message box
        self.msg_box.exec_()
   
    def validate_all_fields(self):
        """
        Validates all table rows and required fields, and enables/disables the OK button.
       
        This method checks the validity of all table rows, required fields, and the state of the dropdown selection.
        It then enables or disables the OK button based on the validation results.
        """
       
        # Initialize a flag to track the overall validity of all fields
        all_valid = True

        # Iterate over each row in the table
        for row in range(self.table.rowCount()):
            # Initialize a flag to track the validity of the current row
            row_valid = True
           
            try:
                # Get the values from the current row
                app_name = self.table.cellWidget(row, 0).text().strip()
                cyclic_text = self.table.cellWidget(row, 1).text().strip()
                turnaround_text = self.table.cellWidget(row, 2).text().strip()
                soc_combo = self.table.cellWidget(row, 3)
                soc_selected = soc_combo.currentText() if isinstance(soc_combo, QComboBox) else ""

                # Check if any of the required fields are empty
                if not app_name or not cyclic_text or not turnaround_text:
                    row_valid = False
                else:
                    # Attempt to convert the cyclic and turnaround values to integers
                    cyclic_val = int(cyclic_text)
                    turnaround_val = int(turnaround_text)
                   
                    # Check if the cyclic and turnaround values are within the valid range (0-100)
                    if not (0 <= cyclic_val <= 100) or not (0 <= turnaround_val <= 100):
                        row_valid = False

                # Check if a SoC has been selected
                if soc_selected == "Select SoC" or not soc_selected:
                    row_valid = False

            except Exception as e:
                # Handle any exceptions that occur during validation
                print(f"Error validating row {row}: {e}")
                row_valid = False

            # If the current row is not valid, set the overall validity flag to False
            if not row_valid:
                all_valid = False

        try:
            # Check if all required fields have been filled
            fields_filled = all([
                self.qnx_path_input.text().strip(),
                self.workspace_path_input.toPlainText().strip(),
                self.test_report_name_input.toPlainText().strip(),
                self.margin_cyclic_input.text().strip()
            ])
           
            # If the KEV duration input is enabled, check if it has been filled
            if self.kev_duration_input.isEnabled():
                fields_filled = fields_filled and bool(self.kev_duration_input.text().strip())
        except Exception as e:
            # Handle any exceptions that occur during field validation
            print(f"Error validating fields: {e}")
            fields_filled = False        
           
        # Get the current selection state from the dropdown
        is_enabled = self.kev_generation_dropdown.currentData()

        # Enable/disable relevant UI elements based on dropdown selection
        self.kev_duration_input.setEnabled(is_enabled)
        self.folder_button.setEnabled(not is_enabled)

        # Reset styles and tooltips
        self.folder_button.setStyleSheet("")
        self.folder_button.setToolTip("")
        self.ok_button.setToolTip("")

        # Check for folders with multiple .kev files only if the folder button is enabled
        multiple_file_folders = self.get_folders_with_multiple_files() if not is_enabled else None

        # Highlight the folder button if multiple .kev files are found
        if multiple_file_folders:
            self.folder_button.setStyleSheet("border: 2px solid red;")
            self.folder_button.setToolTip("Multiple .kev files found")

        # Determine if the OK button should be enabled
        border_status = self.refresh_all_borders()
        ok_enabled = (
            all_valid and
            fields_filled and
            border_status and
            (is_enabled or not multiple_file_folders)
        )

        # Update the OK button state and tooltip
        self.ok_button.setEnabled(ok_enabled)
        if not ok_enabled:
            self.ok_button.setToolTip("To enable the OK Button, configure all red highlighted fields")

    def update_border(self, widget) -> bool:
        """
        Updates the border of a given widget based on its validation status.        
        Args:
            widget: The widget to update the border for.        
        Returns:
            bool: True if the widget is valid, False otherwise.
        """        
        # Define a function to apply a red border to the widget
        def apply_red_border():
            widget.setStyleSheet("border: 2px solid red;")

        # Define a function to clear the border from the widget
        def clear_border():
            widget.setStyleSheet("")

        # If the widget is disabled, clear its border and return True
        if not widget.isEnabled():
            clear_border()
            return True

        # Initialize a flag to track the validity of the widget
        is_valid = True

        # Check the type of widget and validate its content accordingly
        if isinstance(widget, QLineEdit):
            # Get the text from the line edit widget
            text = widget.text()

            # Strip any leading or trailing whitespace from the text
            stripped_text = text.strip()
           
            # If the text is empty or contains only whitespace, apply a red border and set the validity flag to False
            if not stripped_text or text != stripped_text:
                apply_red_border()
                is_valid = False
            # Otherwise, clear the border
            else:
                clear_border()

        elif isinstance(widget, QTextEdit):
            # Get the text from the text edit widget
            text = widget.toPlainText()

            # Strip any leading or trailing whitespace from the text
            stripped_text = text.strip()
           
            # If the text is empty or contains only whitespace, apply a red border and set the validity flag to False
            if text != stripped_text or not stripped_text:
                apply_red_border()
                is_valid = False
            # Otherwise, clear the border
            else:
                clear_border()
       
        elif isinstance(widget, QComboBox):
            # Get the current text from the combo box and strip any leading/trailing whitespace
            text = widget.currentText().strip()
            is_valid = True  # Flag to track validity of the selection

            # Define a mapping of combo box selections to their corresponding validation keys
            validation_map = {
                "PADAS": ("PADAS", "RCAR"),
                "RCAR": ("Elite", "RCAR"),
                "SoC1": ("Elite", "SoC1"),
                "SoC0": ("Elite", "SoC0"),
            }

            # Check if the selected text is one of the keys that require validation
            if text in validation_map:
                group, key = validation_map[text]
                # Validate the selection using the ecu_selection_status dictionary
                if not self.ecu_selection_status.get(group, {}).get(key, False):
                    apply_red_border()  # Highlight the widget with a red border to indicate error
                    is_valid = False
                else:
                    clear_border()  # Clear any previous error indication
            # If no valid selection is made (e.g., default index or empty text), mark as invalid
            elif widget.currentIndex() == 0 or text == "":
                apply_red_border()
                is_valid = False
            # Otherwise, clear the border
            else:
                clear_border()  
           
        # Return the validity flag
        return is_valid

    def refresh_all_borders(self) -> bool:
        """
        Refreshes the borders of all widgets and table cells.        
        Output:
            bool: True if all validations pass, False otherwise.
        """
       
        # Define a list of widgets to validate
        widgets_to_validate = [
            self.qnx_path_input,
            self.workspace_path_input,
            self.test_report_name_input,
            self.margin_cyclic_input,
            self.kev_duration_input
        ]

        # Initialize a list to store the validation results
        validation_results = []

        # Update borders for individual widgets
        for widget in widgets_to_validate:
            # Update the border for the current widget and append the result to the validation results list
            result = self.update_border(widget)
            validation_results.append(result)

        # Update borders for each row in the table
        for row in range(self.table.rowCount()):
            try:
                # Iterate over each column in the current row
                for column in range(4):
                    # Update the border for the current cell and append the result to the validation results list
                    result = self.update_border(self.table.cellWidget(row, column))
                    validation_results.append(result)
            except Exception as e:
                # Handle any exceptions that occur during border updates
                print(f"Error updating border for row {row}: {e}")
                # Append False to the validation results list to indicate failure
                validation_results.append(False)
       
        # Check if all validations passed
        return all(validation_results)
   
    def ok_clicked(self):
        self.save_and_close()
           
    def load_data(self):
        config_path = "./Cyclic_Turnaround_Time_Scripts/cyclic_turnaround_config.json"

        try:
            with open(config_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            return
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading configuration file: {e}")
            return

        try:
            # Check if all necessary fields are present in the JSON file
            required_fields = ["Kev_duration", "QNXInstalledPath", "project", "Test_Report_Name", "Threshold Margin", "GenerateKEVFile", "Application_Settings"]

            if not all(field in data for field in required_fields):
                print("Invalid configuration file.")
                return
           
            self.kev_duration_input.setText(str(data.get("Kev_duration", "")))
            self.qnx_path_input.setText(data.get("QNXInstalledPath", ""))
            self.workspace_path_input.setPlainText(data.get("project", ""))
            self.test_report_name_input.setPlainText(data.get("Test_Report_Name", ""))
            self.margin_cyclic_input.setText(str(data.get("Threshold Margin", "")))

            index = self.kev_generation_dropdown.findData(data.get('GenerateKEVFile', True))
            if index != -1:
                self.kev_generation_dropdown.setCurrentIndex(index)

            self.table.setRowCount(0)

            for row_data in data.get("Application_Settings", []):
                    self.add_row()
                    row = self.table.rowCount() - 1

                    try:
                        self.table.cellWidget(row, 0).setText(row_data.get("Application", ""))
                        self.table.cellWidget(row, 1).setText(str(row_data.get("CyclicThreshold", "")))
                        self.table.cellWidget(row, 2).setText(str(row_data.get("TurnaroundThreshold", "")))

                        soc_combo = self.table.cellWidget(row, 3)
                        if isinstance(soc_combo, QComboBox):
                            soc_combo.setCurrentText(row_data.get("Soc", "Select SoC"))
                       
                    except Exception as e:
                        print(f"Error updating row {row}: {e}")

            self.validate_all_fields()

        except Exception as e:
            print(f"Error applying configuration data: {e}")
   
    def save_and_close(self):
        """
        Collects user input from the UI, updates ECU selection status based on selected SoCs,
        and saves the configuration to a JSON file.
        Inputs:
        - UI fields for KEV duration, QNX path, project name, workspace path, test report name, and margin.
        - A table containing application settings including selected SoCs.
        Outputs:
        - Saves a JSON file with all configuration data including ECU selection status.
        - Closes the dialog window.
        Logic:
        1. Read and validate all input fields.
        2. Reset all ECU selections to False.
        3. Iterate through the table rows to collect application settings and selected SoCs.
        4. Update ECU selection status based on selected SoCs.
        5. Save the complete configuration to a JSON file.
        """

        try:
            # Step 1: Read and validate input fields
            kev_duration = int(self.kev_duration_input.text()) if self.kev_duration_input.text() else ""
            qnx_path = self.qnx_path_input.text()
            workspace_path = self.workspace_path_input.toPlainText()
            test_report_name = self.test_report_name_input.toPlainText()
            threshold_margin = int(self.margin_cyclic_input.text())
            generate_kev_file = self.kev_generation_dropdown.currentData()

            # Initialize configuration dictionary
            config_data = {
                "Kev_duration": kev_duration,
                "GenerateKEVFile": generate_kev_file,
                "QNXInstalledPath": qnx_path,
                "project": workspace_path,
                "Test_Report_Name": test_report_name,
                "Threshold Margin": threshold_margin,
                "Application_Settings": []
            }

            selected_socs = []

            # Step 2: Reset all ECU selections to False
            for ecu_group in self.ecu_selection_status:
                for soc in self.ecu_selection_status[ecu_group]:
                    self.ecu_selection_status[ecu_group][soc] = False

            # Step 3: Process each row in the table
            for row in range(self.table.rowCount()):
                try:
                    app_name = self.table.cellWidget(row, 0).text()
                    cyclic_threshold = int(self.table.cellWidget(row, 1).text())
                    turnaround_threshold = int(self.table.cellWidget(row, 2).text())
                    soc_combo = self.table.cellWidget(row, 3)
                    selected_soc = soc_combo.currentText()

                    selected_socs.append(selected_soc)

                    row_data = {
                        "Application": app_name,
                        "CyclicThreshold": cyclic_threshold,
                        "TurnaroundThreshold": turnaround_threshold,
                        "Soc": selected_soc
                    }

                    config_data["Application_Settings"].append(row_data)

                except ValueError as ve:
                    print(f"Invalid numeric value in row {row}: {ve}")
                except Exception as e:
                    print(f"Error processing row {row}: {e}")

            # Step 4: Update ECU selection status based on selected SoCs
            for soc in selected_socs:
                if soc == 'PADAS':
                    self.ecu_selection_status['PADAS']['RCAR'] = True
                elif soc in ['RCAR', 'SoC0', 'SoC1']:
                    self.ecu_selection_status['Elite'][soc] = True

            config_data["ECU_setting"] = self.ecu_selection_status

            # Step 5: Save configuration to JSON file
            with open("./Cyclic_Turnaround_Time_Scripts/cyclic_turnaround_config.json", "w") as f:
                json.dump(config_data, f, indent=4)

            # Step 6: Close the dialog
            self.accept()

        except ValueError as ve:
            print(f"Invalid numeric input: {ve}")
        except Exception as e:
            print(f"Error saving configuration: {e}")