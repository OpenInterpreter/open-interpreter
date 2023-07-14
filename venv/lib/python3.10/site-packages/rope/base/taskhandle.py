from abc import ABC, abstractmethod
from typing import Optional, Sequence

from rope.base import exceptions, utils


class BaseJobSet(ABC):
    name: str = ""
    job_name: str = ""

    @abstractmethod
    def started_job(self, name: str) -> None:
        pass

    @abstractmethod
    def finished_job(self) -> None:
        pass

    @abstractmethod
    def check_status(self) -> None:
        pass

    @utils.deprecated("Just use JobSet.job_name attribute/property instead")
    def get_active_job_name(self) -> str:
        pass

    @abstractmethod
    def get_percent_done(self) -> Optional[float]:
        pass

    @utils.deprecated("Just use JobSet.name attribute/property instead")
    def get_name(self) -> str:
        pass

    @abstractmethod
    def increment(self) -> None:
        """
        Increment the number of tasks to complete.

        This is used if the number is not known ahead of time.
        """
        pass


class BaseTaskHandle(ABC):
    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def current_jobset(self) -> Optional[BaseJobSet]:
        pass

    @abstractmethod
    def add_observer(self) -> None:
        pass

    @abstractmethod
    def is_stopped(self) -> bool:
        pass

    @abstractmethod
    def get_jobsets(self) -> Sequence[BaseJobSet]:
        pass

    def create_jobset(
        self, name: str = "JobSet", count: Optional[int] = None
    ) -> BaseJobSet:
        pass

    def _inform_observers(self) -> None:
        pass


class TaskHandle(BaseTaskHandle):
    def __init__(self, name="Task", interrupts=True):
        """Construct a TaskHandle

        If `interrupts` is `False` the task won't be interrupted by
        calling `TaskHandle.stop()`.

        """
        self.name = name
        self.interrupts = interrupts
        self.stopped = False
        self.job_sets = []
        self.observers = []

    def stop(self):
        """Interrupts the refactoring"""
        if self.interrupts:
            self.stopped = True
            self._inform_observers()

    def current_jobset(self):
        """Return the current `JobSet`"""
        if self.job_sets:
            return self.job_sets[-1]

    def add_observer(self, observer):
        """Register an observer for this task handle

        The observer is notified whenever the task is stopped or
        a job gets finished.

        """
        self.observers.append(observer)

    def is_stopped(self):
        return self.stopped

    def get_jobsets(self):
        return self.job_sets

    def create_jobset(self, name="JobSet", count=None):
        result = JobSet(self, name=name, count=count)
        self.job_sets.append(result)
        self._inform_observers()
        return result

    def _inform_observers(self):
        for observer in list(self.observers):
            observer()


class JobSet(BaseJobSet):
    def __init__(self, handle, name, count):
        self.handle = handle
        self.name = name
        self.count = count
        self.done = 0
        self.job_name = None

    def started_job(self, name):
        self.check_status()
        self.job_name = name
        self.handle._inform_observers()

    def finished_job(self):
        self.check_status()
        self.done += 1
        self.handle._inform_observers()
        self.job_name = None

    def check_status(self):
        if self.handle.is_stopped():
            raise exceptions.InterruptedTaskError()

    @utils.deprecated("Just use JobSet.job_name attribute/property instead")
    def get_active_job_name(self):
        return self.job_name

    def get_percent_done(self):
        if self.count is not None and self.count > 0:
            percent = self.done * 100 // self.count
            return min(percent, 100)

    @utils.deprecated("Just use JobSet.name attribute/property instead")
    def get_name(self):
        return self.name

    def increment(self):
        self.count += 1


class NullTaskHandle(BaseTaskHandle):
    def __init__(self):
        pass

    def is_stopped(self):
        return False

    def stop(self):
        pass

    def create_jobset(self, *args, **kwds):
        return NullJobSet()

    def get_jobsets(self):
        return []

    def add_observer(self, observer):
        pass

    def current_jobset(self) -> None:
        """Return the current `JobSet`"""
        return None


class NullJobSet(BaseJobSet):
    def __init__(self, *args):
        pass

    def started_job(self, name):
        pass

    def finished_job(self):
        pass

    def check_status(self):
        pass

    @utils.deprecated("Just use JobSet.job_name attribute/property instead")
    def get_active_job_name(self):
        pass

    def get_percent_done(self):
        pass

    @utils.deprecated("Just use JobSet.name attribute/property instead")
    def get_name(self):
        pass

    def increment(self):
        pass


DEFAULT_TASK_HANDLE = NullTaskHandle()
DEFAULT_JOB_SET = NullJobSet()
