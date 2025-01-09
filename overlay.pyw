import sys
import logging
from datetime import datetime, timezone
import traceback
import os
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QColor, QPainter, QBrush, QRadialGradient, QKeySequence
from PyQt5.QtWidgets import QApplication, QWidget, QShortcut
import win32gui
import atexit
import signal
import time
from check_instance import is_script_already_running

def setup_logging():
    try:
        home_dir = os.path.expanduser('~')
        log_dir = os.path.join(home_dir, 'AppData', 'Local', 'Overlay')
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'overlay_{timestamp}.log')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] '
            '%(message)s - line %(lineno)d in %(funcName)s'
        )
        file_handler.setFormatter(formatter)
        
        logger = logging.getLogger('OverlayLogger')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        
        logger.info(f"Current Date and Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Current User's Login: {os.getlogin()}")
        
        return logger
    except Exception as e:
        print(f"Failed to setup logging: {e}")
        return logging.getLogger('fallback')

# Create logger instance
logger = setup_logging()

# Check for existing instance
if is_script_already_running('overlay.py'):
    logger.warning("Another instance is already running. Exiting.")
    sys.exit(0)

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("Initializing Overlay")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
        screen = QApplication.desktop()
        screen_size = f"{screen.width()}x{screen.height()}"
        logger.info(f"Screen size: {screen_size}")
        
        self.setGeometry(0, 0, screen.width(), screen.height())
        self.active_window_rect = QRect()
        self.is_desktop_active = False
        self.force_hidden = False
        self.last_window_hwnd = None
        self.last_update_time = time.time()
        self.update_count = 0
        self.last_error_time = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_active_window)
        self.timer.start(100)

        self.shortcut = QShortcut(QKeySequence('Ctrl+Shift+/'), self)
        self.shortcut.activated.connect(toggle_overlay)

    def update_active_window(self):
        try:
            current_time = time.time()
            
            if current_time - self.last_update_time < 0.1:
                return
            
            self.last_update_time = current_time
            self.update_count += 1
            
            if self.update_count % 100 == 0:
                logger.debug(f"Update count: {self.update_count}, Force hidden: {self.force_hidden}")

            if self.force_hidden:
                return

            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    window_text = win32gui.GetWindowText(hwnd)
                    window_class = win32gui.GetClassName(hwnd)

                    if hwnd != self.last_window_hwnd:
                        logger.info(f"Window transition - Class: {window_class}, "
                                  f"Title: {window_text}, HWND: {hwnd}")
                        logger.debug(f"Window rect: {rect}")

                    if not rect or rect[2] <= rect[0] or rect[3] <= rect[1]:
                        logger.warning(f"Invalid window rectangle: {rect}")
                        return

                    system_windows = [
                        "Program Manager",
                        "Windows.UI.Core.CoreWindow",
                        "Shell_TrayWnd",
                        "Shell_SecondaryTrayWnd",
                        "Progman",
                        "WorkerW",
                    ]

                    if window_class in system_windows or window_text in system_windows:
                        logger.debug(f"System window detected: {window_class} - {window_text}")
                        self.hide()
                        self.last_window_hwnd = None  # Forget the last window when desktop is clicked
                    else:
                        self.active_window_rect = QRect(rect[0], rect[1], 
                                                      rect[2] - rect[0], 
                                                      rect[3] - rect[1])
                        
                        if hwnd != self.last_window_hwnd:
                            self.show()
                            self.last_window_hwnd = hwnd
                        
                    self.update()

                except Exception as e:
                    current_error_time = time.time()
                    if current_error_time - self.last_error_time > 1:
                        logger.error(f"Window info error: {e}\n{traceback.format_exc()}")
                        self.last_error_time = current_error_time
                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"Critical error in update_active_window: {e}\n{traceback.format_exc()}")
            time.sleep(0.1)

    def paintEvent(self, event):
        try:
            current_time = time.time()
            
            if hasattr(self, 'last_paint_time') and \
               current_time - self.last_paint_time < 0.05:
                return
                
            self.last_paint_time = current_time
            
            if hasattr(self, 'paint_count'):
                self.paint_count += 1
            else:
                self.paint_count = 1
                
            if self.paint_count % 100 == 0:
                logger.debug(f"Paint count: {self.paint_count}")

            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            painter.setBrush(QBrush(QColor(0, 0, 0, 235)))
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.rect())

            vignette_radius = max(self.rect().width(), self.rect().height()) * 0.75
            vignette_gradient = QRadialGradient(self.rect().center(), vignette_radius)
            vignette_gradient.setColorAt(0.7, QColor(0, 0, 0, 0))
            vignette_gradient.setColorAt(1, QColor(0, 0, 0, 180))

            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setBrush(QBrush(vignette_gradient))
            painter.drawRect(self.rect())

            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.drawRect(self.active_window_rect)
            
        except Exception as e:
            logger.error(f"Paint error: {e}\n{traceback.format_exc()}")

    def cleanup(self):
        logger.info("Cleaning up overlay")
        logger.info(f"Final update count: {self.update_count}")
        logger.info(f"Final paint count: {getattr(self, 'paint_count', 0)}")
        self.timer.stop()
        self.hide()
        self.deleteLater()

def toggle_overlay():
    try:
        if overlay.isVisible():
            logger.info("Manually hiding overlay")
            overlay.hide()
            overlay.force_hidden = True
        else:
            logger.info("Manually showing overlay")
            overlay.force_hidden = False
            overlay.last_window_hwnd = None
            overlay.update_active_window()
    except Exception as e:
        logger.error(f"Toggle error: {e}\n{traceback.format_exc()}")

def cleanup():
    logger.info("Performing global cleanup")
    try:
        overlay.cleanup()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}")
    cleanup()
    sys.exit(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = Overlay()

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        overlay.show()
        app.exec_()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}\n{traceback.format_exc()}")
    finally:
        cleanup()
