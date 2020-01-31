import threading
from queue import Queue


class Observable:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._observers = []
        self._observable_lock = threading.Condition()

    def add_observer(self, observer):
        self._observers.append(observer)

    def remove_observer(self, observer):
        self._observers.remove(observer)

    def notify_observers(self):
        """
        Invoke this method to notify all your observers of your state change.
        :return: nothing
        """
        self._observable_lock.acquire()
        for observer in self._observers:
            observer.observable_notify(self)
        self._observable_lock.release()


class ThreadedObserver:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._observable_queue = Queue()
        self._observer_thread = threading.Thread(target=self._process_observable_queue)
        self._observer_thread.daemon = True
        self._observer_thread.start()

    def observable_notify(self, o):
        """
        This is the public method that the observable class will invoke when it changes.
        Children of this class do not need to override this.
        This implementation puts the observable on the _observable_queue so the thread can pick it up.
        :param o: the observable object that changed
        :return: nothing
        """
        self._observable_queue.put(o)

    def observable_update(self, o):
        """
        Children of this class SHOULD override this method.  This gets invoked in the observer thread
        whenever the observable changes.
        :param o: the observable that changed
        :return: nothing
        """
        raise NotImplementedError("Please override ThreadedObserver.observable_update()")

    def _process_observable_queue(self):
        """
        Thread target, grabs observables off the queue and invokes ???
        :return:
        """
        while True:
            o = self._observable_queue.get()
            self.observable_update(o)
