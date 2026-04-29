"""
Pytest configuration and fixtures for VoidAccess test suite.

This module provides:
- Session-scoped fixtures for test database engines
- Automatic cleanup of engine caches after each test
- Leak detection to catch engines left in the cache after test sessions
"""

import pytest


@pytest.fixture
def db_engine(tmp_path):
    """
    Create a function-scoped SQLite engine that is cleaned up after each test.

    Uses tmp_path to create a unique temporary database file per test,
    then properly disposes of the engine and clears it from the cache
    in the teardown phase.

    Usage::

        def test_something(db_engine):
            Base.metadata.create_all(db_engine)
            # ... test code ...
    """
    from db.models import Base
    from db.session import get_engine, release_engine

    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    engine = get_engine(url)
    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)
    release_engine(url)


@pytest.fixture
def clear_engine_cache(request):
    """
    Clear engine caches after each test to prevent leaks.

    This fixture can be added to any test that creates engines to ensure
    they are properly disposed. Unlike the db_engine fixture, this does
    not create an engine - it only cleans up any existing one.
    
    Add this as a parameter to your test function if you need it:
    
        def test_something(clear_engine_cache):
            ...
    """
    yield

    from db.session import get_engine

    cache_info = get_engine.cache_info()
    if cache_info.currsize > 0:
        get_engine.cache_clear()


@pytest.fixture(scope="session")
def check_engine_cache_leaks():
    """
    Session-scoped fixture to detect engine cache leaks at the end of the test session.

    Returns the cache_info before the session starts, then compares at the end
    to warn if engines were leaked.
    """
    from db.session import get_engine

    initial_info = get_engine.cache_info()

    yield

    final_info = get_engine.cache_info()
    if final_info.currsize > initial_info.currsize:
        leaked = final_info.currsize - initial_info.currsize
        pytest.fail(
            f"Engine cache leak detected: {leaked} entries remained after test session. "
            f"Final cache stats: {final_info}"
        )