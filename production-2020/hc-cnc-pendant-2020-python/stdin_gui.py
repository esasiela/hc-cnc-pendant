import sys
from threading import Thread
from PyQt5.QtWidgets import QApplication, QMainWindow, QFrame, QVBoxLayout
from hc_cnc_console import ConsoleFrame


class StdinGui:
    def __init__(self, application=None):
        self.application = application
        self.main_window = QMainWindow()
        self.console_frame = ConsoleFrame(title="Stdin")
        t = Thread(target=self.stdin_thread)
        t.daemon = True
        t.start()

    def create_gui(self):
        self.main_window.setWindowTitle("HC Stdin GUI")
        self.main_window.setMinimumWidth(500)

        main_frame = QFrame()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.console_frame)
        main_frame.setLayout(main_layout)

        self.main_window.setCentralWidget(main_frame)
        self.main_window.show()

    def stdin_thread(self):
        try:
            while True:
                line = sys.stdin.readline().rstrip()
                if line == "":
                    # print("stdin empty str")
                    if self.application is not None:
                        # print("stdin_thread telling application to exit")
                        self.application.quit()
                    break
                self.console_frame.log_text(line)
        except EOFError:
            # print("stdin EOF")
            pass
        # print("stdin_thread exiting")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    gui = StdinGui(application=app)

    gui.create_gui()

    ret = app.exec_()
    app.exit(ret)
