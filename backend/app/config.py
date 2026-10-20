import os
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "backend" / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
RECORDS_FILE = STORAGE_DIR / "meal_records.json"
PROFILE_FILE = STORAGE_DIR / "user_profile.json"
CONFIG_DIR = BASE_DIR / "backend" / "config"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
CONFIG_EXAMPLE_FILE = CONFIG_DIR / "config.example.yaml"
MEMORY_DIR = STORAGE_DIR / "memory"
SHORT_MEMORY_DIR = MEMORY_DIR / "short_term"
LONG_MEMORY_DIR = MEMORY_DIR / "long_term"
BODY_METRICS_FILE = LONG_MEMORY_DIR / "body_metrics.json"


def _load_dotenv() -> None:
    """读取 backend/.env 与项目根 .env，把变量注入环境。

    已存在的真实环境变量优先，不会被 .env 覆盖。
    密钥只放在 .env（已 gitignore），配置文件里保持空值。
    """
    for candidate in (BASE_DIR / "backend" / ".env", BASE_DIR / ".env"):
        if not candidate.exists():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_settings() -> dict:
    settings = load_yaml(CONFIG_EXAMPLE_FILE)
    settings = deep_merge(settings, load_yaml(CONFIG_FILE))
    llm = settings.setdefault("llm", {})
    server = settings.setdefault("server", {})
    rag = settings.setdefault("rag", {})
    memory = settings.setdefault("memory", {})

    llm["api_key"] = os.getenv("OPENAI_API_KEY") or os.getenv("RAG_API_KEY") or llm.get("api_key", "")
    llm["base_url"] = os.getenv("OPENAI_BASE_URL") or os.getenv("RAG_BASE_URL") or llm.get("base_url", "https://www.dmxapi.cn/v1")
    llm["chat_model"] = os.getenv("NUTRIFIT_CHAT_MODEL") or llm.get("chat_model", "gpt-5-mini")
    llm["vision_model"] = os.getenv("NUTRIFIT_VISION_MODEL") or llm.get("vision_model", "gpt-5-mini")
    server["host"] = os.getenv("NUTRIFIT_HOST") or server.get("host", "127.0.0.1")
    server["port"] = int(os.getenv("NUTRIFIT_PORT") or server.get("port", 8008))
    rag["top_k"] = int(rag.get("top_k", 6))
    memory["short_term_max_turns"] = int(memory.get("short_term_max_turns", 12))
    return settings


_load_dotenv()
SETTINGS = load_settings()
OPENAI_API_KEY = SETTINGS["llm"].get("api_key", "")
OPENAI_BASE_URL = SETTINGS["llm"].get("base_url", "https://www.dmxapi.cn/v1")
CHAT_MODEL = SETTINGS["llm"].get("chat_model", "gpt-5-mini")
VISION_MODEL = SETTINGS["llm"].get("vision_model", "gpt-5-mini")
LLM_TEMPERATURE = float(SETTINGS["llm"].get("temperature", 0.2))
SHORT_TERM_MAX_TURNS = int(SETTINGS["memory"].get("short_term_max_turns", 12))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
SHORT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LONG_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
