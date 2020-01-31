import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QFrame, QHBoxLayout, QVBoxLayout, QPushButton
from hc_cnc_console import ConsoleFrame


class StdoutGui:
    def __init__(self):
        self.text_input = QLineEdit()
        self.main_window = QMainWindow()
        self.console_frame = ConsoleFrame(title="Stdout")

    def create_gui(self):
        self.main_window.setWindowTitle("HC Stdout GUI")
        self.main_window.setMinimumWidth(500)

        top_frame = QFrame()
        top_frame.setFrameStyle(QFrame.StyledPanel)
        top_layout = QHBoxLayout()

        top_layout.addWidget(self.text_input)
        button = QPushButton("Send")
        # pay attention to "click" vs "clicked" to make this work right
        # connect the ENTER key signal to the button.click slot
        self.text_input.returnPressed.connect(button.click)
        # connect the button.clicked signal to my own slot
        button.clicked.connect(self.click_send)

        top_layout.addWidget(button)
        top_frame.setLayout(top_layout)

        main_frame = QFrame()
        main_layout = QVBoxLayout()
        main_layout.addWidget(top_frame)
        main_layout.addWidget(self.console_frame)
        main_frame.setLayout(main_layout)

        self.main_window.setCentralWidget(main_frame)
        self.main_window.show()

    def click_send(self):
        text = self.text_input.text()
        print(text, flush=True)
        self.console_frame.log(text)
        self.text_input.setText("")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    gui = StdoutGui()

    gui.create_gui()

    ret = app.exec_()
    app.exit(ret)
