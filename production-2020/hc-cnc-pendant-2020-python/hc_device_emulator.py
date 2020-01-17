from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

from hc_cnc_pendant_2020 import ConsoleFrame


class EmuLed(QWidget):
    def __init__(self, parent=None, emu=None, color_on=(255, 255, 255), color_off=(0, 0, 0), diameter=5, move_to=None):
        super(EmuLed, self).__init__(parent)
        self.emu = emu
        self.color_on = color_on
        self.color_off = color_off
        self.diameter = diameter
        self.led_on = False

        self.resize(self.diameter, self.diameter)
        self.setMask(QRegion(self.rect(), QRegion.Ellipse))

        if move_to is not None:
            self.move(move_to[0], move_to[1])

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)

        # draw the LED portion
        if self.led_on:
            color = self.color_on
        else:
            color = self.color_off

        qp.setBrush(QBrush(QColor(color[0], color[1], color[2]), Qt.SolidPattern))
        qp.drawEllipse(0, 0, self.diameter, self.diameter)

        qp.end()


class EmuButton(QWidget):
    def __init__(self, parent=None, emu=None, color=(0, 0, 0), diameter=10, move_to=None, button_num=-1):
        super(EmuButton, self).__init__(parent)
        self.emu = emu
        self.button_num = button_num
        self.color = color
        self.diameter = diameter
        self.resize(self.diameter + 2, self.diameter + 2)
        self.setMask(QRegion(self.rect(), QRegion.Ellipse))
        if move_to is not None:
            self.move(move_to[0], move_to[1])

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        qp.setBrush(QBrush(QColor(self.color[0], self.color[1], self.color[2]), Qt.SolidPattern))
        if self.underMouse():
            qp.setPen(QColor(255, 255, 255))
        qp.drawEllipse(1, 1, self.diameter, self.diameter)
        qp.end()

    def enterEvent(self, event):
        self.repaint()
        return super(EmuButton, self).enterEvent(event)

    def leaveEvent(self, event):
        self.repaint()
        return super(EmuButton, self).leaveEvent(event)

    def mousePressEvent(self, event):
        self.emu.button_press(self.button_num)


class EmuLedButton(EmuButton):
    def __init__(self, parent=None, emu=None, color=(0, 0, 0), diameter=10, move_to=None, button_num=-1, color_off=(0, 0, 0)):
        super(EmuLedButton, self).__init__(parent, emu, color, diameter, move_to, button_num)
        self.color_on = color
        self.color_off = color_off
        self.led_on = False

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)

        # draw the LED portion
        if self.led_on:
            color = self.color_on
        else:
            color = self.color_off

        qp.setBrush(QBrush(QColor(color[0], color[1], color[2]), Qt.SolidPattern))
        if self.underMouse():
            qp.setPen(QColor(255, 255, 255))
        qp.drawEllipse(1, 1, self.diameter, self.diameter)

        # draw the inner silver button portion
        qp.setBrush(QBrush(QColor(190, 190, 190), Qt.SolidPattern))

        #if self.underMouse():
        #    qp.setPen(QColor(255, 255, 255))
        qp.drawEllipse(6, 6, self.diameter-10, self.diameter-10)

        qp.end()

    def mousePressEvent(self, event):
        # update the size selector
        self.emu.button_press(self.button_num)


class ClientMsgComm(QObject):
    """
    ClientMsgComm is used to send Qt signal to PendantEmu for updates to LEDs on unit size and Job Notify
    """
    signal = pyqtSignal(bytearray)


class PendantEmulator(QFrame):
    """
    Widget that emulates the client device half of the HC Pendant 2020 system.
    GUI looks like the device.
    Instead of serial messages, we just put them on the message queue of the main
    pendant host application.
    """
    def __init__(self, parent=None, pendant=None):
        QFrame.__init__(self, parent)
        self.pendant = pendant

        self.log_console = ConsoleFrame(title="Emu Log", pendant=self.pendant, show_border=False)

        self.client_msg_comm = ClientMsgComm()
        self.client_msg_comm.signal.connect(self.process_client_msg_comm_signal)

        self.msg_start_byte = 0x03
        self.jog_unit_selector = 21
        self.jog_size_selector = 13

        self.led_buttons = []

        self.setFrameStyle(QFrame.StyledPanel)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        content_frame = QFrame()
        # content_frame.setFrameStyle(QFrame.StyledPanel)
        content_layout = QVBoxLayout()
        # content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.addWidget(QLabel(self.pendant.config["gui_frame_emu_title"]))

        image_widget = QWidget()

        image_layout = QVBoxLayout()
        image_layout.setContentsMargins(0, 0, 0, 0)

        image_label = QLabel()
        pixmap = QPixmap(self.pendant.config["gui_frame_emu_image"])
        image_label.setPixmap(pixmap)
        image_layout.addWidget(image_label)

        # RED - stop
        EmuButton(image_label, emu=self, diameter=21, color=(255, 0, 0), move_to=(41, 34), button_num=6)
        # WHITE - G28, G30, GotoXY
        EmuButton(image_label, emu=self, diameter=21, color=(255, 255, 255), move_to=(41, 81), button_num=11)
        EmuButton(image_label, emu=self, diameter=21, color=(255, 255, 255), move_to=(41, 127), button_num=10)
        EmuButton(image_label, emu=self, diameter=21, color=(255, 255, 255), move_to=(41, 174), button_num=9)
        # YELLOW - x and y axis jog
        EmuButton(image_label, emu=self, diameter=21, color=(233, 237, 12), move_to=(104, 146), button_num=0)
        EmuButton(image_label, emu=self, diameter=21, color=(233, 237, 12), move_to=(188, 146), button_num=1)
        EmuButton(image_label, emu=self, diameter=21, color=(233, 237, 12), move_to=(146, 174), button_num=2)
        EmuButton(image_label, emu=self, diameter=21, color=(233, 237, 12), move_to=(146, 118), button_num=3)
        # GREEN - z axis jog
        EmuButton(image_label, emu=self, diameter=21, color=(37, 200, 10), move_to=(247, 174), button_num=4)
        EmuButton(image_label, emu=self, diameter=21, color=(37, 200, 10), move_to=(247, 118), button_num=5)
        # BLUE - zztop and probe
        EmuButton(image_label, emu=self, diameter=21, color=(0, 0, 200), move_to=(317, 174), button_num=8)
        EmuButton(image_label, emu=self, diameter=21, color=(0, 0, 200), move_to=(317, 118), button_num=12)
        # BLACK - notify
        EmuButton(image_label, emu=self, diameter=21, color=(44, 44, 44), move_to=(317, 63), button_num=7)

        # LED buttons
        self.led_buttons.append(EmuLedButton(image_label, emu=self, diameter=27, color=(0, 255, 68),
                                             color_off=(1, 71, 20), move_to=(100, 60), button_num=13))
        self.led_buttons.append(EmuLedButton(image_label, emu=self, diameter=27, color=(0, 255, 68),
                                             color_off=(1, 71, 20), move_to=(172, 60), button_num=14))
        self.led_buttons.append(EmuLedButton(image_label, emu=self, diameter=27, color=(0, 255, 68),
                                             color_off=(1, 71, 20), move_to=(244, 60), button_num=15))

        # this is a funny way of setting default, but it forces an update of the LED buttons, which I want
        self.set_jog_size(self.jog_size_selector)

        # Notify LED indicator
        self.notify_led = EmuLed(image_label, emu=self, diameter=9, color_on=(0, 255, 68),
                                 color_off=(1, 71, 20), move_to=(325, 37))

        image_layout.addWidget(self.log_console)

        image_layout.addStretch()
        image_widget.setLayout(image_layout)

        content_layout.addWidget(image_widget)
        content_frame.setLayout(content_layout)

        layout.addWidget(content_frame)
        self.setLayout(layout)

    def log(self, msg):
        self.log_console.log(msg)

    def button_press(self, button_num):
        self.pendant.add_msg(bytearray([self.msg_start_byte, button_num, self.jog_unit_selector]))

    def set_jog_size(self, jog_size):
        self.jog_size_selector = jog_size

        for led_button in self.led_buttons:
            led_button.led_on = (led_button.button_num == jog_size)
            led_button.repaint()

    def set_notify_led(self, is_on):
        self.notify_led.led_on = is_on
        self.notify_led.repaint()

    def process_client_msg_comm_signal(self, msg):
        """
        This guy runs in the Qt GUI thread
        :param msg: bytearray message received from the Pendant application
        :return: nothing
        """
        if msg[0] != 0x03:
            self.log("signal proc - invalid start byte, skipping")
            return

        if msg[1] == 0x01:
            # jog size setting, expecting 13-15 as value
            idx = msg[2]
            self.log("signal proc - jog size - " + str(idx))
            self.set_jog_size(idx)
        elif msg[1] == 0x02:
            # job notify setting, data value TBD
            self.log("signal proc - job notify - data TBD")

    def pendant_client_name(self):
        return "emulator"

    def pendant_client_msg(self, msg):
        self.log("pendant_client_msg - " + str(msg))
        self.client_msg_comm.signal.emit(msg)
