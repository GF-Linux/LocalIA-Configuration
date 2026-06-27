import os

DEFAULT_ZIM_PATH = r"C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim"

def get_zim_path() -> str:
    return os.environ.get("PROFESSOR_ZIM_PATH", DEFAULT_ZIM_PATH)
