# Makes sure the test environment (throw-away SQLite DB, fake GenAI client)
# is configured before any application module is imported.
import tests.helpers  # noqa: F401
