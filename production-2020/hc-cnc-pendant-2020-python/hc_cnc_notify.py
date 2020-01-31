from datetime import datetime
from threading import Thread
from smtplib import SMTP, SMTPException
from PyQt5.QtWidgets import QFrame, QPushButton, QGridLayout, QVBoxLayout, QLabel, QHBoxLayout
from hc_cnc_constants import NotifyStates, JobStates
from hc_observable import Observable, ThreadedObserver


class NotifyManager(Observable):
    def __init__(self, config=None, **kwargs):
        super().__init__(**kwargs)
        self.notify_state = NotifyStates.IDLE
        self.job_state = JobStates.IDLE
        self.job_start = None

        self.email_server = config["email_server"]
        self.email_port = int(config["email_port"])
        self.email_from = config["email_from"]
        self.email_password = config["email_password"]
        self.email_to = config["email_to"]

    def process_notify_button(self, debug=False):
        """
        Operator pressed the notify button
        :return: nothing
        """
        if debug:
            print("process_notify_button")

        if self.notify_state == NotifyStates.IDLE:
            # activate the monitor
            self.set_notify_state(NotifyStates.ARMED)
        elif self.notify_state == NotifyStates.ARMED:
            # deactivate the monitor
            self.set_notify_state(NotifyStates.IDLE)
        elif self.notify_state == NotifyStates.FIRED:
            # user is telling us the notify message was received, so reset
            self.set_notify_state(NotifyStates.IDLE)

    def set_notify_state(self, state, notify=True):
        self.notify_state = state
        if notify:
            self.notify_observers()

    def set_job_state(self, state):
        """
        Here is where the magic happens.  Depending on job_state and notify_state, we just might notify the operator.
        :param state: the new job_state
        :return: nothing
        """
        if state == JobStates.IDLE:
            # We are no longer milling
            if self.job_state == JobStates.RUNNING and self.notify_state == NotifyStates.ARMED:
                # We were milling, now we're IDLE, and the user armed the notify system
                self.operator_notice()
                self.set_notify_state(NotifyStates.FIRED, notify=False)
            # clear the start time AFTER operator_notice so we can include a start time in the email
            self.job_start = None
        elif state == JobStates.RUNNING and self.job_state == JobStates.IDLE:
            # We were idle, now we're milling, record the start time
            self.job_start = datetime.now()

        self.job_state = state
        self.notify_observers()

    def operator_notice(self, debug=False):
        if debug:
            print("You've been served!", str(self.job_start).split('.')[0])

        # invoke the email in its own thread in case of network delay
        email_thread = Thread(target=self.send_email)
        email_thread.start()

    def send_email(self, debug=False):

        if self.email_server is None or self.email_server == "":
            print("email_server=None, pendant-email.ini did not load.  Specify it as the second argument to the runtime. Not sending mail.")
            return

        if self.email_server == "SERVER":
            print("email_server=SERVER, default pendant-email.ini needs updating.  Not sending mail.")
            return

        if debug:
            print("Sending email...")

        message = "Subject: CNC job finished\n\nThe job finished at " + str(datetime.now()).split('.')[0]

        try:
            with SMTP(self.email_server, self.email_port) as smtp:
                # smtp = SMTP(self.email_server, self.email_port)
                smtp.starttls()
                smtp.login(self.email_from, self.email_password)
                smtp.sendmail(self.email_from, self.email_to, message)
        except SMTPException as e:
            print("Failed sending email: " + e.strerror)

        if debug:
            print("Email sent. " + message)


class NotifyFrame(QFrame, ThreadedObserver):
    """
    Widget for displaying the CNC Job Notify information.  Used for sending me a text message
    when a long running CNC G-Code job completes.
    """
    def __init__(self, pendant=None, notify_manager=None, **kwargs):
        super().__init__(**kwargs)

        self.notify_manager: NotifyManager = notify_manager
        self.notify_manager.add_observer(self)

        self.pendant = pendant

        self.setFrameStyle(QFrame.StyledPanel)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(self.pendant.config["gui_frame_notify_title"]))

        label_frame = QFrame()

        label_layout = QGridLayout()
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.addWidget(QLabel("Notify State:  "), 0, 0)
        self.notify_state_label = QLabel("")
        label_layout.addWidget(self.notify_state_label, 0, 1)
        label_layout.addWidget(QLabel("Job State:  "), 1, 0)
        self.job_state_label = QLabel("")
        label_layout.addWidget(self.job_state_label, 1, 1)
        label_frame.setLayout(label_layout)

        top_frame = QFrame()
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(label_frame)

        fire_button = QPushButton("Fire!")
        fire_button.clicked.connect(self.click_fired)
        top_layout.addWidget(fire_button)

        self.job_button = QPushButton("Set Job Running")
        self.job_button.clicked.connect(self.click_job)
        top_layout.addWidget(self.job_button)

        top_layout.addStretch()
        top_frame.setLayout(top_layout)

        layout.addWidget(top_frame)

        # call our update to initialize the display
        self.observable_update(self)

        self.setLayout(layout)

    def click_fired(self):
        self.notify_manager.set_notify_state(NotifyStates.FIRED)

    def click_job(self):
        if self.notify_manager.job_state == JobStates.IDLE:
            self.notify_manager.set_job_state(JobStates.RUNNING)
            self.job_button.setText("Set Job Idle")
        elif self.notify_manager.job_state == JobStates.RUNNING:
            self.notify_manager.set_job_state(JobStates.IDLE)
            self.job_button.setText("Set Job Running")

    def observable_update(self, o, debug=False):
        if debug:
            print("NotifyFrame.observable_update")

        if self.notify_manager.notify_state == NotifyStates.IDLE:
            self.notify_state_label.setText("IDLE")
        elif self.notify_manager.notify_state == NotifyStates.ARMED:
            self.notify_state_label.setText("ARMED")
        elif self.notify_manager.notify_state == NotifyStates.FIRED:
            self.notify_state_label.setText("FIRED")

        if self.notify_manager.job_state == JobStates.IDLE:
            self.job_state_label.setText("IDLE")
        elif self.notify_manager.job_state == JobStates.RUNNING:
            self.job_state_label.setText("RUNNING")
