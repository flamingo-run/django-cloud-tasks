import inspect
from contextlib import contextmanager
from typing import Callable, Type
from django.test import SimpleTestCase
from django.utils.connection import ConnectionProxy
from gcp_pilot.mocker import patch_auth

LockType = (Callable | Exception | Type[Exception]) | None


class AuthenticationMixin(SimpleTestCase):
    def setUp(self) -> None:
        auth = patch_auth()
        auth.start()
        self.addCleanup(auth.stop)
        super().setUp()


def patch_cache_lock(
    lock_side_effect: LockType = None,
    unlock_side_effect: LockType = None,
):
    class CacheAssertion:
        def __init__(self):
            self.call_count = 0
            self.call_args = []
            self.call_kwargs = {}

        def start(self):
            setattr(ConnectionProxy, "lock", mocked_lock)

        def stop(self):
            delattr(ConnectionProxy, "lock")

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop()

        def assert_called(self):
            msg = "Expected to be called, but it was not"
            assert self.call_count > 0, msg

        def assert_called_with(self, *expected_args, **expected_kwargs):
            self.assert_called()

            lock_args = self.call_args  # remove the self argument
            msg = (
                f"Expected to lock with {len(expected_args)} args: {', '.join(expected_args)}. "
                f"But locked with {len(lock_args)} args: {', '.join(lock_args)}"
            )
            assert len(expected_args) == len(lock_args), msg

            for expected, received in zip(expected_args, lock_args):
                msg = f"Expected to lock with {expected}, but locked with {received}"
                assert expected == received, msg

            lock_kwargs = self.call_kwargs
            msg = (
                f"Expected to lock with {len(expected_kwargs)} kwargs: {', '.join(expected_kwargs)}. "
                f"But locked with {len(lock_kwargs)} kwargs: {', '.join(lock_kwargs)}"
            )
            assert len(expected_kwargs) == len(lock_kwargs), msg

            for expected_key, expected_value in expected_kwargs.items():
                received = lock_kwargs.get(expected_key)
                msg = f"Expected to lock with {expected_key}={expected_value}, but locked with {received}"
                assert expected_value == received, msg

    assertion = CacheAssertion()

    def _execute_effect(effect):
        if effect:
            if inspect.isclass(effect) and issubclass(effect, Exception):
                raise effect()
            if isinstance(effect, Exception):
                raise effect
            if callable(effect):
                effect()

    @contextmanager
    def mocked_lock(*lock_args, **lock_kwargs):
        nonlocal assertion

        assertion.call_count += 1
        assertion.call_args = lock_args[1:]  # remove self argument
        assertion.call_kwargs = lock_kwargs

        _execute_effect(effect=lock_side_effect)
        yield
        _execute_effect(effect=unlock_side_effect)

    return assertion
