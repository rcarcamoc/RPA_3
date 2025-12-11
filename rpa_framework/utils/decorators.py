"""Decorators."""
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

def retry_with_logging(max_attempts: int = 3, delay: float = 1.0):
    """Retry con logging."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} fallido finalmente")
                        raise
                    logger.warning(f"{func.__name__} reintentando ({attempt}/{max_attempts})")
                    time.sleep(delay)
        return wrapper
    return decorator

def timing(func):
    """Mide tiempo de ejecución."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"{func.__name__} en {elapsed:.2f}s")
        return result
    return wrapper
