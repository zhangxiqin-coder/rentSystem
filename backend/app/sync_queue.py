"""
Turso sync 失败重试队列

当 session.commit() 后的 after_commit 钩子中 sync_to_cloud() 失败时，
记录待同步状态到文件。后台 cron job 定时检查并重试。

为什么用文件而不是数据库表：
- 数据库本身的 sync 刚失败了，再写一条记录进去只会再失败一次
- 文件系统更可靠，不依赖 Turso 连接状态
"""
import os
import json
import logging
import threading
from datetime import datetime

# 待同步队列文件目录
QUEUE_DIR = os.path.join(os.path.dirname(__file__), "..", "sync_queue")
QUEUE_FILE = os.path.join(QUEUE_DIR, "pending_syncs.jsonl")
MAX_RETRY = 5

# 线程锁（FastAPI 是多线程的）
_lock = threading.Lock()


def record_failed_sync(context: str):
    """记录一次 sync 失败到队列文件。

    Args:
        context: 什么操作触发的（如 "create_payment id=123"）
    """
    try:
        os.makedirs(QUEUE_DIR, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "retry_count": 0,
            "last_retry": None,
            "last_error": None,
        }
        with _lock:
            with open(QUEUE_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        logging.error(f"Turso sync 失败已记录到重试队列: {context}")
    except Exception as e:
        # 连记录日志都失败了，只能 log
        logging.error(f"记录 sync 失败日志也失败了: {e}", exc_info=True)


def get_pending_syncs():
    """读取所有待重试的 sync 记录。"""
    if not os.path.exists(QUEUE_FILE):
        return []
    results = []
    with _lock:
        with open(QUEUE_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return results


def retry_pending_syncs():
    """重试所有待同步的记录。

    成功的清除，失败的更新 retry_count。
    超过 MAX_RETRY 次的标记为永久失败，返回给调用方通知用户。

    Returns:
        list: 永久失败的记录（需要通知用户）
    """
    from app.database import sync_to_cloud

    pending = get_pending_syncs()
    if not pending:
        return []

    still_pending = []
    permanent_failures = []

    for entry in pending:
        if entry["retry_count"] >= MAX_RETRY:
            permanent_failures.append(entry)
            continue

        entry["retry_count"] += 1
        entry["last_retry"] = datetime.now().isoformat()

        try:
            success = sync_to_cloud()
            if success:
                logging.info(f"sync 重试成功: {entry['context']} (第{entry['retry_count']}次)")
                continue  # 成功，不写回队列
            else:
                entry["last_error"] = "sync_to_cloud returned False"
                still_pending.append(entry)
        except Exception as e:
            entry["last_error"] = str(e)
            if entry["retry_count"] >= MAX_RETRY:
                permanent_failures.append(entry)
            else:
                still_pending.append(entry)

    # 写回仍然 pending 的记录
    with _lock:
        os.makedirs(QUEUE_DIR, exist_ok=True)
        with open(QUEUE_FILE, "w") as f:
            for entry in still_pending:
                f.write(json.dumps(entry) + "\n")

    if permanent_failures:
        logging.error(
            f"⚠️ {len(permanent_failures)} 条 sync 重试 {MAX_RETRY} 次后永久失败！"
            f"本地缓存有数据但云端缺失，需要手动处理。"
        )

    return permanent_failures
