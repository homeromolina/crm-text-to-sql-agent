import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# banco de teste isolado, criado antes de importar app.config
_DB = Path(tempfile.mkdtemp()) / "crm_teste.db"
os.environ["CRM_DB_PATH"] = str(_DB)
os.environ.pop("LANGFUSE_PUBLIC_KEY", None)

sys.path.insert(0, str(RAIZ / "data"))
import seed  # noqa: E402

seed.main(_DB)
