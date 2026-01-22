


# define a enum for task modes
from enum import Enum
class TaskMode(str, Enum):
    SYNC = 'SYNC'
    ASYNC = 'ASYNC'

# usage example:
# mode = TaskMode.SYNC