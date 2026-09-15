"""Test trace plugin - DO NOT IMPORT"""

import traceback

import aiohttp

_created = []


def pytest_configure(config):
    orig_init = aiohttp.UnixConnector.__init__

    def patched(self, *args, **kwargs):
        stack = traceback.extract_stack()[:-1][-3:]
        _created.append(("create", stack))
        return orig_init(self, *args, **kwargs)

    aiohttp.UnixConnector.__init__ = patched


def pytest_unconfigure(config):
    for action in ("create",):
        for create_type, stack in _created:
            if create_type == action:
                print(f"\n=== UnixConnector {action} at ===")
                for line in stack:
                    print(f"  {line.filename}:{line.lineno} in {line.name}")
                break
    _created.clear()
