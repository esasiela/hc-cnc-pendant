# from enum import Enum, auto

# TODO upgrade Python version on Raspberry Pi controller to get Enum support
# class LogTypes(Enum):
#    SYS = auto()
#    DEBUG = auto()
#    MSG = auto()
#    GCODE = auto()
#    JOG = auto()
#    STOP = auto()
#    PROBE = auto()
#    NOTIFY = auto()


class LogTypes:
    SYS = 0
    DEBUG = 2
    MSG = 3
    GCODE = 4
    JOG = 5
    STOP = 6
    PROBE = 7
    NOTIFY = 8


class NotifyStates:
    """
    Use byte value constants for comparison to serial byte coming from the device
    """
    IDLE = 0x01
    ARMED = 0x02
    FIRED = 0x03


class JobStates:
    IDLE = 0
    RUNNING = 1
