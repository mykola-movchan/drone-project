import pygame
import time
from PyQt6.QtCore import QThread, pyqtSignal


class GamepadWorker(QThread):
    """
    Independent worker thread for polling Gamepad data.
    Separating this prevents the UI from lagging while waiting for hardware events.
    """
    command_signal = pyqtSignal(str)
    axis_signal = pyqtSignal(list)  # [left_x, left_y, right_x, right_y]

    def __init__(self):
        super().__init__()
        self.running = False
        pygame.init()
        pygame.joystick.init()
        self.joystick = None

    def run(self):
        self.running = True

        # Initialize the first available joystick
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

        last_cmd_time = 0

        while self.running:
            pygame.event.pump()  # Process internal pygame event queue

            if self.joystick:
                # Xbox Series Controller Mapping
                # Sticks (Axes)
                lx = self.joystick.get_axis(0)  # Left Stick X
                ly = self.joystick.get_axis(1)  # Left Stick Y
                rx = self.joystick.get_axis(2)  # Right Stick X
                ry = self.joystick.get_axis(3)  # Right Stick Y

                # Emit raw axis data for the UI visualizer
                self.axis_signal.emit([lx, ly, rx, ry])

                # Buttons
                # A (0), B (1), X (2), Y (3), Menu (7)
                if self.joystick.get_button(0):
                    self.command_signal.emit("takeoff")
                if self.joystick.get_button(1):
                    self.command_signal.emit("land")
                if self.joystick.get_button(7):
                    self.command_signal.emit("emergency")

                # Movement Command Throttling (Don't flood the Tello with 100pkts/sec)
                now = time.time()
                if now - last_cmd_time > 0.3:
                    # Deadzone check (0.2)
                    if abs(ly) > 0.2:
                        cmd = f"{'back' if ly > 0 else 'forward'} {int(abs(ly) * 100)}"
                        self.command_signal.emit(cmd)
                    if abs(lx) > 0.2:
                        cmd = f"{'right' if lx > 0 else 'left'} {int(abs(lx) * 100)}"
                        self.command_signal.emit(cmd)
                    last_cmd_time = now

            self.msleep(10)  # 100Hz polling rate

    def stop(self):
        self.running = False
        self.wait()