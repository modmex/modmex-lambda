from contextvars import copy_context

from reactivex.scheduler import ThreadPoolScheduler


class ContextThreadPoolScheduler(ThreadPoolScheduler):
    """Thread-pool scheduler that preserves the scheduling context."""

    class ThreadPoolThread(ThreadPoolScheduler.ThreadPoolThread):
        def __init__(self, executor, target):
            super().__init__(executor, target)
            self.context = copy_context()

        def start(self) -> None:
            self.future = self.executor.submit(self.context.run, self.target)
