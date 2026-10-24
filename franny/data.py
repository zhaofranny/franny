"""Validated metadata-only import; never downloads note URLs."""
from contextlib import contextmanager
import io
import math
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import pandas as pd

COLUMNS = ["title", "url", "published_at", "likes", "saves", "comments"]
ALIASES = dict(zip(["标题", "笔记链接", "发布时间", "点赞数", "收藏数", "评论数"], COLUMNS))

def parse_csv(raw: bytes) -> pd.DataFrame:
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("文件不能超过 10MB")
    try:
        df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig", dtype=str).rename(columns=ALIASES)
    except Exception as exc:
        raise ValueError("请使用 UTF-8 CSV，检查格式") from exc
    if not set(COLUMNS).issubset(df.columns) or df.columns.duplicated().any():
        raise ValueError("缺少必填列或列名重复：" + ", ".join(COLUMNS))
    df = df[COLUMNS].copy()
    if df.empty or len(df) > 50000:
        raise ValueError("需要 1–50000 行数据")
    for col in ["title", "url"]:
        df[col] = df[col].fillna("").str.strip()
        if df[col].eq("").any():
            raise ValueError(f"{col} 不能为空")
    if df.title.str.len().gt(500).any():
        raise ValueError("标题不能超过 500 字")
    def normalize(url):
        try:
            p = urlsplit(url)
            if p.scheme != "https" or p.hostname not in {"www.xiaohongshu.com", "xiaohongshu.com", "xhslink.com"} or p.username or p.password or p.port not in (None, 443):
                raise ValueError()
            return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))
        except ValueError as exc:
            raise ValueError("笔记链接须为小红书 HTTPS 链接") from exc
    df["url"] = df.url.map(normalize)
    # Naive CSV timestamps are interpreted as Asia/Shanghai.
    def date(value):
        try:
            t = pd.Timestamp(value)
            if pd.isna(t):
                raise ValueError()
            t = t.tz_localize("Asia/Shanghai") if t.tzinfo is None else t
            t = t.tz_convert("UTC")
            if t > pd.Timestamp.now(tz="UTC"):
                raise ValueError()
            return t.isoformat()
        except Exception as exc:
            raise ValueError("发布时间无效或在未来") from exc
    df["published_at"] = df.published_at.map(date)
    for col in COLUMNS[3:]:
        nums = pd.to_numeric(df[col], errors="coerce")
        if nums.isna().any() or not nums.map(lambda n: math.isfinite(n) and 0 <= n <= 10**12 and n == int(n)).all():
            raise ValueError(f"{col} 必须为非负整数（不超过 10^12）")
        df[col] = nums.astype("int64")
    return df.drop_duplicates("url", keep="last")

class Store:
    def __init__(self, path="data/franny.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS notes(title TEXT NOT NULL,url TEXT PRIMARY KEY,published_at TEXT NOT NULL,likes INTEGER,saves INTEGER,comments INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS generation_limits(provider TEXT PRIMARY KEY,next_allowed REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS drafts(id INTEGER PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP,payload TEXT NOT NULL)")
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()
    def import_notes(self, df):
        with self.connect() as db:
            db.executemany("INSERT INTO notes VALUES(?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET title=excluded.title,published_at=excluded.published_at,likes=excluded.likes,saves=excluded.saves,comments=excluded.comments", df[COLUMNS].itertuples(index=False, name=None))
        return len(df)
    def notes(self):
        with self.connect() as db:
            return pd.read_sql_query("SELECT * FROM notes", db)
    def save_draft(self, payload):
        with self.connect() as db:
            return db.execute("INSERT INTO drafts(payload) VALUES(?)", (payload,)).lastrowid
    def drafts(self):
        with self.connect() as db:
            return db.execute("SELECT id,created_at,payload FROM drafts ORDER BY id DESC").fetchall()

    def reserve_generation(self, provider, interval=8, now=None):
        from .errors import GenerationCooldownError
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT next_allowed FROM generation_limits WHERE provider=?", (provider,)).fetchone()
            if row and row[0] > now:
                raise GenerationCooldownError(math.ceil(row[0]-now))
            db.execute("INSERT INTO generation_limits VALUES(?,?) ON CONFLICT(provider) DO UPDATE SET next_allowed=excluded.next_allowed",(provider,now+interval))

    def set_cooldown(self, provider, seconds, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute("INSERT INTO generation_limits VALUES(?,?) ON CONFLICT(provider) DO UPDATE SET next_allowed=MAX(next_allowed,excluded.next_allowed)",(provider,now+seconds))

    def backup_bytes(self):
        # SQLite online backup includes committed WAL state; never copy live database files directly.
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'franny.sqlite'
            with self.connect() as source, sqlite3.connect(path) as target:
                source.backup(target)
            return path.read_bytes()
