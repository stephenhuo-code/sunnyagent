"""SQL deep agent — queries the Chinook music store database."""

import urllib.request
from pathlib import Path

from deepagents import create_deep_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase

from backend.llm import get_model
from backend.prompts import SQL_SUBAGENT_PROMPT
from backend.registry import register_agent
from backend.tools.file_tools import read_file
from backend.checkpointer_store import get_checkpointer

_CHINOOK_DB = Path(__file__).resolve().parent.parent.parent / "chinook.db"
_CHINOOK_URL = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"


def _ensure_chinook_db(path: Path) -> Path:
    """Download Chinook database if it doesn't exist."""
    if not path.exists():
        urllib.request.urlretrieve(_CHINOOK_URL, path)
    return path


_db_path = _ensure_chinook_db(_CHINOOK_DB)
_db = SQLDatabase.from_uri(f"sqlite:///{_db_path}", sample_rows_in_table_info=3)
_model = get_model("sql")
_sql_tools = SQLDatabaseToolkit(db=_db, llm=_model).get_tools()
_tools = _sql_tools + [read_file]  # 添加文件读取工具

_agent = create_deep_agent(
    model=_model,
    tools=_tools,
    system_prompt=SQL_SUBAGENT_PROMPT,
    name="sql",
    checkpointer=get_checkpointer(),
)

register_agent(
    name="sql",
    description=(
        "Query the Chinook music store database "
        "(artists, albums, tracks, customers, invoices, employees)."
    ),
    graph=_agent,
    tools=_tools,
    icon="database",
    capabilities=["database", "sql_query"],
    source="preset",
)
