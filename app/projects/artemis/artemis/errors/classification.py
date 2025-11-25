class TaskError(Exception):
    pass

class SourceError(TaskError):
    pass

class SinkError(TaskError):
    pass

