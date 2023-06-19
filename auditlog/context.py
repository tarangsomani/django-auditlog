import contextlib
import threading
import time
from functools import partial, wraps

from django.db.models.signals import pre_save

from auditlog.models import LogEntry

threadlocal = threading.local()


@contextlib.contextmanager
def set_actor(actor, remote_addr=None, db_user=None):
    """Connect a signal receiver with current user attached."""
    # Initialize thread local storage
    threadlocal.auditlog = {
        "signal_duid": ("set_actor", time.time()),
        "remote_addr": remote_addr,
        "db_user": db_user
    }

    # Connect signal for automatic logging
    set_actor = partial(
        _set_actor, user=actor, signal_duid=threadlocal.auditlog["signal_duid"]
    )
    pre_save.connect(
        set_actor,
        sender=LogEntry,
        dispatch_uid=threadlocal.auditlog["signal_duid"],
        weak=False,
    )

    try:
        yield
    finally:
        try:
            auditlog = threadlocal.auditlog
        except AttributeError:
            pass
        else:
            pre_save.disconnect(sender=LogEntry, dispatch_uid=auditlog["signal_duid"])
            del threadlocal.auditlog


def _set_actor(user, sender, instance, signal_duid, **kwargs):
    """Signal receiver with extra 'user' and 'signal_duid' kwargs.

    This function becomes a valid signal receiver when it is curried with the actor and a dispatch id.
    """
    try:
        auditlog = threadlocal.auditlog
    except AttributeError:
        pass
    else:
        if signal_duid != auditlog["signal_duid"]:
            return

        if sender == LogEntry and instance.actor is None:
            instance.actor = user

        instance.remote_addr = auditlog["remote_addr"]
        instance.db_user = auditlog["db_user"]


@contextlib.contextmanager
def disable_auditlog():
    threadlocal.auditlog_disabled = True
    try:
        yield
    finally:
        try:
            del threadlocal.auditlog_disabled
        except AttributeError:
            pass


def custom_logging():
    def decorator(func):
        @wraps(func)
        def wrapped_func(self, request, *args, **kwargs):
            with set_actor(request.user, db_user=request.db_user):
                return func(self, request, *args, **kwargs)
        return wrapped_func
    return decorator