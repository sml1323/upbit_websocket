import os
from unittest.mock import patch

from src.config import get_db_dsn, setup_logging


def test_get_db_dsn_defaults():
    dsn = get_db_dsn()
    assert "host=" in dsn
    assert "dbname=" in dsn


def test_get_db_dsn_with_env():
    with patch.dict(os.environ, {"DB_HOST": "myhost", "DB_PORT": "5433", "DB_NAME": "testdb"}):
        from importlib import reload
        import src.config as cfg
        reload(cfg)
        dsn = cfg.get_db_dsn()
        assert "myhost" in dsn
        assert "5433" in dsn
        assert "testdb" in dsn


def test_setup_logging_returns_logger():
    logger = setup_logging("test_logger")
    assert logger.name == "test_logger"
    assert len(logger.handlers) > 0


def test_setup_logging_level():
    logger = setup_logging("debug_logger", level="DEBUG")
    import logging
    assert logger.level == logging.DEBUG
