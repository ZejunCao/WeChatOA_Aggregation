import json
import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
}


@dataclass
class Message_Info:
    id: str
    title: str
    digest: str
    link: str
    cover: str
    create_time: str
    is_deleted: bool
    item_show_type: int


class JsonFileManager:
    """仅管理仍使用 JSON 的运行时配置（凭证、爬取问题记录等）。"""

    _instance = None
    _lock = threading.Lock()
    data_dir = Path(__file__).parent.parent.parent / 'data'

    # 文章数据已迁入 wechatoa.db；勿在此加载 message_info / message_detail_text 等
    FILES = [
        'id_info',
        'issues_message',
    ]

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._data = {}
        self._file_locks = {}
        for file_name in self.FILES:
            self._load_file(file_name)

    def _load_file(self, file_name):
        file_path = self.data_dir / f"{file_name}.json"
        lock = threading.Lock()
        self._file_locks[file_name] = lock

        with lock:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self._data[file_name] = json.load(f)
                except (json.JSONDecodeError, IOError):
                    raise Exception(f"File '{file_name}' is corrupted")
            else:
                self._data[file_name] = {}
                if file_name == 'issues_message':
                    self._data[file_name] = {
                        'is_delete': [],
                        'dup_minhash': {},
                    }

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    def write(self, file_name):
        if file_name not in self._data:
            raise ValueError(f"File '{file_name}' not managed by this instance")

        lock = self._file_locks[file_name]
        file_path = self.data_dir / f"{file_name}.json"
        temp_path = self.data_dir / f".{file_name}.tmp"

        with lock:
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(
                        self._data[file_name],
                        f,
                        ensure_ascii=False,
                        indent=4,
                    )
                shutil.move(temp_path, file_path)
                return True
            except Exception as e:
                if temp_path.exists():
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                print(f"Error writing {file_name}: {str(e)}")
                return False

    def write_all(self):
        results = {}
        for file_name in self._data:
            results[file_name] = self.write(file_name)
        return results

    def reload(self, file_name):
        if file_name in self.FILES:
            self._load_file(file_name)
            return True
        return False

    def reload_all(self):
        for file_name in self.FILES:
            self.reload(file_name)
        return True


data_manager = JsonFileManager()
