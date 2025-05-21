import asyncio
import signal
import threading
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import Manager
from threading import Event
from types import FrameType
from typing import Any, Callable

from accurecord_test import settings
from accurecord_test.background import run as background_run
from accurecord_test.common import get_logger
from accurecord_test.web import run as web_run


@dataclass
class ShutdownHandler:
    exit_event: Event
    logger: Any

    def __call__(self, signum: int | None, frame: FrameType | None):
        self.logger.info(
            "Sending exit event to all tasks in pool", signal=signum, frame=frame
        )
        self.exit_event.set()


@dataclass
class DoneHandler:
    name: str
    exit_event: Event
    logger: Any
    shutdown_handler: ShutdownHandler

    def __call__(self, future: Future) -> None:
        self.logger.info(
            "MAIN: Task is done, prompting others to quit",
            name=self.name,
            future=future,
        )

        if future.exception() is not None:
            self.logger.exception(future.exception())

        self.shutdown_handler(None, None)


def process_run(func: Callable[..., Any], exit_event: Event, *arguments: Any) -> None:
    # NOTE: Construct the awaitable object here so it is properly handled by asyncio
    asyncio.run(func(exit_event, *arguments))


def task_submit(
    executor: ProcessPoolExecutor,
    exit_event: Event,
    name: str,
    func: Callable[..., Any],
    *arguments: Any,
    logger: Any,
) -> Future | None:
    future = executor.submit(process_run, func, exit_event, *arguments)

    future.add_done_callback(
        DoneHandler(name, exit_event, logger, ShutdownHandler(exit_event, logger))
    )
    logger.info("MAIN: Task is submitted", name=name, future=future)

    return future


def main() -> None:
    logger = get_logger(__name__)
    pmanager = Manager()
    exit_event = pmanager.Event()

    with ProcessPoolExecutor() as executor:
        for signal_num in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
            signal.signal(signal_num, ShutdownHandler(exit_event, logger))

        task_submit(executor, exit_event, "web", web_run, logger=logger)
        task_submit(executor, exit_event, "background", background_run, logger=logger)
