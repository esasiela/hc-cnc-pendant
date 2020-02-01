from enum import Enum, IntEnum, auto


class LogTypes(Enum):
    SYS = auto()
    DEBUG = auto()
    MSG = auto()
    GCODE = auto()
    JOG = auto()
    STOP = auto()
    PROBE = auto()
    NOTIFY = auto()


class NotifyStates(IntEnum):
    """
    Use byte value constants for comparison to serial byte coming from the device
    """
    IDLE = 0x01
    ARMED = 0x02
    FIRED = 0x03


class JobStates(Enum):
    IDLE = auto()
    RUNNING = auto()
