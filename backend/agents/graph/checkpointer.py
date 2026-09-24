import sqlite3

from agents.utils import logger


def make_checkpointer(settings):
    """
    Where LangGraph saves each step of a run, so paused or interrupted
    analyses can continue later (even after a server restart).

    - DATABASE_URL set  -> Postgres (e.g. your Supabase database)
    - otherwise         -> local SQLite file
    """
    if settings.database_url:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            conninfo=settings.database_url,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
            open=True,
        )
        saver = PostgresSaver(pool)
        saver.setup()
        logger.info("Checkpoints: Postgres")
        return saver

    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(settings.checkpoint_db, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    logger.info("Checkpoints: SQLite (%s)", settings.checkpoint_db)
    return saver
