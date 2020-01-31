from threading import Thread, Condition
import requests
from queue import Queue
# from enum import Enum, auto
import serial.tools.list_ports
import serial
import sys
from datetime import datetime, timedelta, date, time
import configparser

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QHBoxLayout, \
    QRadioButton, QGridLayout,  QCheckBox, QDesktopWidget, QMainWindow, QTabWidget

from hc_observable import ThreadedObserver
from hc_device_emulator import PendantEmulator
from hc_cnc_console import ConsoleFrame, StdinFrame
from hc_cnc_notify import NotifyFrame, NotifyManager
from hc_cnc_constants import LogTypes, JobStates


def rgb_from_config(color_str="0,0,0"):
    return [int(c) for c in color_str.split(',')]


class SerialConnectionWidget(QFrame):
    """
    Widget to let user see available serial comm ports and manage the connection.
    """
    def __init__(self, parent=None, pendant=None):
        QFrame.__init__(self, parent)

        # tell the pendant object that I want to know about serial connection changes
        pendant.observe_serial_connection(self)

        self.setFrameStyle(QFrame.StyledPanel)

        self.pendant = pendant
        self.port_combobox = None
        self.connect_button = None

        layout = QVBoxLayout()
        layout.addWidget(QLabel(self.pendant.config["gui_frame_serial_title"]))

        port_frame = QWidget()
        port_layout = QHBoxLayout()

        self.port_combobox = QComboBox()
        self.click_refresh()
        port_layout.addWidget(self.port_combobox)

        port_refresh_button = QPushButton(self.pendant.config["gui_frame_serial_refresh"])
        port_refresh_button.clicked.connect(self.click_refresh)
        port_layout.addWidget(port_refresh_button)

        port_layout.setContentsMargins(0, 0, 0, 0)
        port_frame.setLayout(port_layout)

        # connect_frame = QWidget()
        # connect_layout = QHBoxLayout()
        self.connect_button = QPushButton(self.pendant.config["gui_frame_serial_connect"])
        self.connect_button.clicked.connect(self.click_connect)
        # connect_layout.addWidget(self.connect_button)
        # connect_layout.setContentsMargins(0, 0, 0, 0)
        # connect_frame.setLayout(connect_layout)

        layout.addWidget(port_frame)
        # layout.addWidget(connect_frame)
        layout.addWidget(self.connect_button)
        self.setLayout(layout)

    def serial_connection_event(self, debug=False):
        if debug:
            self.pendant.log("serial widget - handling serial connection event")

        if self.pendant.is_serial_connected():
            self.connect_button.setText(self.pendant.config["gui_frame_serial_disconnect"])
        else:
            self.connect_button.setText(self.pendant.config["gui_frame_serial_connect"])

    def click_refresh(self):
        if self.port_combobox is not None:
            self.port_combobox.clear()
            for p in serial.tools.list_ports.comports():
                self.port_combobox.addItem(str(p))

    def click_connect(self):
        # self.pendant.log("clicked connect [" + self.port_combobox.currentText() + "]")
        if self.pendant.is_serial_connected():
            self.pendant.serial_disconnect()
            # self.connect_button.setText("Connect")
        else:
            self.pendant.serial_connect(self.port_combobox.currentText().split(" ")[0])
            # if self.pendant.is_serial_connected():
            #    self.connect_button.setText("Disconnect")


class ProbeComboBox(QComboBox):
    def __init__(self, parent=None, pendant=None, key_prefix=None):
        QComboBox.__init__(self, parent)
        self.pendant = pendant
        self.key_prefix = key_prefix
        self.load_items()

    def load_items(self):
        for k, v in self.pendant.config.items():
            if k.startswith(self.key_prefix) and k.endswith("_name"):
                # we have a name key.  also need the matching mm key
                try:
                    name = v
                    mm = self.pendant.config.get(k.replace("_name", "_mm"))
                    if mm is None:
                        raise KeyError()

                    self.addItem(name + " (" + str(mm) + " mm)", mm)
                except KeyError:
                    self.pendant.log("config error for " + self.key_prefix + ", skipping")


class ProbeFrame(QFrame):
    """
    Widget to manage the axis probe macros.  Spends most of its life in Z axis, with the occasional
    XY when I use a custom fixture rather than the standard bumpstop zero'ed on G28.
    """
    def __init__(self, parent=None, pendant=None):
        QFrame.__init__(self, parent)
        self.pendant = pendant

        self.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(self.pendant.config["gui_frame_probe_title"]))

        plate_frame = QFrame()
        plate_layout = QHBoxLayout()
        plate_layout.setContentsMargins(0, 0, 0, 0)
        plate_layout.addWidget(QLabel("Touch plate:"))
        self.plate_combobox = ProbeComboBox(pendant=self.pendant, key_prefix="probe_plate")
        self.plate_combobox.currentIndexChanged.connect(self.change_plate_selection)
        self.change_plate_selection(1)
        plate_layout.addWidget(self.plate_combobox)
        plate_layout.addStretch()
        plate_frame.setLayout(plate_layout)

        layout.addWidget(plate_frame)

        grid_frame = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)

        rb = QRadioButton("Z")
        rb.axis = "Z"
        rb.setChecked(True)
        rb.toggled.connect(self.change_axis_selection)
        grid_layout.addWidget(rb, 0, 0)

        rb = QRadioButton("X")
        rb.axis = "X"
        rb.toggled.connect(self.change_axis_selection)
        grid_layout.addWidget(rb, 0, 1)

        rb = QRadioButton("Y")
        rb.axis = "Y"
        rb.toggled.connect(self.change_axis_selection)
        grid_layout.addWidget(rb, 0, 2)

        self.tool_combobox = ProbeComboBox(pendant=self.pendant, key_prefix="probe_tool")
        self.tool_combobox.currentIndexChanged.connect(self.change_tool_selection)
        self.change_tool_selection(1)

        grid_layout.addWidget(QLabel("Select Tool for X/Y:"), 1, 1, 1, 2)
        grid_layout.addWidget(self.tool_combobox, 2, 1, 1, 2)

        grid_frame.setLayout(grid_layout)

        layout.addWidget(grid_frame)

        self.setLayout(layout)

    def change_axis_selection(self):
        rb: QRadioButton = self.sender()
        if rb.isChecked():
            # if debug:
            #    self.pendant.log("probe axis selection changed: " + rb.axis)
            self.pendant.probe_axis = rb.axis

    def change_tool_selection(self, i, debug=False):
        if debug:
            self.pendant.log("probe tool selection changed: text[" + self.tool_combobox.currentText() + "] data[" +
                             str(self.tool_combobox.currentData()) + "]")
        self.pendant.probe_tool_mm = self.tool_combobox.currentData()

    def change_plate_selection(self, i, debug=False):
        if debug:
            self.pendant.log("probe plate selection changed: text[" + self.plate_combobox.currentText() + "] data[" +
                             str(self.plate_combobox.currentData()) + "]")
        self.pendant.probe_plate_mm = self.plate_combobox.currentData()


class SerialClientMsgSender:
    """
    Class used to pass client messages generated by the Pendant application to the serial
    device.
    """
    def __init__(self, pendant=None):
        self.pendant = pendant

    @staticmethod
    def pendant_client_name():
        return "serial"

    def pendant_client_msg(self, msg):
        """
        Sends the message to the client over the Pendant's serial connection
        :param msg: bytearray(3) the message data to send
        :return: nothing
        """
        self.pendant.serial_port.write(msg)
        self.pendant.serial_port.flush()


class Pendant(ThreadedObserver):
    def __init__(self, config=None, **kwargs):
        super().__init__(**kwargs)

        self.config = config
        self.notify_manager = NotifyManager(config=config)
        self.notify_manager.add_observer(self)

        self.log_object = None
        self.gcode_log = None
        self.serial_port = None
        self.serial_thread = None
        self.serial_observers = []

        self.stdin_line_queue = Queue()
        stdin_thread = Thread(target=self.thread_stdin)
        stdin_thread.daemon = True
        stdin_thread.start()

        self.alive = True
        self.alive_lock = Condition()
        self.log_lock = Condition()
        self.gcode_log_lock = Condition()

        self.client_msg_queue = Queue()
        self.client_msg_receivers = []
        self.client_msg_thread = Thread(target=self.thread_client_msg)
        self.client_msg_thread.daemon = True
        self.client_msg_thread.start()

        self.msg_queue = Queue()
        self.msg_thread = Thread(target=self.thread_msg)
        self.msg_thread.daemon = True
        self.msg_thread.start()

        self.jog_size_index = 13

        self.probe_axis = "Z"
        self.probe_tool_mm = None
        self.probe_plate_mm = None

        self.gcode_sender_enable = True
        self.gcode_sender_name = 'bcnc'

    def __del__(self):
        if self.alive:
            print("destructor - alive=True, initiating shutdown...")
            self.shutdown()

    def shutdown(self):
        print("shutdown - setting 'alive' to False")
        self.alive_lock.acquire()
        self.alive = False
        self.alive_lock.notify_all()
        self.alive_lock.release()

        print("shutdown - serial_disconnect")
        self.serial_disconnect()

        print("shutdown - done")

    def observable_update(self, o):
        """
        Handles updates to any observables that we registered to watch.
        1) NotifyManager - let clients (device, emu) know when notify changes state (LED display)
        :param o: the observable that changed
        :return: nothing
        """
        if isinstance(o, NotifyManager):
            # the NotifyManager changed state, let the clients (device,emu) know
            self.send_job_notify()

    def add_msg(self, msg):
        self.msg_queue.put(msg)

    def log(self, text, msg_type=None, stamp=False):
        self.log_lock.acquire()
        t = text
        if stamp:
            # prepend a timestamp
            t = str(datetime.now()).split('.')[0] + " " + t

        if self.alive:
            self.log_object.log(t, msg_type)
        else:
            print(t)
        self.log_lock.release()

    def log_gcode(self, gcode):
        self.gcode_log_lock.acquire()
        # no need to do a similar "alive" check as the console log, we don't care about logging gcode in...
        # ...bizarre circumstances
        self.gcode_log.log(gcode)
        self.gcode_log_lock.release()

    def add_client_msg_receiver(self, receiver):
        self.client_msg_receivers.append(receiver)

        # always notify new receivers of the current jog size and job notify status
        self.send_jog_size()
        self.send_job_notify()

    def remove_client_msg_receiver(self, receiver_name, debug=False):
        if debug:
            self.log("remove_client_msg_rec(" + receiver_name + ") list size before " +
                     str(len(self.client_msg_receivers)))

        self.client_msg_receivers[:] = [rec for rec in self.client_msg_receivers
                                        if rec.pendant_client_name() != "serial"]

        if debug:
            self.log("remove_client_msg_rec(" + receiver_name + ") list size after " +
                     str(len(self.client_msg_receivers)))

    def set_jog_size(self, new_size):
        self.jog_size_index = new_size
        self.send_jog_size()

    def send_job_notify(self):
        """
        Inform any clients (device, emulator) that we have a change in notify state, so they
        may update their green LED.
        This method does NOT send the text/email, that is done by NotifyManager.operator_notice()
        :return: nothing
        """
        # start byte, 0x01=jog size (and 0x02=notify), notify data TBD
        self.send_client_msg(bytearray([0x03, 0x02, self.notify_manager.notify_state]))

    def send_jog_size(self):
        # start byte, 0x01=jog size (and 0x02=notify), index is 13-15 which client will map to the right LED
        self.send_client_msg(bytearray([0x03, 0x01, self.jog_size_index]))

    def send_client_msg(self, msg):
        """
        Put the client_msg onto the queue and the daemon thread will get() it and send to registered clients.
        :param msg: the byte message to send to the clients (device, emu)
        :return: nothing
        """
        self.client_msg_queue.put(msg)

    def thread_client_msg(self, debug=False):
        while True:
            msg = self.client_msg_queue.get()
            for receiver in self.client_msg_receivers:
                if debug:
                    self.log("thread_client_msg - sending msg " + str(bytearray([msg[1]])) + " to - " +
                             receiver.pendant_client_name())
                receiver.pendant_client_msg(msg)

    def thread_stdin(self, debug=True):
        while True:
            line = self.stdin_line_queue.get()
            if debug:
                self.log("stdin [" + line + "]")
            # parse the line, expecting it is bCNC output
            if line == self.config[self.gcode_sender_name + "_stdin_start"]: #Controller state changed to: Run (Running: True)":
                self.log("gcode job started", stamp=True)
                self.notify_manager.set_job_state(JobStates.RUNNING)
            elif line == self.config[self.gcode_sender_name + "_stdin_stop"]: #Controller state changed to: Idle (Running: False)":
                self.notify_manager.set_job_state(JobStates.IDLE)
                self.log("gcode job ended", stamp=True)

    def observe_serial_connection(self, observer):
        """
        When a serial connection event occurs (conn/disco), we will notify any observers via their
        serial_connection_event() method.
        :param observer: object to be notified when serial connection event occurs
        :return: nothing
        """
        self.serial_observers.append(observer)

    def fire_serial_connection_event(self):
        """
        Internal method for notifying observers that our serial connection state changed
        :return: nothing
        """
        for observer in self.serial_observers:
            observer.serial_connection_event()

    def serial_connect(self, port_name):
        # if self.serial_port is None or not self.serial_port.isOpen():
        if not self.is_serial_connected():
            self.log("connecting to serial port [" + port_name + "]")
            try:
                self.serial_port = serial.Serial(port=port_name, timeout=int(self.config["comm_read_timeout"]))
                self.log("connection status: " + str(self.serial_port.isOpen()))

                self.serial_thread = Thread(target=self.thread_serial_read)
                self.serial_thread.start()

                self.fire_serial_connection_event()

            except serial.SerialException as e:
                self.log("failed opening serial connection: " + e.strerror)
                self.serial_port = None
        else:
            self.log("not attempting to connect, port is already open")

    def serial_disconnect(self, join_thread=True):
        # self.log("serial_disconnect")

        # take the client message bridge off the list
        self.remove_client_msg_receiver("serial")

        if self.is_serial_connected():
            self.serial_port.close()
            self.log("serial_disconnect - serial port closed")
            self.fire_serial_connection_event()

        if join_thread and self.serial_thread is not None:
            # thread will shutdown when it sees connection closed
            self.log("serial_disconnect - joining reader thread")
            self.serial_thread.join()
            self.log("serial_disconnect - reader thread hath endeth")
        else:
            self.log("serial_disconnect - not join()'ing reader thread")

    def is_serial_connected(self):
        return self.serial_port is not None and self.serial_port.isOpen()

    def thread_serial_read(self, debug=False):
        while self.alive and self.is_serial_connected():
            try:
                # REMEMBER: when button 10 shows up, readline() treats that as LF, so splits the msg
                msg = self.serial_port.readline()

                if msg is None or len(msg) < 1:
                    if debug:
                        self.log("serial_read: read timed out, msg is none")
                else:
                    if debug:
                        self.log("serial_read: have a message, len " + str(len(msg)))

                    if msg[0] == 0x03:
                        # msg begins with 0x03 (ETX=start of text), real message
                        if debug:
                            self.log("serial_read: msg [" + str(msg) + "]", LogTypes.MSG)
                        self.add_msg(msg)
                    elif msg[0] == 21:
                        # 21 == 0x15 == NAK, this comes through as separate stupid message on button 10 press
                        if debug:
                            self.log("serial_read: ignoring button 10 line feed.")
                    else:
                        # msg doesnt begin with 0x03, debugging message
                        txt = msg.decode("utf-8").rstrip()
                        self.log("serial_read: txt [" + txt + "]", LogTypes.MSG)
                        if debug:
                            if msg[0] != 72:
                                for idx in range(len(msg)):
                                    self.log("  byte " + str(idx) + " [" + str(msg[idx]) + "]")

                        # special action on one specific string, startup "HC CNC PENDANT 2020"
                        if txt == self.config["serial_device_start_msg"]:
                            if debug:
                                self.log("serial device started, adding a msg bridge")

                            # put a connector on the list to map client messages to the client device
                            self.add_client_msg_receiver(SerialClientMsgSender(self))

            except (AttributeError, TypeError, serial.SerialException) as e:
                # most likely we disconnected while reading
                self.log("serial_read: error reading, did you disconnect?")
                self.serial_disconnect(join_thread=False)
        self.log("serial_read: end")

    def thread_msg(self, debug=False):
        while True:
            msg = self.msg_queue.get()

            # message bytes:
            #   0 : start of text : const 0x03
            #   1 : button num : 0-127 (really 0-15 for HC Pendant 2020)
            #   2 : mm/inch : 21/20 (always 21 for HC Pendant 2020, but keep it generic)
            #   OBSOLETE - fourth byte is no longer sent in Pendant 2020
            #   3 : jog size : 0=10.0, 1=01.0, 2=0.10

            # look up the type of button by button_num
            key_prefix = "btn_" + str(msg[1]) + "_"

            # if "stop" config key exists, we have a STOP button
            try:
                stop = self.config[key_prefix + "stop"]
                self.log("button " + str(msg[1]) + " - stop", LogTypes.MSG)
                self.send_cmd(stop)
            except KeyError:
                pass

            # if "notify" config key exists, we have a NOTIFY button
            try:
                notify = self.config[key_prefix + "notify"]
                self.log("button " + str(msg[1]) + " - notify", LogTypes.MSG)
                self.notify_manager.process_notify_button()
            except KeyError:
                pass

            # if "probe" config key exists, we have a PROBE button
            try:
                probe = self.config[key_prefix + "probe"]
                # we need:
                #  [AXIS] - X, Y, Z
                #  [DIR_FW] - Z probes negative so val is '-', XY probe positive so val is '' blank
                #  [DIR_BK] - opposite of DIR_FW, Z='', XY='-'
                #  [OFFSET_MM] - Z=plate_mm, XY=plate_mm+(tool_diameter/2)
                axis = self.probe_axis
                if axis == "Z":
                    dir_fw = "-"
                    dir_bk = ""
                    offset = str(self.probe_plate_mm)
                else:
                    dir_fw = ""
                    dir_bk = "-"
                    offset = str(float(self.probe_plate_mm) + float(self.probe_tool_mm) / 2)

                self.log("button " + str(msg[1]) + " - probe - axis[" + axis + "] dir_fw[" + dir_fw + "] dir_bk[" + dir_bk +
                         "] offset[" + offset + "]", LogTypes.MSG)

                gcode = self.config["probe_gcode"].replace("[AXIS]", axis)\
                    .replace("[DIR_FW]", dir_fw).replace("[DIR_BK]", dir_bk)\
                    .replace("[OFFSET_MM]", offset)

                self.send_gcode(gcode)

            except KeyError:
                pass

            # if "size" config key exists, we have a JOG_SIZE button
            try:
                new_size = self.config[key_prefix + "size"]
                self.log("button " + str(msg[1]) + "- jog_size [" + new_size + "]", LogTypes.MSG)

                # we don't send the size value, we send the size selector index
                self.set_jog_size(msg[1])
            except KeyError:
                pass

            # if "gcode" config key exists, we have straight gcode to send
            try:
                gcode = self.config[key_prefix + "gcode"]
                self.log("button " + str(msg[1]) + " - gcode [" + gcode + "]", LogTypes.MSG)
                self.send_gcode(gcode)
            except KeyError:
                pass

            # if "axis" config key exists, we have a jog instruction so form the gcode
            try:
                axis = self.config[key_prefix + "axis"]
                direction = self.config[key_prefix + "dir"]
                jog_unit = str(msg[2])

                # Jog Size is maintained here in the Pendant app, not by the message from the client
                # jog_size = self.config["jog_size_" + str(msg[3])]
                # self.log("jog_size_index " + str(self.jog_size_index), LogTypes.JOG)
                jog_size = self.config["btn_" + str(self.jog_size_index) + "_size"]
                self.log("button " + str(msg[1]) + " - jog [" + axis + direction + "] [" + jog_unit + "] [" +
                         jog_size + "]", LogTypes.MSG)

                gcode = self.config["jog_gcode_pattern"].replace("[JOG_UNIT]", jog_unit)\
                    .replace("[JOG_AXIS]", axis).replace("[JOG_DIR]", direction).replace("[JOG_SIZE]", jog_size)

                self.send_gcode(gcode)

            except KeyError:
                pass

    def send_gcode(self, gcode):
        """
        Send the gcode string to the URL of the config-specified gcode sender (i.e. bCNC)
        :param gcode: raw gcode string to send
        :return:
        """
        self.log_gcode(gcode)
        self.send_gcode_or_cmd("gcode", gcode)

    def send_cmd(self, cmd):
        """
        Send a non-gcode command to the URL of the config-specified gcode sender (i.e. bCNC)
        Mainly used for STOP command in bCNC
        :param cmd: raw command string to send
        :return:
        """
        self.log_gcode(cmd)
        self.send_gcode_or_cmd("cmd", cmd)

    def send_gcode_or_cmd(self, key, txt, debug=False):
        """
        Helper method, reuses the logic between gcode and cmd's
        :param key: "gcode" or "cmd"
        :param txt: the actual gcode or cmd string
        :type debug: True for verbose output
        :return: nothing
        """
        key_prefix = self.gcode_sender_name + "_" + key + "_"

        # base URL is directly in the config
        base_url = self.config[key_prefix + "url"]

        # gcode string needs to be translated to sender-specific format (i.e. for bCNC replace ; with \n)
        if debug:
            self.log("text replace, before [" + txt + "]")

        # ok, so configparser escapes the string literal, rather than beat my head against this anymore,
        # i'm just straight replacing the one and only string literal that's between me and victory.
        txt = txt.replace(self.config[key + "_separator"],
                          self.config[key_prefix + "separator"].replace('\\n', '\n'))
        if debug:
            self.log("text replace, after  [" + txt + "]")

        # query param name is in the config
        param_name = self.config[key_prefix + "paramName"]

        params = {param_name: txt}
        self.send_to_gcode_sender(base_url, params)

    def send_to_gcode_sender(self, url, params):
        """
        If gcode_sender_enable, then we will send the msg to the configured gcode sender
        :param url: the url with all gcode properly encoded
        :param params: a dictionary of query parameter names and values
        :return: nothing
        """
        if self.gcode_sender_enable:
            try:
                http_rsp = requests.get(url, params)
                self.log("HTTP Response --begin")
                self.log("response status: " + str(http_rsp.status_code))
                self.log(http_rsp.text)
                self.log("--end HTTP Response")
            except Exception as e:
                self.log("Error visiting gcode sender URL: " + str(e))


class PendantGui(Pendant):
    def __init__(self, config=None):
        Pendant.__init__(self, config=config)
        self.main_window = PendantMainWindow(pendant=self)
        self.log_object = ConsoleFrame(title=self.config["gui_frame_log_title"])
        self.gcode_log = ConsoleFrame(title=self.config["gui_frame_gcode_title"])
        self.stdin_log = StdinFrame(title=self.config["gui_frame_stdin_title"])
        self.stdin_log.add_stdin_line_subscriber(self.stdin_line_queue)

    def create_gui(self):

        sender_frame = QFrame()
        sender_frame.setFrameStyle(QFrame.StyledPanel)
        sender_layout = QHBoxLayout()
        enable_cb = QCheckBox("Enable Gcode Sending")
        enable_cb.stateChanged.connect(self.changed_enable_state)
        enable_cb.setChecked(self.gcode_sender_enable)
        sender_layout.addWidget(enable_cb)
        sender_frame.setLayout(sender_layout)

        outer_frame = QWidget()
        outer_layout = QHBoxLayout()

        left_frame = QWidget()
        left_frame.setMinimumWidth(400)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(SerialConnectionWidget(pendant=self))
        left_layout.addWidget(sender_frame)
        left_layout.addWidget(self.gcode_log)

        # tabbed pane for system log and stdin
        tabs = QTabWidget()
        tabs.addTab(self.log_object, "System Log")
        tabs.addTab(self.stdin_log, self.stdin_log.title)

        left_layout.addWidget(tabs)
        left_frame.setLayout(left_layout)

        right_frame = QFrame()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(ProbeFrame(pendant=self))
        right_layout.addWidget(NotifyFrame(pendant=self, notify_manager=self.notify_manager))
        emu_frame = PendantEmulator(pendant=self)
        self.add_client_msg_receiver(emu_frame)
        right_layout.addWidget(emu_frame)
        right_frame.setLayout(right_layout)

        outer_layout.addWidget(left_frame)
        outer_layout.addWidget(right_frame)
        outer_frame.setLayout(outer_layout)

        self.main_window.setCentralWidget(outer_frame)
        self.main_window.setWindowTitle("HC Pendant 2020")

        if self.config.getboolean("window_position"):
            print("setting window position")
            monitor = QDesktopWidget().screenGeometry(int(self.config["window_monitor"]))
            self.main_window.move(monitor.left() + int(self.config["window_x"]), monitor.top() +
                                  int(self.config["window_y"]))
        else:
            print("config says don't set window position, allowing default to continue")

        self.main_window.show()

    def changed_enable_state(self, state, debug=False):
        if debug:
            self.log("enable state changed")

        self.gcode_sender_enable = (state == Qt.Checked)


class PendantMainWindow(QMainWindow):
    def __init__(self, parent=None, pendant=None):
        QWidget.__init__(self, parent)
        self.pendant = pendant

    def closeEvent(self, event):
        print("closing main window")
        self.pendant.shutdown()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    config_file = "pendant.ini"
    email_config_file = "pendant-email.ini"
    if len(sys.argv) < 2:
        print("no config file specified, using default:", config_file)
    else:
        config_file = sys.argv[1]
        print("using config file:", config_file)

    if len(sys.argv) < 3:
        print("no email config file specified, using default:", email_config_file)
    else:
        email_config_file = sys.argv[2]
        print("using email config file:", email_config_file)

    configuration = configparser.ConfigParser(allow_no_value=True)
    configuration.read(config_file)
    configuration = configuration["DEFAULT"]

    email_config = configparser.ConfigParser(allow_no_value=True)
    email_config.read(email_config_file)

    for k, v in email_config.items("EMAIL"):
        configuration[k] = v

    gui = PendantGui(config=configuration)

    gui.create_gui()

    ret = app.exec_()
    app.exit(ret)
