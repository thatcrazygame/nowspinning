import asyncio
from errno import ENETDOWN, ENETUNREACH, ENETRESET
import functools
import logging

logger = logging.getLogger(__name__)


def async_wait_for_network(pause: int, max_errors: int):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            network_errnos = [ENETDOWN, ENETUNREACH, ENETRESET]
            while not wrapper.success:
                try:
                    value = func(*args, **kwargs)
                    if wrapper.caught_errors > 0:
                        logger.warning(
                            f"Network restored. {func.__name__} run successfully."
                        )
                    wrapper.caught_errors = 0
                    wrapper.success = True
                    return value
                except OSError as e:
                    if e.errno not in network_errnos:
                        raise

                    if wrapper.caught_errors >= max_errors:
                        await asyncio.sleep(pause)
                        continue

                    wrapper.caught_errors += 1
                    logger.warning(
                        f"Network error in {func.__name__}. Will try again in {pause} seconds.",
                    )
                    if wrapper.caught_errors >= max_errors:
                        logger.warning(
                            f"Max network errors ({max_errors}) reached. Will not be logged again. Will continue to retry."
                        )

                    await asyncio.sleep(pause)
            wrapper.success = False  # reset for next run

        wrapper.caught_errors = 0
        wrapper.success = False
        return wrapper

    return decorator
