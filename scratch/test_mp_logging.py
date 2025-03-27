import sys
from concurrent.futures.process import ProcessPoolExecutor
import logging
import logging.handlers as handlers
import time
import multiprocessing as mp


"""
File was used to test the logging behavior when using a process pool executor. 
"""


def some_test_fn(dur: int, stp: int, fn_idx: int):
    """
    Small test function. Retrieves the QueueHandler from the given environment.
    Counts up to duration, sleeping for step s between outputs to the logger and finally returning the index.
    
    :param dur: How long should we sleep for in total
    :param stp: How long should we sleep for each increment
    :param fn_idx: user defined return value for debugging
    
    :returns: index
    """
    qh = globals().get("queue_handler")
    logger = logging.getLogger(f"worker_{fn_idx}")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(qh)
    qh.setLevel(logging.DEBUG)

    idx = 0
    while idx < dur:
        time.sleep(stp)
        idx += stp
        logger.info(f"Now at: {idx}")

    logger.warning(f"We're done now")
    return fn_idx


def init_child_logger(logging_queue: mp.Queue):
    """
    Init method adds a queue handler to the global environment of the child process.
    """
    queue_handler = handlers.QueueHandler(logging_queue)
    globals()["queue_handler"] = queue_handler


queue = mp.Queue()
duration = [i for i in range(60, 120, 2)]
index = [k+1 for k in range(30)]
step = [j for j in range(1, 60, 2)]

logger = logging.getLogger(f"Main")
logger.setLevel(logging.DEBUG)
handler = handlers.QueueHandler(queue)
handler.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
ql = handlers.QueueListener(queue, stream_handler)
ql.start()


pe = ProcessPoolExecutor(max_workers=16, initializer=init_child_logger, initargs=(queue,))
results = pe.map(some_test_fn, duration, step, index)
for result in results:
    logger.info(f"Got result {result}")

logger.warning("Got all done")
ql.stop()
