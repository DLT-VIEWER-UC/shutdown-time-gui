from imports_utils import *

class CustomIntValidator(QIntValidator):
    def __init__(self, minimum=1, maximum=300, parent=None):
        super().__init__(minimum, maximum, parent)
        self._min = minimum
        self._max = maximum
    def setRange(self, minimum, maximum):
        self._min = minimum
        self._max = maximum
        super().setRange(minimum, maximum)
    def validate(self, input_str, pos):
        if input_str == "":
            return (QIntValidator.Intermediate, input_str, pos)
       
        if input_str.isdigit():
            # Check for leading zeros
            if input_str.startswith('0') and len(input_str) > 1:
                return (QIntValidator.Invalid, input_str, pos)
            value = int(input_str)
 
            if self._min <= value:# <= self._max:
                return (QIntValidator.Acceptable, input_str, pos)
            else:
                return (QIntValidator.Invalid, input_str, pos)
        else:
            return (QIntValidator.Invalid, input_str, pos)
       
           
class ShutdownTimeConfig(QDialog):
    DEFAULT_CONFIG = {
        # 'script-execution-time-in-seconds': 0,
        # 'iterations': 0,
        # 'threshold-in-seconds': 0,
        'windows': {'isPathSet': False, 'dltViewerPath': ''},
        'ecu-config': []
    }

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.set_window_properties()

        self.config_path = './Shutdown_Time_Scripts/shutdown_time_config.json'
        self.config_data = self.load_config()
        self.widgets = {}

        self.init_ui()
   
    def set_window_properties(self):
        self.setWindowTitle('Shutdown Time Configuration')
        self.setWindowIcon(QIcon('KPIT_logo.png'))

        # Get the geometry of the MainWindow
        main_window_x = self.main_window.x()
        main_window_y = self.main_window.y()
        main_window_width = self.main_window.width()
        main_window_height = self.main_window.height()

        # Define window dimensions
        # TODO: update these values as needed
        window_width = 900
        window_height = 550

        # Calculate the position to center the window
        x = main_window_x + (main_window_width - window_width) // 2
        y = main_window_y + (main_window_height - window_height) // 2

        # Set the geometry and fixed size of the window
        self.setGeometry(x, y, window_width, window_height)
        self.setFixedSize(window_width, window_height)

    def load_config(self):
        if not os.path.exists(self.config_path):
            return dict(self.DEFAULT_CONFIG)
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            merged = dict(self.DEFAULT_CONFIG)
            merged.update(data)
            return merged
        except Exception as e:
            return dict(self.DEFAULT_CONFIG)

    def init_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        central = QWidget()
        layout = QVBoxLayout(central)
       
        scroll.setWidget(central)
        # self.setCentralWidget(scroll)
        dlg_layout = QVBoxLayout(self)
        dlg_layout.addWidget(scroll)
        self.setLayout(dlg_layout)


        # General Settings
        general_group = QGroupBox('General Settings')
        general_group.setFixedHeight(110)
        general_layout = QFormLayout()
        for key, validator in [
            ('script-execution-time-in-seconds', CustomIntValidator(1, 500)),
            ('iterations', CustomIntValidator(1, 50))
            # , ('threshold-in-seconds', CustomIntValidator(1, 100))
        ]:
            # print(key, str(self.config_data.get(key, '')))
            le = QLineEdit(str(self.config_data.get(key, '')))
            le.setPlaceholderText('0')
            # le.textChanged.connect(lambda text: [self.ok_btn.setDisabled(False)])
            le.textChanged.connect(lambda text: [self.on_change_update_ok_btn_state()])
            le.setValidator(validator)
            le.setFixedWidth(150)
            row_layout = QHBoxLayout()
            row_layout.addWidget(le)
            if key != 'iterations':
                row_layout.addWidget(QLabel('sec'))
            general_layout.addRow(QLabel(key), row_layout)
            self.widgets[key] = le
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # Windows Settings
        win_group = QGroupBox('Windows Settings')
        win_group.setFixedHeight(100)
        win_layout = QFormLayout()
        win = self.config_data.get('windows', {})
        path_cb = QCheckBox(); path_cb.setChecked(win.get('isPathSet', False))
        win_layout.addRow(QLabel('isPathSet'), path_cb)
        self.widgets['windows.isPathSet'] = path_cb

        # Path line edit with char count
        path_le = QLineEdit(win.get('dltViewerPath', ''))
        # path_le.textChanged.connect(lambda text: [self.ok_btn.setDisabled(False)])
        path_le.textChanged.connect(lambda text: [self.on_change_update_ok_btn_state()])
        path_le.setMaxLength(250)
        count_lbl = QLabel(f"{len(path_le.text())} / {path_le.maxLength()}")
        path_le.textChanged.connect(lambda text: count_lbl.setText(f"{len(text)} / {path_le.maxLength()}"))
        browse_btn = QPushButton('Browse')
        browse_btn.clicked.connect(lambda: self.browse_path(path_le))
        hl = QHBoxLayout()
        hl.addWidget(path_le)
        hl.addWidget(browse_btn)
        hl.addWidget(count_lbl)
        win_layout.addRow(QLabel('dltViewerPath'), hl)
        self.widgets['windows.dltViewerPath'] = path_le
        win_group.setLayout(win_layout)
        layout.addWidget(win_group)

        # Enable/disable path based on checkbox
        path_le.setDisabled(path_cb.isChecked())
        browse_btn.setDisabled(path_cb.isChecked())
        count_lbl.setDisabled(path_cb.isChecked())
       
        path_cb.toggled.connect(lambda checked: [path_le.setDisabled(checked), browse_btn.setDisabled(checked), count_lbl.setDisabled(checked), self.on_change_update_ok_btn_state()])#, self.ok_btn.setDisabled(False)])

        # ECU Configurations
        self.ec_group = QGroupBox('ECU Configurations')
        self.ec_group.setFixedHeight(220)
        ec_vbox = QVBoxLayout()

        isElite, isPadas=False, False
        isRCAR, isSOC0, isSOC1 = False, False, False
        if self.config_data.get('PADAS', {}).get('RCAR', False):
            isRCAR = True
            isPadas = True
        else:
            for board_type, enabled in self.config_data.get('Elite', {}).items():
                if enabled:
                    isElite = True
                    if board_type == 'RCAR':
                        isRCAR = True
                    elif board_type == 'SoC0':
                        isSOC0 = True
                    elif board_type == 'SoC1':
                        isSOC1 = True
                   
        # print("isElite, isPadas", isElite, isPadas)
        # print("isRCAR, isSOC0, isSOC1", isRCAR, isSOC0, isSOC1)            

        self.ecu_selection_group = QGroupBox('ECU Selection')
        self.ecu_selection_group.setFixedHeight(80)
        # Radio setup
        self.padas_radio = QRadioButton("PADAS")
        self.elite_radio = QRadioButton("Elite")
        self.setup_group = QButtonGroup()
        self.setup_group.addButton(self.padas_radio)
        self.setup_group.addButton(self.elite_radio)
        self.elite_radio.setChecked(isElite)
        self.padas_radio.setChecked(isPadas)
        radio_h = QHBoxLayout()
        radio_h.addWidget(self.padas_radio)
        radio_h.addWidget(self.elite_radio)
        self.ecu_selection_group.setLayout(radio_h)
        ec_vbox.addWidget(self.ecu_selection_group)
        self.padas_radio.toggled.connect(lambda checked: [self.on_radio_changed(checked), self.on_change_update_ok_btn_state()])
        self.elite_radio.toggled.connect(lambda checked: [self.on_radio_changed(checked), self.on_change_update_ok_btn_state()])

       
        self.board_selection_group = QGroupBox('Board Selection')
        self.board_selection_group.setFixedHeight(80)
        board_selection_layout = QHBoxLayout()
        self.rcar_cb = QCheckBox('RCAR');  self.rcar_cb.setChecked(isRCAR)
        self.soc0_cb = QCheckBox('SoC0');  self.soc0_cb.setChecked(isSOC0)
        self.soc1_cb = QCheckBox('SoC1');  self.soc1_cb.setChecked(isSOC1)
        board_selection_layout.addWidget(self.rcar_cb)
        board_selection_layout.addWidget(self.soc0_cb)
        board_selection_layout.addWidget(self.soc1_cb)
        self.board_selection_group.setLayout(board_selection_layout)
        ec_vbox.addWidget(self.board_selection_group)

        self.board_selection_group.setDisabled(not self.padas_radio.isChecked() and not self.elite_radio.isChecked())

        if self.padas_radio.isChecked():
            self.soc0_cb.setDisabled(True)
            self.soc1_cb.setDisabled(True)              

        self.ec_group.setLayout(ec_vbox)
        layout.addWidget(self.ec_group)

        self.rcar_cb.toggled.connect(lambda checked: [self.on_change_update_ok_btn_state()])
        self.soc0_cb.toggled.connect(lambda checked: [self.on_change_update_ok_btn_state()])
        self.soc1_cb.toggled.connect(lambda checked: [self.on_change_update_ok_btn_state()])

        # OK/Cancel
        btn_h = QHBoxLayout()
        btn_h.addStretch()
        self.ok_btn = QPushButton('OK'); self.ok_btn.clicked.connect(self.ok_clicked)
        cancel_btn = QPushButton('Cancel'); cancel_btn.clicked.connect(self.reject)
        btn_h.addWidget(self.ok_btn); btn_h.addWidget(cancel_btn)
        layout.addLayout(btn_h)

        self.on_change_update_ok_btn_state()
        # self.ok_btn.setDisabled(True)        

    def ok_clicked(self):
        self.save_config()
        self.close()

    def done(self, result):
        print("Shutdown Time configuration window closed successfully")
        super().done(result)

    def on_radio_changed(self, checked):
        # self.ok_btn.setDisabled(False)
        visible = self.elite_radio.isChecked()
        self.board_selection_group.setDisabled(False)
        if visible:
            self.soc0_cb.setDisabled(False)
            self.soc1_cb.setDisabled(False)
            self.soc0_cb.setChecked(False)
            self.soc1_cb.setChecked(False)
        else:
            self.soc0_cb.setDisabled(True)
            self.soc1_cb.setDisabled(True)
            self.soc0_cb.setChecked(False)
            self.soc1_cb.setChecked(False)
        # for i in (1, 2):
        #     self.ecu_block_list[i].setVisible(visible)

    def on_change_update_ok_btn_state(self):
        enabled = True
        for key in ['script-execution-time-in-seconds', 'iterations']: # , 'threshold-in-seconds'
            text = self.widgets[key].text()
            if not text or len(text) == 0:
                enabled = False
                break
        if enabled:
            path_cb = self.widgets['windows.isPathSet']
            path_le = self.widgets['windows.dltViewerPath']
            if not path_cb.isChecked() and (not path_le.text() or len(path_le.text()) == 0):
                enabled = False
        if enabled:
            if not self.padas_radio.isChecked() and not self.elite_radio.isChecked():
                enabled = False
            elif not self.rcar_cb.isChecked() and not self.soc0_cb.isChecked() and not self.soc1_cb.isChecked():
                enabled = False

        self.ok_btn.setEnabled(enabled)

    def browse_path(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self, 'Select dlt-viewer executable')
        if path:
            line_edit.setText(path)

    def save_config(self):
        data = {}
        for key in ['script-execution-time-in-seconds', 'iterations']: # , 'threshold-in-seconds'
            w = self.widgets[key]
            # print(w.text())
            if w.text() and len(w.text())>0:
                data[key] = int(w.text())
        data['windows'] = {
            'isPathSet': self.widgets['windows.isPathSet'].isChecked(),
            'dltViewerPath': self.widgets['windows.dltViewerPath'].text()
        }
        data['PADAS'] = {
            'RCAR': self.rcar_cb.isChecked() and self.padas_radio.isChecked()
        }
        data['Elite'] = {
                'RCAR': self.rcar_cb.isChecked() and self.elite_radio.isChecked(),
                'SoC0': self.soc0_cb.isChecked() and self.elite_radio.isChecked(),
                'SoC1': self.soc1_cb.isChecked() and self.elite_radio.isChecked()
        }
        try:
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=4)

            self.accept()
        except Exception as e:
            print(f'Failed to save config: {e}')