"""
Task Manager Module
Handles course grabbing tasks with independent execution threads.
"""

import os
import json
import uuid
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Callable, Dict

from jwglxt_api import JwglxtAPI
from account_manager import AccountManager, Account


class TaskStatus(Enum):
    """Task execution status."""
    STOPPED = "stopped"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass
class CourseInfo:
    """Course information for a task."""
    kch_id: str          # Course ID
    kcmc: str            # Course name
    jxb_ids: str         # Teaching class ID
    jxb_mc: str          # Teaching class name
    gnmkdm: str = "N253512"  # Module code
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CourseInfo':
        return cls(
            kch_id=data.get('kch_id', ''),
            kcmc=data.get('kcmc', ''),
            jxb_ids=data.get('jxb_ids', ''),
            jxb_mc=data.get('jxb_mc', ''),
            gnmkdm=data.get('gnmkdm', 'N253512')
        )


@dataclass
class GrabTask:
    """Represents a course grabbing task."""
    id: str
    account_id: str
    course_info: CourseInfo
    interval: float = 0.5
    status: TaskStatus = TaskStatus.STOPPED
    created_at: str = ""
    last_attempt: str = ""
    attempt_count: int = 0
    last_message: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'account_id': self.account_id,
            'course_info': self.course_info.to_dict(),
            'interval': self.interval,
            'status': self.status.value,
            'created_at': self.created_at,
            'last_attempt': self.last_attempt,
            'attempt_count': self.attempt_count,
            'last_message': self.last_message
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GrabTask':
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            account_id=data.get('account_id', ''),
            course_info=CourseInfo.from_dict(data.get('course_info', {})),
            interval=data.get('interval', 0.5),
            status=TaskStatus(data.get('status', 'stopped')),
            created_at=data.get('created_at', ''),
            last_attempt=data.get('last_attempt', ''),
            attempt_count=data.get('attempt_count', 0),
            last_message=data.get('last_message', '')
        )


class TaskManager:
    """Manages course grabbing tasks with independent execution."""
    
    def __init__(self, account_manager: AccountManager, tasks_path: str = None):
        if tasks_path is None:
            tasks_path = os.path.join(os.path.dirname(__file__), "tasks.json")
        
        self.tasks_path = tasks_path
        self.account_manager = account_manager
        self.tasks: List[GrabTask] = []
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_flags: Dict[str, bool] = {}
        self._api_sessions: Dict[str, JwglxtAPI] = {}  # Per-account API sessions
        
        # Callbacks
        self.on_task_update: Optional[Callable[[GrabTask], None]] = None
        self.on_task_success: Optional[Callable[[GrabTask, str], None]] = None
        self.on_task_error: Optional[Callable[[GrabTask, str], None]] = None
        self.on_log: Optional[Callable[[str, str, str], None]] = None  # task_id, message, level
        
        self._load()
    
    def _load(self):
        """Load tasks from file."""
        if not os.path.exists(self.tasks_path):
            self.tasks = []
            return
        
        try:
            with open(self.tasks_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.tasks = [GrabTask.from_dict(t) for t in data.get('tasks', [])]
            
            # Reset running tasks to stopped on load
            for task in self.tasks:
                if task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.STOPPED
            
        except Exception as e:
            print(f"Error loading tasks: {e}")
            self.tasks = []
    
    def save(self):
        """Save tasks to file."""
        data = {
            'tasks': [t.to_dict() for t in self.tasks]
        }
        
        with open(self.tasks_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_task(self, account_id: str, course_info: CourseInfo, 
                    interval: float = 0.5) -> Optional[GrabTask]:
        """Create a new grabbing task."""
        # Verify account exists
        if not self.account_manager.get_account(account_id):
            return None
        
        task = GrabTask(
            id=str(uuid.uuid4()),
            account_id=account_id,
            course_info=course_info,
            interval=interval
        )
        
        self.tasks.append(task)
        self.save()
        return task
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task by ID. Stops it first if running."""
        # Stop if running
        self.stop_task(task_id)
        
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self.save()
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[GrabTask]:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def update_task(self, task_id: str, interval: float = None) -> bool:
        """Update task properties. Can update interval even while running."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        if interval is not None:
            task.interval = interval
        
        self.save()
        self._emit_update(task)
        return True
    
    def get_all_tasks(self) -> List[GrabTask]:
        """Get all tasks."""
        return self.tasks.copy()
    
    def get_tasks_for_account(self, account_id: str) -> List[GrabTask]:
        """Get all tasks for a specific account."""
        return [t for t in self.tasks if t.account_id == account_id]
    
    def _get_api_session(self, account_id: str) -> Optional[JwglxtAPI]:
        """Get or create API session for account."""
        if account_id not in self._api_sessions:
            account = self.account_manager.get_account(account_id)
            if not account:
                return None
            
            base_url = self.account_manager.get_base_url()
            api = JwglxtAPI(base_url=base_url)
            self._api_sessions[account_id] = api
        
        return self._api_sessions[account_id]
    
    def _ensure_logged_in(self, account_id: str) -> bool:
        """Ensure the account is logged in."""
        api = self._get_api_session(account_id)
        if not api:
            return False
        
        account = self.account_manager.get_account(account_id)
        if not account:
            return False
        
        # Check if already logged in (has student_info)
        if hasattr(api, 'student_info') and api.student_info:
            return True
        
        try:
            api.login(account.username, account.password)
            api.init_course_selection()
            return True
        except Exception as e:
            self._emit_log(account_id, f"登录失败: {e}", "error")
            return False
    
    def _emit_log(self, task_id: str, message: str, level: str = "info"):
        """Emit log message."""
        if self.on_log:
            self.on_log(task_id, message, level)
    
    def _emit_update(self, task: GrabTask):
        """Emit task update."""
        if self.on_task_update:
            self.on_task_update(task)
    
    def start_task(self, task_id: str) -> bool:
        """Start a task."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.status == TaskStatus.RUNNING:
            return True  # Already running
        
        # Reset status
        task.status = TaskStatus.RUNNING
        task.last_message = ""
        self._stop_flags[task_id] = False
        self.save()
        self._emit_update(task)
        
        # Start thread
        thread = threading.Thread(target=self._run_task, args=(task_id,), daemon=True)
        self._threads[task_id] = thread
        thread.start()
        
        return True
    
    def stop_task(self, task_id: str) -> bool:
        """Stop a task."""
        task = self.get_task(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.RUNNING:
            return True  # Not running
        
        self._stop_flags[task_id] = True
        return True
    
    def start_all_tasks(self):
        """Start all stopped tasks."""
        for task in self.tasks:
            if task.status == TaskStatus.STOPPED:
                self.start_task(task.id)
    
    def stop_all_tasks(self):
        """Stop all running tasks."""
        for task in self.tasks:
            if task.status == TaskStatus.RUNNING:
                self.stop_task(task.id)
    
    def _run_task(self, task_id: str):
        """Run a task in its own thread."""
        task = self.get_task(task_id)
        if not task:
            return
        
        account = self.account_manager.get_account(task.account_id)
        account_name = account.name if account else "未知账号"
        course_name = task.course_info.kcmc
        class_name = task.course_info.jxb_mc
        
        self._emit_log(task_id, f"[{account_name}] 开始抢课: {course_name} - {class_name}", "info")
        
        # Ensure logged in
        if not self._ensure_logged_in(task.account_id):
            task.status = TaskStatus.FAILED
            task.last_message = "登录失败"
            self.save()
            self._emit_update(task)
            return
        
        api = self._get_api_session(task.account_id)
        
        while not self._stop_flags.get(task_id, False):
            task.attempt_count += 1
            task.last_attempt = datetime.now().isoformat()
            
            try:
                result = api.select_course(
                    task.course_info.jxb_ids,
                    task.course_info.kch_id,
                    task.course_info.kcmc,
                    task.course_info.gnmkdm
                )
                
                flag = result.get("flag", "-1")
                msg = result.get("msg", "未知结果")
                
                if flag == "1":
                    # Success!
                    if not msg or msg == "未知结果":
                        msg = "选课成功！"
                    task.status = TaskStatus.SUCCESS
                    task.last_message = msg
                    self.save()
                    self._emit_update(task)
                    self._emit_log(task_id, f"[{account_name}] 🎉 抢课成功: {course_name} - {msg}", "success")
                    if self.on_task_success:
                        self.on_task_success(task, msg)
                    return
                else:
                    # Check for conflict
                    if "冲突" in msg:
                        task.status = TaskStatus.CONFLICT
                        task.last_message = msg
                        self.save()
                        self._emit_update(task)
                        self._emit_log(task_id, f"[{account_name}] 🛑 时间冲突: {msg}", "error")
                        if self.on_task_error:
                            self.on_task_error(task, msg)
                        return
                    
                    # Continue trying
                    task.last_message = msg
                    self._emit_log(task_id, f"[{account_name}] 尝试 {task.attempt_count}: {msg}", "info")
                    
            except Exception as e:
                task.last_message = str(e)
                self._emit_log(task_id, f"[{account_name}] 尝试 {task.attempt_count}: 请求异常 - {e}", "warning")
            
            self._emit_update(task)
            time.sleep(task.interval)
        
        # Stopped by user
        task.status = TaskStatus.STOPPED
        task.last_message = "已停止"
        self.save()
        self._emit_update(task)
        self._emit_log(task_id, f"[{account_name}] ⏹ 任务已停止: {course_name}", "info")
    
    def clear_api_session(self, account_id: str):
        """Clear API session for account (e.g., after password change)."""
        if account_id in self._api_sessions:
            del self._api_sessions[account_id]
    
    def set_api_session(self, account_id: str, api: JwglxtAPI):
        """Set API session for account (shared from main GUI to avoid session conflicts)."""
        self._api_sessions[account_id] = api
    
    def get_api_session(self, account_id: str) -> Optional[JwglxtAPI]:
        """Get API session for account if it exists."""
        return self._api_sessions.get(account_id)


if __name__ == "__main__":
    # Simple test
    from account_manager import AccountManager
    
    acc_manager = AccountManager()
    task_manager = TaskManager(acc_manager)
    print(f"Loaded {len(task_manager.tasks)} tasks")
    for task in task_manager.tasks:
        print(f"  - {task.course_info.kcmc}: {task.status.value}")
