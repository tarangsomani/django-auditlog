from functools import partial, wraps
from auditlog.context import set_actor


def custom_logging():
    def decorator(func):
        @wraps(func)
        def wrapped_func(self, request, *args, **kwargs):
            with set_actor(request.user, db_user=request.db_user):
                return func(self, request, *args, **kwargs)
        return wrapped_func
    return decorator
