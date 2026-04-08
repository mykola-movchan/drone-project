import os
import time
from PyQt6.QtWidgets import (QWidget, QPushButton, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QSlider, QFrame, QLabel,
                             QSizePolicy, QDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QPixmap, QImage


# --- PATTERN DESIGNER DIALOG ---
class PatternDialog(QDialog):
    last_saved_state = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("8x8 LED Pattern Designer")
        self.setFixedSize(420, 560)
        self.pattern_string = ""
        self.colors = {0: ("#444", "0"), 1: ("#ff0000", "r"), 2: ("#0000ff", "b"), 3: ("#800080", "p")}
        self.grid_state = [0] * 64
        self.buttons = []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        header_layout = QHBoxLayout()
        info_label = QLabel("Click pixels to cycle colors:\nGray -> Red -> Blue -> Purple")
        info_label.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")

        self.btn_load_saved = QPushButton("Display Saved")
        self.btn_load_saved.setFixedSize(110, 35)
        self.btn_load_saved.setStyleSheet(
            "background-color: #009688; color: white; border-radius: 4px; font-size: 11px;")
        self.btn_load_saved.clicked.connect(self.load_saved_pattern)
        if PatternDialog.last_saved_state is None: self.btn_load_saved.setEnabled(False)

        header_layout.addWidget(info_label, 1)
        header_layout.addWidget(self.btn_load_saved)
        layout.addLayout(header_layout)

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(2)
        for i in range(64):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setStyleSheet(f"background-color: {self.colors[0][0]}; border: 1px solid #222;")
            btn.clicked.connect(lambda checked, idx=i: self.cycle_color(idx))
            self.grid_layout.addWidget(btn, i // 8, i % 8)
            self.buttons.append(btn)
        layout.addWidget(grid_widget)

        controls = QHBoxLayout()
        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self.clear_grid)
        btn_clear.setStyleSheet("background-color: #f44336; color: white; min-height: 40px;")

        btn_save = QPushButton("Save Pattern")
        btn_save.clicked.connect(self.save_current_pattern)
        btn_save.setStyleSheet("background-color: #2196F3; color: white; min-height: 40px;")

        btn_ok = QPushButton("Send to Drone")
        btn_ok.clicked.connect(self.accept_pattern)
        btn_ok.setStyleSheet("background-color: #4CAF50; color: white; min-height: 40px;")

        controls.addWidget(btn_clear);
        controls.addWidget(btn_save);
        controls.addWidget(btn_ok)
        layout.addLayout(controls)
        self.setLayout(layout)
        self.setStyleSheet("background-color: #1a2a44;")

    def cycle_color(self, idx):
        self.grid_state[idx] = (self.grid_state[idx] + 1) % 4
        self.update_button_style(idx)

    def update_button_style(self, idx):
        color_hex = self.colors[self.grid_state[idx]][0]
        self.buttons[idx].setStyleSheet(f"background-color: {color_hex}; border: 1px solid #222;")

    def clear_grid(self):
        for i in range(64):
            self.grid_state[i] = 0
            self.update_button_style(i)

    def save_current_pattern(self):
        PatternDialog.last_saved_state = list(self.grid_state)
        self.btn_load_saved.setEnabled(True)

    def load_saved_pattern(self):
        if PatternDialog.last_saved_state is not None:
            self.grid_state = list(PatternDialog.last_saved_state)
            for i in range(64): self.update_button_style(i)

    def accept_pattern(self):
        self.pattern_string = "".join([self.colors[state][1] for state in self.grid_state])
        self.accept()


# --- MAIN UI PANEL ---
class TelloFullPanel(QWidget):
    def __init__(self, worker, status_thread, video_thread):
        super().__init__()
        self.worker = worker
        self.status_thread = status_thread
        self.video_thread = video_thread
        self.last_frame = None

        self.photo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
        if not os.path.exists(self.photo_dir):
            os.makedirs(self.photo_dir)

        self.initUI()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def initUI(self):
        self.setWindowTitle('Tello Command Center')
        self.setMinimumWidth(1200)
        self.setMinimumHeight(800)

        self.setStyleSheet("""
            QWidget { background-color: #1a2a44; }
            QPushButton { background-color: #e0e0e0; border: 1px solid #999; font-weight: bold; min-height: 45px; border-radius: 4px; color: #333; font-size: 13px; padding: 4px; }
            QPushButton:pressed { background-color: #bbbbbb; }
            QLineEdit { background-color: white; border: 1px solid #999; border-radius: 4px; padding: 5px; color: black; font-weight: bold; min-height: 45px; font-size: 13px; }
            QLabel#Terminal { background-color: #000; color: #0f0; font-family: 'Courier New'; font-weight: bold; padding-left: 10px; border: 1px solid #334466; border-top-left-radius: 4px; border-bottom-left-radius: 4px; border-right: none; }
            QLabel#StatusBar { background-color: #0a1424; color: #fff; font-weight: bold; border: 1px solid #334466; border-top-right-radius: 4px; border-bottom-right-radius: 4px; }
            QLabel#VideoDisplay { background-color: #000; border: 2px solid #334466; border-radius: 4px; color: #555; font-size: 18px; font-weight: bold; }
            QLabel#VisualizerPlaceholder { background-color: #000; border: 1px solid #334466; color: #444; font-size: 14px; font-weight: bold; border-radius: 4px; }
            QSlider::groove:horizontal { border: 1px solid #999; height: 8px; background: white; margin: 2px 0; border-radius: 4px; }
            QSlider::handle:horizontal { background: #334466; border: 1px solid #555; width: 14px; height: 18px; margin: -6px 0; border-radius: 4px; }
        """)

        main_vbox = QVBoxLayout()
        main_vbox.setContentsMargins(15, 15, 15, 15)
        main_vbox.setSpacing(15)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)
        self.terminal_display = QLabel(" > Awaiting Commands...")
        self.terminal_display.setObjectName("Terminal")
        header_layout.addWidget(self.terminal_display, 1)

        self.status_bar = QFrame()
        self.status_bar.setObjectName("StatusBar")
        status_inner_layout = QHBoxLayout(self.status_bar)
        status_inner_layout.setContentsMargins(15, 0, 15, 0)
        status_inner_layout.setSpacing(20)
        self.lbl_bat, self.lbl_temp, self.lbl_speed, self.lbl_vid_status = QLabel("🔋 --%"), QLabel("🌡️ --°C"), QLabel(
            "⚡ --"), QLabel("📺 VIDEO: OFF")

        self.lbl_vid_status.setStyleSheet("color: #f44336; font-size: 13px; font-weight: bold;")
        for lbl in [self.lbl_bat, self.lbl_temp, self.lbl_speed, self.lbl_vid_status]:
            if lbl != self.lbl_vid_status:
                lbl.setStyleSheet("color: #00d4ff; font-size: 13px;")
            status_inner_layout.addWidget(lbl)

        header_layout.addWidget(self.status_bar)
        header_container = QWidget();
        header_container.setFixedHeight(45);
        header_container.setLayout(header_layout)
        main_vbox.addWidget(header_container)

        middle_layout = QHBoxLayout();
        middle_layout.setSpacing(15)
        self.video_display = QLabel("VIDEO OFF")
        self.video_display.setObjectName("VideoDisplay")
        self.video_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        middle_layout.addWidget(self.video_display, 6)

        # PANEL 1: MOVEMENT
        panel1_container = QFrame()
        panel1_layout = QGridLayout(panel1_container)
        panel1_layout.setContentsMargins(0, 0, 0, 0);
        panel1_layout.setSpacing(5)

        btn_move_data = [
            ('🚁 Takeoff (Space)', 0, 0, 'takeoff'), ('⬆️ Forward', 0, 1, 'forward 50'), ('🅿️ Land (L)', 0, 2, 'land'),
            ('⬅️ Left', 1, 0, 'left 50'), ('🚦 CMD', 1, 1, 'command'), ('➡️ Right', 1, 2, 'right 50'),
            ('👆 Up (W)', 2, 0, 'up 50'), ('⬇️ Back', 2, 1, 'back 50'), ('👇 Down (S)', 2, 2, 'down 50'),
            ('🔄 CCW (A)', 3, 0, 'ccw 90'), ('🔄 CW (D)', 3, 2, 'cw 90')
        ]
        for label, row, col, cmd in btn_move_data:
            btn = self.create_expanding_btn(label)
            btn.clicked.connect(lambda checked, c=cmd: self.send_cmd(c))
            panel1_layout.addWidget(btn, row, col)

        stack_layout = QVBoxLayout()
        btn_emergency = self.create_expanding_btn('🚨 EMERGENCY')
        btn_emergency.setStyleSheet("background-color: #d32f2f; color: white; min-height: 20px; font-size: 11px;")
        btn_emergency.clicked.connect(lambda: self.send_cmd('emergency'))
        btn_ml = self.create_expanding_btn('Start ML')
        btn_ml.setStyleSheet("background-color: #455a64; color: white; min-height: 20px; font-size: 11px;")
        stack_layout.addWidget(btn_emergency);
        stack_layout.addWidget(btn_ml)
        panel1_layout.addLayout(stack_layout, 3, 1)

        middle_layout.addWidget(panel1_container, 4)
        main_vbox.addLayout(middle_layout, 6)

        bottom_layout = QHBoxLayout();
        bottom_layout.setSpacing(15)

        # PANEL 2: LED CONTROLS
        panel2_container = QFrame()
        panel2_layout = QGridLayout(panel2_container)
        panel2_layout.setContentsMargins(0, 0, 0, 0);
        panel2_layout.setSpacing(5)

        led_btns = [
            ('🔴 Red', 0, 0, 'led 255 0 0'),
            ('🟢 Green', 0, 1, 'led 0 255 0'),
            ('🔵 Blue', 0, 2, 'led 0 0 255'),
            ('🔵 Pulse Blue', 1, 0, 'led 0 0 255 2'),
            ('⚫ Off', 1, 1, 'led 0 0 0'),
            ('🚔 POLICE!', 1, 2, 'led 255 0 0 5')
        ]
        for l, r, c, cmd in led_btns:
            btn = self.create_expanding_btn(l)
            btn.clicked.connect(lambda checked, cmd=cmd: self.send_cmd(cmd))
            panel2_layout.addWidget(btn, r, c)

        text_input_lay = QHBoxLayout()
        text_input_lay.setSpacing(5)
        self.input_text = QLineEdit("Hello")
        self.input_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn_text_send = self.create_expanding_btn("Send Text")
        btn_text_send.clicked.connect(lambda: self.send_cmd(f"EXT mled l b 1 {self.input_text.text()}"))
        text_input_lay.addWidget(self.input_text, 6);
        text_input_lay.addWidget(btn_text_send, 4)

        btn_pattern = self.create_expanding_btn("Pattern Designer")
        btn_pattern.setStyleSheet("background-color: #673AB7; color: white;")
        btn_pattern.clicked.connect(self.open_pattern_designer)

        panel2_layout.addLayout(text_input_lay, 2, 0, 1, 2)
        panel2_layout.addWidget(btn_pattern, 2, 2)

        # Spacer for 4th row to match Panel 1
        panel2_layout.addWidget(QLabel(""), 3, 0, 1, 3)

        bottom_layout.addWidget(panel2_container, 1)

        self.visualizer_placeholder = QLabel("GAMEPAD VISUALIZER")
        self.visualizer_placeholder.setObjectName("VisualizerPlaceholder")
        self.visualizer_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(self.visualizer_placeholder, 1)

        # PANEL 3: UTILITIES
        panel3_container = QFrame()
        panel3_layout = QGridLayout(panel3_container)
        panel3_layout.setContentsMargins(0, 0, 0, 0);
        panel3_layout.setSpacing(5)

        btn_on = self.create_expanding_btn("🥶 Motor ON")
        btn_off = self.create_expanding_btn("📴 Motor OFF")
        btn_on.clicked.connect(lambda: self.send_cmd('motoron'))
        btn_off.clicked.connect(lambda: self.send_cmd('motoroff'))

        panel3_layout.addWidget(btn_on, 0, 0)
        fwd_flip = self.create_expanding_btn("⬆️ Flip fwd")
        fwd_flip.clicked.connect(lambda: self.send_cmd('flip f'))
        panel3_layout.addWidget(fwd_flip, 0, 1)

        btn_photo = self.create_expanding_btn("📸 Take photo")
        btn_photo.clicked.connect(self.take_photo)
        panel3_layout.addWidget(btn_photo, 0, 2)

        flips = [("⬅️ Flip L", 1, 0, 'flip l'), ("🏈 ThrowFly", 1, 1, 'throwfly'), ("➡️ Flip R", 1, 2, 'flip r')]
        for lbl, r, c, cmd in flips:
            btn = self.create_expanding_btn(lbl)
            btn.clicked.connect(lambda chk, cmd=cmd: self.send_cmd(cmd))
            panel3_layout.addWidget(btn, r, c)

        btn_vid_on = self.create_expanding_btn("📺 Video ON")
        btn_vid_on.setStyleSheet("background-color: #4CAF50; color: white;")
        btn_vid_on.clicked.connect(self.video_on)
        panel3_layout.addWidget(btn_vid_on, 2, 0)

        back_flip = self.create_expanding_btn("⬇️ Flip back")
        back_flip.clicked.connect(lambda: self.send_cmd('flip b'))
        panel3_layout.addWidget(back_flip, 2, 1)

        btn_vid_off = self.create_expanding_btn("📺 Video OFF")
        btn_vid_off.setStyleSheet("background-color: #f44336; color: white;")
        btn_vid_off.clicked.connect(self.video_off)
        panel3_layout.addWidget(btn_vid_off, 2, 2)

        # Row 3: Speed Controls and Motor Off
        speed_widget = QWidget()
        speed_v_lay = QVBoxLayout(speed_widget)
        speed_v_lay.setContentsMargins(2, 2, 2, 2);
        speed_v_lay.setSpacing(0)
        speed_label = QLabel("Speed")
        speed_label.setStyleSheet("color: white; font-size: 10px;")
        speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setRange(10, 100)
        speed_slider.valueChanged.connect(lambda val: self.send_cmd(f'speed {val}'))
        speed_v_lay.addWidget(speed_label);
        speed_v_lay.addWidget(speed_slider)

        panel3_layout.addWidget(speed_widget, 3, 0, 1, 2)
        panel3_layout.addWidget(btn_off, 3, 2)

        bottom_layout.addWidget(panel3_container, 1)
        main_vbox.addLayout(bottom_layout, 4)
        self.setLayout(main_vbox)

    def create_expanding_btn(self, label):
        btn = QPushButton(label)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def handle_response(self, text):
        self.terminal_display.setText(f" > {text}")

    def handle_status_update(self, stats):
        if 'bat' in stats: self.update_stat_label('bat', stats['bat'])
        if 'templ' in stats and 'temph' in stats:
            avg_temp = (int(stats['templ']) + int(stats['temph'])) // 2
            self.update_stat_label('temp', str(avg_temp))

    def update_stat_label(self, stat_type, value):
        if stat_type == 'bat':
            self.lbl_bat.setText(f"🔋 {value}%")
        elif stat_type == 'temp':
            self.lbl_temp.setText(f"🌡️ {value}°C")
        elif stat_type == 'speed':
            self.lbl_speed.setText(f"⚡ {value}")
        elif stat_type == 'video':
            if value == "ON":
                self.lbl_vid_status.setText("📺 VIDEO: ON")
                self.lbl_vid_status.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
            else:
                self.lbl_vid_status.setText("📺 VIDEO: OFF")
                self.lbl_vid_status.setStyleSheet("color: #f44336; font-size: 13px; font-weight: bold;")

    def update_video_frame(self, q_img):
        self.last_frame = q_img
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.video_display.size(),
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.FastTransformation)
        self.video_display.setPixmap(scaled_pixmap)

    def send_cmd(self, cmd):
        self.worker.send(cmd)
        if cmd.startswith("speed"):
            try:
                self.update_stat_label('speed', cmd.split(" ")[1])
            except:
                pass

    def take_photo(self):
        if self.last_frame and not self.last_frame.isNull():
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"tello_photo_{timestamp}.png"
            filepath = os.path.join(self.photo_dir, filename)
            if self.last_frame.save(filepath, "PNG"):
                self.terminal_display.setText(f" > Photo saved: {filename}")
            else:
                self.terminal_display.setText(" > Error: Failed to save photo.")
        else:
            self.terminal_display.setText(" > Error: No video frame to capture.")

    def video_on(self):
        if not self.video_thread.isRunning():
            self.terminal_display.setText(" > Initializing Video Stream...")
            self.send_cmd('streamon')
            QTimer.singleShot(1500, self.video_thread.start)
            self.update_stat_label('video', "ON")

    def video_off(self):
        self.terminal_display.setText(" > Stopping Stream...")
        self.send_cmd('streamoff')
        self.video_thread.stop()
        self.video_display.clear()
        self.video_display.setText("VIDEO OFF")
        self.update_stat_label('video', "OFF")

    def open_pattern_designer(self):
        dialog = PatternDialog(self)
        if dialog.exec():
            self.send_cmd(f"EXT mled g {dialog.pattern_string}")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if isinstance(self.focusWidget(), QLineEdit):
            super().keyPressEvent(event)
            return
        commands = {
            Qt.Key.Key_Space: 'takeoff', Qt.Key.Key_L: 'land', Qt.Key.Key_0: 'emergency',
            Qt.Key.Key_Up: 'forward 50', Qt.Key.Key_Down: 'back 50', Qt.Key.Key_Left: 'left 50',
            Qt.Key.Key_Right: 'right 50', Qt.Key.Key_W: 'up 50', Qt.Key.Key_S: 'down 50',
            Qt.Key.Key_A: 'ccw 90', Qt.Key.Key_D: 'cw 90'
        }
        if key in commands:
            self.send_cmd(commands[key])
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.status_thread.stop()
        self.video_thread.stop()
        super().closeEvent(event)