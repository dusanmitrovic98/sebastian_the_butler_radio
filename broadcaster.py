import queue
import threading
import logging

class Broadcaster:
    """
    Manages multiple client queues to broadcast data to all of them.
    This is used to distribute the audio stream to every connected listener.
    """
    def __init__(self):
        self.clients = set()
        self._lock = threading.Lock()
        self.logger = logging.getLogger("Broadcaster")

    def register(self):
        """
        Registers a new client. Creates and returns a new queue for that client.
        The queue has a max size to prevent a slow client from consuming all memory.
        """
        with self._lock:
            # Use a bounded queue to prevent a single slow client from crashing the server
            client_queue = queue.Queue(maxsize=20) 
            self.clients.add(client_queue)
            self.logger.info(f"Client registered. Total clients: {len(self.clients)}")
            return client_queue

    def unregister(self, client_queue):
        """Unregisters a client's queue."""
        with self._lock:
            self.clients.discard(client_queue)
            self.logger.info(f"Client unregistered. Total clients: {len(self.clients)}")

    def push(self, chunk):
        """Pushes a data chunk to all registered client queues."""
        with self._lock:
            # Iterate over a copy, as the set could be modified during iteration
            for client_queue in list(self.clients):
                try:
                    # Use non-blocking put to avoid the audio engine thread from
                    # getting stuck on a full client queue.
                    client_queue.put_nowait(chunk)
                except queue.Full:
                    # A client is lagging. We'll let them miss this chunk.
                    # This prevents one slow listener from halting the stream for everyone.
                    pass