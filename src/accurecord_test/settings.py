import multiprocessing
from os import environ

from dotenv import load_dotenv

load_dotenv()

QUEUE_TIMEOUT = float(environ.get("QUEUE_TIMEOUT", "5.0"))
incoming_queue = multiprocessing.Queue()

WEB_PORT = int(environ.get("WEB_PORT", "80"))
DB_PATH = "./database.sqlite"
