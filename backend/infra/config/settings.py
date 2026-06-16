import json
from pathlib import Path

SETTINGS_PATH=Path(__file__).resolve().parents[3]/".agent"/"settings.json"

def load_settings()->dict:
    """读取完整的settings配置"""
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.parent.mkdir(parents=True,exist_ok=True)
        SETTINGS_PATH.write_text("{}",encoding="utf-8")
        return {}
    
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    
    except Exception:
        return {}
    
def save_settings(data: dict) -> None:
    """将完整的配置字典保存回 settings.json"""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
