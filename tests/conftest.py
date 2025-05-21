import multiprocessing
import queue  # For queue.Empty
import threading  # Added for final thread check
import time
from unittest.mock import Mock, patch  # Import Mock for patching methods

import pytest


@pytest.fixture(scope="session")
def patch_all_threads_daemon():
    """
    Session-scoped fixture to temporarily patch threading.Thread.__init__
    to make all newly created threads (including multiprocessing.Queue's feeder thread)
    daemon threads. This helps ensure clean process exit in tests.
    """
    original_thread_init = threading.Thread.__init__

    def new_thread_init(self, *args, **kwargs):
        original_thread_init(self, *args, **kwargs)
        self.daemon = True  # Force new threads to be daemon
        # print(f"DEBUG: Forced thread '{self.name}' (ident={self.ident}) to be daemon.")

    print("\n[Session Fixture] Applying patch to make all new threads daemon.")
    with patch("threading.Thread.__init__", new=new_thread_init):
        yield  # Yield control for the duration of the session
    print("[Session Fixture] Patch to make new threads daemon reverted.")


@pytest.fixture(scope="session")
def session_multiprocessing_queue(
    patch_all_threads_daemon,
):  # Depend on the patching fixture
    """
    Manages the global multiprocessing.Queue for the entire test session.
    Patches settings.incoming_queue and ensures proper cleanup.
    """
    # The patch from patch_all_threads_daemon is active here, making the queue's feeder thread a daemon.
    q = multiprocessing.Queue()
    print("\n[Session Fixture] Created session-scoped multiprocessing.Queue.")

    # --- CRUCIAL FIX: Store the original close method from the INSTANCE ---
    _original_close_method = q.close  # Store the bound method of the instance
    print(
        "[Session Fixture] Stored original multiprocessing.Queue instance's close() method."
    )

    # --- CRUCIAL FIX: Patch the instance's close method directly ---
    # This ensures that any call to q.close() during the test session is a no-op,
    # preventing premature closure from other parts of the code.
    q.close = Mock()
    print(
        "[Session Fixture] multiprocessing.Queue instance's close() method patched to be a no-op."
    )

    # Patch the global settings.incoming_queue to use our test queue for the entire session
    with patch("accurecord_test.settings.incoming_queue", new=q):
        yield q  # Yield the test queue for the duration of the session

    # --- CRUCIAL CLEANUP FOR multiprocessing.Queue (Session Teardown) ---
    print("\n[Session Fixture] Cleaning up session-scoped multiprocessing.Queue...")

    # 1. Drain the queue if any items are left (important for test isolation)
    print("[Session Fixture] Attempting to drain queue...")
    try:
        while True:
            q.get_nowait()
            print("[Session Fixture] Drained item from queue.")
    except queue.Empty:
        print("[Session Fixture] Queue is empty.")
    except (
        ValueError,
        OSError,
    ) as e:  # Catch errors if handle is already closed during draining
        print(
            f"[Session Fixture] WARNING: Error during queue draining (handle might be closed): {e}"
        )

    # 2. Give the queue's internal thread a moment to settle (optional, but can help)
    time.sleep(0.1)  # Small synchronous sleep (e.g., 100ms)
    print("[Session Fixture] Short sleep after draining.")

    # 3. Explicitly call the original close method from the stored reference
    print(
        "[Session Fixture] Calling original multiprocessing.Queue.close() for final cleanup."
    )
    try:
        _original_close_method()  # Call the stored bound method
    except (ValueError, OSError) as e:
        print(
            f"[Session Fixture] WARNING: Error calling original q.close() (handle might be already closed): {e}"
        )

    # 4. Attempt to join the queue's background feeder thread with a timeout
    try:
        print(
            "[Session Fixture] Attempting to join multiprocessing.Queue feeder thread..."
        )
        if hasattr(q, "_thread") and q._thread and q._thread.is_alive():
            print(
                f"[Session Fixture] Queue internal thread '{q._thread.name}' is alive (daemon: {q._thread.daemon})."
            )
        else:
            print(
                "[Session Fixture] Queue internal thread not found or already stopped before join_thread."
            )

        q.join_thread(
            timeout=10
        )  # Increased timeout significantly for session-level cleanup

        if hasattr(q, "_thread") and q._thread and q._thread.is_alive():
            print(
                "[Session Fixture] WARNING: multiprocessing.Queue feeder thread still alive after join_thread(). This might indicate a deeper issue."
            )
        else:
            print(
                "[Session Fixture] multiprocessing.Queue feeder thread successfully joined or was already stopped."
            )

    except RuntimeError as e:
        print(
            f"[Session Fixture] ERROR: Could not join multiprocessing.Queue thread: {e}"
        )
    except Exception as e:
        print(f"[Session Fixture] ERROR during queue join_thread cleanup: {e}")

    print("[Session Fixture] Session-scoped multiprocessing.Queue cleanup complete.")

    # --- FINAL DIAGNOSTIC: Check for any remaining active threads ---
    print("\n[Session Fixture] --- Final Active Threads Check ---")
    for t in threading.enumerate():
        if t.is_alive() and not t.daemon and t.name != threading.current_thread().name:
            print(
                f"[Session Fixture] WARNING: Non-daemon, non-current thread still alive: Name='{t.name}', Ident={t.ident}"
            )
    print("[Session Fixture] --- End Final Active Threads Check ---")
