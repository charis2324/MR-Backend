import logging

from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig()  # Initialize logging
logging.getLogger("apscheduler").setLevel(logging.DEBUG)

scheduler = BackgroundScheduler()
scheduler.start()
