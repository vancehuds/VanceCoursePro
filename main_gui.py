"""
Course Selection GUI
Main graphical interface for automated course selection.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import time
import json
import os
import webbrowser

from jwglxt_api import JwglxtAPI
from account_manager import AccountManager, Account
from task_manager import TaskManager, GrabTask, CourseInfo, TaskStatus

# Application constants
APP_NAME = "VanceCoursePro"
APP_VERSION = "v1.0"



class AccountDialog:
    """Dialog for adding or editing an account."""
    
    def __init__(self, parent, title, name="", username="", password=""):
        self.result = None
        
        self.dialog = ttk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x280")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 250) // 2
        self.dialog.geometry(f"400x280+{x}+{y}")
        
        # Container
        container = ttk.Frame(self.dialog)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ttk.Label(
            container,
            text=f"{'➕' if not name else '✏️'} {title}",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        )
        header.pack(anchor="w", pady=(0, 15))
        
        # Form
        form = ttk.Frame(container)
        form.pack(fill="x")
        
        # Name
        name_row = ttk.Frame(form)
        name_row.pack(fill="x", pady=(0, 10))
        ttk.Label(name_row, text="名称:", width=8).pack(side="left")
        self.name_entry = ttk.Entry(name_row, width=30, font=("Segoe UI", 10))
        self.name_entry.pack(side="left", fill="x", expand=True)
        self.name_entry.insert(0, name)
        
        # Username
        username_row = ttk.Frame(form)
        username_row.pack(fill="x", pady=(0, 10))
        ttk.Label(username_row, text="学号:", width=8).pack(side="left")
        self.username_entry = ttk.Entry(username_row, width=30, font=("Segoe UI", 10))
        self.username_entry.pack(side="left", fill="x", expand=True)
        self.username_entry.insert(0, username)
        
        # Password
        password_row = ttk.Frame(form)
        password_row.pack(fill="x", pady=(0, 10))
        ttk.Label(password_row, text="密码:", width=8).pack(side="left")
        self.password_entry = ttk.Entry(password_row, width=30, font=("Segoe UI", 10), show="●")
        self.password_entry.pack(side="left", fill="x", expand=True)
        self.password_entry.insert(0, password)
        
        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(20, 0))
        
        ttk.Button(
            btn_frame,
            text="取消",
            command=self._on_cancel,
            bootstyle="secondary"
        ).pack(side="right", padx=(8, 0))
        
        ttk.Button(
            btn_frame,
            text="保存",
            command=self._on_save,
            bootstyle="success"
        ).pack(side="right")
        
        self.dialog.wait_window()
    
    def _on_save(self):
        name = self.name_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not name or not username or not password:
            messagebox.showwarning("警告", "请填写所有字段", parent=self.dialog)
            return
        
        self.result = (name, username, password)
        self.dialog.destroy()
    
    def _on_cancel(self):
        self.dialog.destroy()


class CourseSelectionApp:
    """Main application window with modern UI."""

    def __init__(self, root):
        self.root = root
        self.root.title("VanceCoursePro")
        self.root.geometry("1200x850")
        self.root.minsize(1100, 750)

        # Initialize managers
        self.account_manager = AccountManager()
        self.task_manager = TaskManager(self.account_manager)
        
        # Set up task manager callbacks
        self.task_manager.on_task_update = self._on_task_update
        self.task_manager.on_task_success = self._on_task_success
        self.task_manager.on_task_error = self._on_task_error
        self.task_manager.on_log = self._on_task_log
        
        # Current account (API session is managed by task_manager)
        self.current_account: Account = None
        
        self.courses = []
        self.classes = []
        self.current_page = 1
        
        self._create_widgets()
        self._load_accounts()
        self._refresh_task_list()

    def _create_card(self, parent, title):
        """Create a styled card container with title."""

        # Outer container with padding
        outer = ttk.Frame(parent)
        
        # Card frame - use tk.LabelFrame to avoid ttkbootstrap padding issue with Python 3.14
        card = tk.LabelFrame(
            outer,
            text=f"  {title}  "
        )
        card.pack(fill="both", expand=True)
        
        # Inner container for padding
        inner = ttk.Frame(card)
        inner.pack(fill="both", expand=True, padx=15, pady=15)
        
        return outer, inner

        
    def _create_widgets(self):
        """Create all UI elements with modern styling."""
        
        # Main container with padding
        main_container = ttk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        # ========== HEADER ==========
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 15))
        
        title_label = ttk.Label(
            header_frame,
            text=f"🎓 {APP_NAME}",
            font=("Segoe UI", 18, "bold"),
            bootstyle="primary"
        )
        title_label.pack(side="left")
        
        version_label = ttk.Label(
            header_frame,
            text=APP_VERSION,
            font=("Segoe UI", 10),
            bootstyle="secondary"
        )
        version_label.pack(side="left", padx=(10, 0), pady=(8, 0))
        
        # About button
        self.about_btn = ttk.Button(
            header_frame,
            text="ℹ️ 关于",
            command=self._on_about,
            bootstyle="secondary-outline"
        )
        self.about_btn.pack(side="right")
        
        # Settings button on the right
        self.settings_btn = ttk.Button(
            header_frame,
            text="⚙️ 设置",
            command=self._on_settings,
            bootstyle="secondary-outline"
        )
        self.settings_btn.pack(side="right", padx=(0, 8))
        
        # ========== MAIN LAYOUT (PanedWindow) ==========
        # Vertical split: Content on Top, Logs on Bottom
        main_paned = ttk.Panedwindow(main_container, orient="vertical")
        main_paned.pack(fill="both", expand=True)
        
        # Top Pane (Horizontal split: Courses vs Tasks)
        top_paned = ttk.Panedwindow(main_paned, orient="horizontal")
        main_paned.add(top_paned, weight=4)
        
        # Left Frame (Courses)
        left_frame = ttk.Frame(top_paned)
        top_paned.add(left_frame, weight=3)
        
        # Right Frame (Accounts + Tasks)
        right_frame = ttk.Frame(top_paned)
        top_paned.add(right_frame, weight=1)
        
        # Bottom Frame (Logs)
        bottom_frame = ttk.Frame(main_paned)
        main_paned.add(bottom_frame, weight=1)

        # ========== RIGHT SIDE: ACCOUNT & TASKS ==========
        
        # 1. Account Management (Top of Right Side)
        account_outer, account_card = self._create_card(right_frame, "🔐 账号管理")
        account_outer.pack(fill="x", pady=(0, 10))
        
        # Account management row
        account_row = ttk.Frame(account_card)
        account_row.pack(fill="x")
        
        # Account selector (Compact)
        row1 = ttk.Frame(account_row)
        row1.pack(fill="x", pady=(0, 5))
        
        ttk.Label(row1, text="账号").pack(side="left", padx=(0, 5))
        self.account_combobox = ttk.Combobox(row1, width=18, state="readonly")
        self.account_combobox.pack(side="left", fill="x", expand=True)
        self.account_combobox.bind("<<ComboboxSelected>>", self._on_account_selected)
        
        # Status indicator
        self.status_frame = ttk.Frame(row1)
        self.status_frame.pack(side="right")
        
        self.status_dot = tk.Canvas(
            self.status_frame,
            width=10, height=10,
            highlightthickness=0
        )
        self.status_dot.pack(side="left", padx=(5, 5))
        self.status_dot.create_oval(2, 2, 10, 10, fill="gray", outline="")
        
        # Account buttons (Row 2)
        row2 = ttk.Frame(account_row)
        row2.pack(fill="x")
        
        self.add_account_btn = ttk.Button(row2, text="➕", width=3, command=self._on_add_account, bootstyle="secondary")
        self.add_account_btn.pack(side="left", padx=(0, 2))
        
        self.edit_account_btn = ttk.Button(row2, text="✏️", width=3, command=self._on_edit_account, bootstyle="secondary")
        self.edit_account_btn.pack(side="left", padx=(0, 2))
        
        self.delete_account_btn = ttk.Button(row2, text="🗑", width=3, command=self._on_delete_account, bootstyle="danger")
        self.delete_account_btn.pack(side="left", padx=(0, 5))
        
        self.login_btn = ttk.Button(row2, text="登录", width=6, command=self._on_login, bootstyle="success")
        self.login_btn.pack(side="right")
        
        self.status_label = ttk.Label(self.status_frame, text="未登录", bootstyle="secondary")

        # 2. Task Management (Rest of Right Side)
        task_outer, task_card = self._create_card(right_frame, "📋 抢课任务")
        task_outer.pack(fill="both", expand=True)
        
        # Task list treeview
        task_tree_container = ttk.Frame(task_card)
        task_tree_container.pack(fill="both", expand=True, pady=(0, 8))
        
        task_columns = ("status", "course", "interval", "attempts", "message")
        self.task_tree = ttk.Treeview(
            task_tree_container,
            columns=task_columns,
            show="headings",
            selectmode="browse",
            height=4,
            bootstyle="primary"
        )
        
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("course", text="课程")
        self.task_tree.heading("interval", text="间隔")
        self.task_tree.heading("attempts", text="尝试")
        self.task_tree.heading("message", text="消息")
        
        self.task_tree.column("status", width=35, anchor="center")
        self.task_tree.column("course", width=90)
        self.task_tree.column("interval", width=35, anchor="center")
        self.task_tree.column("attempts", width=35, anchor="center")
        self.task_tree.column("message", width=100)
        
        task_scrollbar = ttk.Scrollbar(task_tree_container, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=task_scrollbar.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        task_scrollbar.pack(side="right", fill="y")
        
        self.task_tree.bind("<Double-1>", lambda e: self._on_edit_task())
        
        # Task control buttons
        task_btn_row = ttk.Frame(task_card)
        task_btn_row.pack(fill="x")
        
        self.start_task_btn = ttk.Button(task_btn_row, text="启动", width=4, command=self._on_start_task, bootstyle="success")
        self.start_task_btn.pack(side="left", padx=(0, 2))
        
        self.stop_task_btn = ttk.Button(task_btn_row, text="暂停", width=4, command=self._on_stop_task, bootstyle="warning")
        self.stop_task_btn.pack(side="left", padx=(0, 2))
        
        self.edit_task_btn = ttk.Button(task_btn_row, text="✏", width=3, command=self._on_edit_task, bootstyle="secondary")
        self.edit_task_btn.pack(side="left", padx=(0, 2))
        
        self.delete_task_btn = ttk.Button(task_btn_row, text="🗑", width=3, command=self._on_delete_task, bootstyle="danger")
        self.delete_task_btn.pack(side="left", padx=(0, 5))
        
        self.start_all_btn = ttk.Button(task_btn_row, text="全启", width=4, command=self._on_start_all_tasks, bootstyle="success-outline")
        self.start_all_btn.pack(side="left", padx=(0, 2))
        
        self.stop_all_btn = ttk.Button(task_btn_row, text="全停", width=4, command=self._on_stop_all_tasks, bootstyle="warning-outline")
        self.stop_all_btn.pack(side="left")
        
        self.task_count_label = ttk.Label(task_btn_row, text="0", bootstyle="secondary")
        self.task_count_label.pack(side="right")

        # ========== LEFT SIDE: COURSE SELECTION ==========
        course_outer, course_card = self._create_card(left_frame, "📚 课程列表")
        course_outer.pack(fill="both", expand=True)

        # Control toolbar
        toolbar = ttk.Frame(course_card)
        toolbar.pack(fill="x", pady=(0, 12))
        
        # Left side buttons
        btn_left = ttk.Frame(toolbar)
        btn_left.pack(side="left")
        
        self.load_courses_btn = ttk.Button(btn_left, text="📥 加载列表", command=self._on_load_courses, state="disabled", bootstyle="info")
        self.load_courses_btn.pack(side="left", padx=(0, 4))

        self.load_more_btn = ttk.Button(btn_left, text="📄 更多", command=self._on_load_more_courses, state="disabled", bootstyle="info-outline")
        self.load_more_btn.pack(side="left", padx=(0, 4))

        self.load_all_btn = ttk.Button(btn_left, text="📦 全部", command=self._on_load_all_courses, state="disabled", bootstyle="info-outline")
        self.load_all_btn.pack(side="left", padx=(0, 4))
        
        ttk.Separator(btn_left, orient="vertical").pack(side="left", fill="y", padx=8)

        self.load_all_details_btn = ttk.Button(btn_left, text="🔍 一键详情", command=self._on_load_all_details, state="disabled", bootstyle="primary")
        self.load_all_details_btn.pack(side="left", padx=(0, 4))

        self.load_details_only_btn = ttk.Button(btn_left, text="📋 仅详情", command=self._on_load_details_only, state="disabled", bootstyle="primary-outline")
        self.load_details_only_btn.pack(side="left", padx=(0, 4))

        # Right side - filters
        filter_frame = ttk.Frame(toolbar)
        filter_frame.pack(side="right")
        
        self.tab_combobox = ttk.Combobox(filter_frame, width=10, state="readonly")
        self.tab_combobox.pack(side="left", padx=(0, 8))

        self.search_entry = ttk.Entry(filter_frame, width=15, font=("Segoe UI", 10))
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda e: self._on_load_courses())

        # Course Treeview with custom styling
        tree_container = ttk.Frame(course_card)
        tree_container.pack(fill="both", expand=True, pady=(0, 12))

        columns = ("kch_id", "kcmc", "xf", "yxzt", "jxb_mc", "jsxx", "yxzrs")
        display_columns = ("kch_id", "kcmc", "xf" , "jxb_mc", "jsxx", "yxzrs")
        
        self.course_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            displaycolumns=display_columns,
            show="headings",
            selectmode="browse",
            bootstyle="primary"
        )
        
        self.course_tree.heading("kch_id", text="代码")
        self.course_tree.heading("kcmc", text="课程名称")
        self.course_tree.heading("xf", text="学分")
        self.course_tree.heading("yxzt", text="★是否已选")
        self.course_tree.heading("jxb_mc", text="教学班")
        self.course_tree.heading("jsxx", text="教师")
        self.course_tree.heading("yxzrs", text="余量")

        self.course_tree.column("kch_id", width=80, anchor="center")
        self.course_tree.column("kcmc", width=180)
        self.course_tree.column("xf", width=40, anchor="center")
        self.course_tree.column("yxzt", width=30, anchor="center")
        self.course_tree.column("jxb_mc", width=100)
        self.course_tree.column("jsxx", width=80)
        self.course_tree.column("yxzrs", width=60, anchor="center")

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        self.course_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.course_tree.bind("<<TreeviewSelect>>", self._on_course_select)

        # Action buttons row
        action_row = ttk.Frame(course_card)
        action_row.pack(fill="x")
        
        # Grab section
        grab_section = ttk.Frame(action_row)
        grab_section.pack(side="left")
        
        self.add_task_btn = ttk.Button(grab_section, text="➕ 任务", command=self._on_add_task, state="disabled", bootstyle="success")
        self.add_task_btn.pack(side="left", padx=(0, 6))

        self.drop_btn = ttk.Button(grab_section, text="🗑 退选", command=self._on_drop, state="disabled", bootstyle="danger")
        self.drop_btn.pack(side="left", padx=(0, 10))
        
        self.view_details_btn = ttk.Button(grab_section, text="👁 详情", command=self._on_view_details, state="disabled", bootstyle="info")
        self.view_details_btn.pack(side="left", padx=(0, 6))

        # Interval setting
        interval_section = ttk.Frame(action_row)
        interval_section.pack(side="left")
        
        ttk.Label(interval_section, text="间隔(s)").pack(side="left", padx=(0, 4))
        self.interval_entry = ttk.Entry(interval_section, width=4, font=("Segoe UI", 10))
        self.interval_entry.insert(0, "0.5")
        self.interval_entry.pack(side="left")
        
        self.count_label = ttk.Label(action_row, text="0 门", bootstyle="secondary")
        self.count_label.pack(side="right")

        # ========== LOG SECTION ==========
        log_outer, log_card = self._create_card(bottom_frame, "📝 运行日志")
        log_outer.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_card,
            height=8,
            font=("JetBrains Mono", 9),
            relief="flat",
            padx=10,
            pady=8,
            wrap="word"
        )
        
        self.log_text.tag_configure("timestamp", foreground="gray")
        self.log_text.tag_configure("info", foreground="white")
        self.log_text.tag_configure("success", foreground="#3fb950")
        self.log_text.tag_configure("warning", foreground="#d29922")
        self.log_text.tag_configure("error", foreground="#f85149")
        
        log_scrollbar = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set, state="disabled")
        
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")

    def _log(self, message: str, level: str = "info"):
        """Append message to log area with color coding."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        
        # Insert timestamp
        self.log_text.insert("end", f"[{timestamp}] ", "timestamp")
        
        # Determine log level from message content if not specified
        if level == "info":
            if "✅" in message or "成功" in message or "🎉" in message:
                level = "success"
            elif "警告" in message or "⚠" in message:
                level = "warning"
            elif "错误" in message or "失败" in message or "❌" in message or "🛑" in message:
                level = "error"
        
        # Insert message with appropriate tag
        self.log_text.insert("end", f"{message}\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_status(self, text: str, status: str = "default"):
        """Update status indicator."""
        colors = {
            "default": "gray",
            "loading": "#d29922",
            "success": "#3fb950",
            "error": "#f85149"
        }
        color = colors.get(status, "gray")
        
        self.status_dot.delete("all")
        self.status_dot.create_oval(2, 2, 10, 10, fill=color, outline="")
        
        self.status_label.configure(text=text)
        
        bootstyle_map = {
            "default": "secondary",
            "loading": "warning",
            "success": "success",
            "error": "danger"
        }
        self.status_label.configure(bootstyle=bootstyle_map.get(status, "secondary"))

    def _load_accounts(self):
        """Load accounts from account manager and populate the dropdown."""
        accounts = self.account_manager.get_all_accounts()
        
        if accounts:
            account_names = [f"{acc.name} ({acc.username})" for acc in accounts]
            self.account_combobox['values'] = account_names
            
            # Select default account
            default = self.account_manager.get_default_account()
            if default:
                for i, acc in enumerate(accounts):
                    if acc.id == default.id:
                        self.account_combobox.current(i)
                        self.current_account = acc
                        break
            
            self._log(f"📂 已加载 {len(accounts)} 个账号")
        else:
            self._log("ℹ️ 尚未添加账号，请点击'添加'按钮添加账号")
    
    def _on_account_selected(self, event=None):
        """Handle account selection change."""
        idx = self.account_combobox.current()
        accounts = self.account_manager.get_all_accounts()
        if 0 <= idx < len(accounts):
            self.current_account = accounts[idx]
            self.account_manager.set_default_account(self.current_account.id)
            
            # Check if this account has an active session
            api = self.task_manager.get_api_session(self.current_account.id)
            if api and hasattr(api, 'student_info') and api.student_info:
                self._update_status(f"已登录: {self.current_account.name}", "success")
                self._log(f"📌 已选择账号: {self.current_account.name} (已登录)")
                self._enable_course_buttons()
                # Load tabs from existing session
                self._load_tabs_from_session(api)
            else:
                self._update_status("未登录", "default")
                self._log(f"📌 已选择账号: {self.current_account.name}")
                self._disable_course_buttons()
    
    def _on_add_account(self):
        """Show dialog to add a new account."""
        dialog = AccountDialog(self.root, "添加账号")
        if dialog.result:
            name, username, password = dialog.result
            account = self.account_manager.add_account(name, username, password)
            self._load_accounts()
            # Select the new account
            accounts = self.account_manager.get_all_accounts()
            for i, acc in enumerate(accounts):
                if acc.id == account.id:
                    self.account_combobox.current(i)
                    self.current_account = acc
                    break
            self._log(f"✅ 已添加账号: {name}", "success")
    
    def _on_edit_account(self):
        """Show dialog to edit the selected account."""
        if not self.current_account:
            messagebox.showwarning("警告", "请先选择一个账号")
            return
        
        dialog = AccountDialog(
            self.root, 
            "编辑账号",
            name=self.current_account.name,
            username=self.current_account.username,
            password=self.current_account.password
        )
        if dialog.result:
            name, username, password = dialog.result
            self.account_manager.update_account(
                self.current_account.id,
                name=name,
                username=username,
                password=password
            )
            self._load_accounts()
            self._log(f"✅ 已更新账号: {name}", "success")
    
    def _on_delete_account(self):
        """Delete the selected account."""
        if not self.current_account:
            messagebox.showwarning("警告", "请先选择一个账号")
            return
        
        confirm = messagebox.askyesno(
            "确认删除",
            f"确定要删除账号 '{self.current_account.name}' 吗？\n\n相关的抢课任务不会被自动删除。"
        )
        if confirm:
            name = self.current_account.name
            self.account_manager.remove_account(self.current_account.id)
            self.current_account = None
            self._load_accounts()
            self._log(f"🗑 已删除账号: {name}")

    def _on_about(self):
        """Show about dialog with project information."""
        dialog = ttk.Toplevel(self.root)
        dialog.title("关于")
        dialog.geometry("480x450")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 480) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 450) // 2
        dialog.geometry(f"480x450+{x}+{y}")
        
        # Container
        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=30, pady=25)
        
        # App icon and name
        title_frame = ttk.Frame(container)
        title_frame.pack(fill="x", pady=(0, 15))
        
        app_icon = ttk.Label(
            title_frame,
            text="🎓",
            font=("Segoe UI", 36)
        )
        app_icon.pack()
        
        app_name_label = ttk.Label(
            title_frame,
            text=APP_NAME,
            font=("Segoe UI", 18, "bold"),
            bootstyle="primary"
        )
        app_name_label.pack(pady=(5, 0))
        
        version_label = ttk.Label(
            title_frame,
            text=APP_VERSION,
            font=("Segoe UI", 11),
            bootstyle="secondary"
        )
        version_label.pack()
        
        # Separator
        ttk.Separator(container, orient="horizontal").pack(fill="x", pady=15)
        
        # Description
        desc_label = ttk.Label(
            container,
            text="一款基于 Python 的正方教务系统自动化选课工具",
            font=("Segoe UI", 10),
            wraplength=380,
            justify="center"
        )
        desc_label.pack(pady=(0, 5))
        
        features_label = ttk.Label(
            container,
            text="支持多账号管理、自动抢课、课程退选等功能",
            font=("Segoe UI", 9),
            bootstyle="secondary",
            wraplength=380,
            justify="center"
        )
        features_label.pack(pady=(0, 15))
        
        # GitHub link
        github_url = "https://github.com/vancehuds/VanceCoursePro"
        
        github_frame = ttk.Frame(container)
        github_frame.pack(pady=(0, 10))
        
        github_icon = ttk.Label(
            github_frame,
            text="📦 开源地址:",
            font=("Segoe UI", 10)
        )
        github_icon.pack(side="left")
        
        github_link = ttk.Label(
            github_frame,
            text=github_url,
            font=("Segoe UI", 10, "underline"),
            bootstyle="info",
            cursor="hand2"
        )
        github_link.pack(side="left", padx=(5, 0))
        github_link.bind("<Button-1>", lambda e: webbrowser.open(github_url))
        
        # Copyright
        copyright_label = ttk.Label(
            container,
            text="© 2025 VanceCoursePro Contributors",
            font=("Segoe UI", 9),
            bootstyle="secondary"
        )
        copyright_label.pack(pady=(15, 0))
        
        license_label = ttk.Label(
            container,
            text="MIT License",
            font=("Segoe UI", 9),
            bootstyle="secondary"
        )
        license_label.pack()
        
        # Close button
        ttk.Button(
            container,
            text="关闭",
            command=dialog.destroy,
            bootstyle="secondary",
            width=10
        ).pack(pady=(20, 0))

    def _on_settings(self):
        """Show settings dialog to configure base URL."""
        dialog = ttk.Toplevel(self.root)
        dialog.title("设置")
        dialog.geometry("500x260")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        dialog.geometry(f"500x260+{x}+{y}")
        
        # Container
        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ttk.Label(
            container,
            text="⚙️ 应用设置",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        )
        header.pack(anchor="w", pady=(0, 15))
        
        # Base URL row
        url_frame = ttk.Frame(container)
        url_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(url_frame, text="服务器地址:", width=10).pack(side="left")
        url_entry = ttk.Entry(url_frame, width=50, font=("Segoe UI", 10))
        url_entry.pack(side="left", fill="x", expand=True)
        url_entry.insert(0, self.account_manager.get_base_url())
        
        # Hint label
        hint = ttk.Label(
            container,
            text="提示：修改后需要重新登录才能生效",
            bootstyle="secondary",
            font=("Segoe UI", 9)
        )
        hint.pack(anchor="w", pady=(0, 15))
        
        def on_save():
            new_url = url_entry.get().strip()
            if new_url:
                self.account_manager.set_base_url(new_url)
                self._log(f"✅ 服务器地址已更新为: {new_url}", "success")
                messagebox.showinfo("成功", "服务器地址已保存，请重新登录以使用新地址。", parent=dialog)
            else:
                self.account_manager.set_base_url(self.account_manager.DEFAULT_BASE_URL)
                self._log(f"✅ 服务器地址已重置为默认值", "success")
            dialog.destroy()
        
        def on_reset():
            url_entry.delete(0, "end")
            url_entry.insert(0, self.account_manager.DEFAULT_BASE_URL)
        
        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x")
        
        ttk.Button(
            btn_frame,
            text="取消",
            command=dialog.destroy,
            bootstyle="secondary"
        ).pack(side="right", padx=(8, 0))
        
        ttk.Button(
            btn_frame,
            text="保存",
            command=on_save,
            bootstyle="success"
        ).pack(side="right")
        
        ttk.Button(
            btn_frame,
            text="重置默认",
            command=on_reset,
            bootstyle="warning-outline"
        ).pack(side="left")

    def _on_login(self):
        """Handle login button click for the selected account."""
        if not self.current_account:
            self._log("⚠ 警告: 请先选择或添加一个账号。", "warning")
            return

        username = self.current_account.username
        password = self.current_account.password

        if not username or not password:
            self._log("⚠ 警告: 账号信息不完整。", "warning")
            return

        self.login_btn.configure(state="disabled")
        self._update_status("登录中...", "loading")
        self._log(f"🔄 正在登录: {self.current_account.name} ({username})...")

        account_id = self.current_account.id
        
        def do_login():
            try:
                base_url = self.account_manager.get_base_url()
                api = JwglxtAPI(base_url=base_url)  # Create new session with configured base URL
                api.login(username, password)
                api.init_course_selection()
                # Store session in task manager (bound to account)
                self.task_manager.set_api_session(account_id, api)
                self.root.after(0, lambda: self._on_login_success())
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._on_login_fail(err))

        threading.Thread(target=do_login, daemon=True).start()
    
    @property
    def api(self) -> JwglxtAPI:
        """Get the API session for the current account."""
        if self.current_account:
            api = self.task_manager.get_api_session(self.current_account.id)
            if api:
                return api
        # Return a dummy API if no session exists (will fail gracefully)
        return JwglxtAPI(base_url=self.account_manager.get_base_url())
    
    def _enable_course_buttons(self):
        """Enable course-related buttons."""
        self.load_courses_btn.configure(state="normal")
        self.load_all_btn.configure(state="normal")
        self.load_all_details_btn.configure(state="normal")
        self.load_details_only_btn.configure(state="disabled")
        self.load_more_btn.configure(state="disabled")
    
    def _disable_course_buttons(self):
        """Disable course-related buttons."""
        self.load_courses_btn.configure(state="disabled")
        self.load_all_btn.configure(state="disabled")
        self.load_all_details_btn.configure(state="disabled")
        self.load_details_only_btn.configure(state="disabled")
        self.load_more_btn.configure(state="disabled")
    
    def _load_tabs_from_session(self, api: JwglxtAPI):
        """Load tabs from an existing API session."""
        tabs = api.student_info.get('tabs', [])
        if tabs:
            tab_names = [t['name'] for t in tabs]
            self.tab_combobox['values'] = tab_names
            if tab_names:
                self.tab_combobox.current(0)

    def _on_login_success(self):
        """Update UI after successful login."""
        self._update_status(f"已登录: {self.current_account.name}", "success")
        self.login_btn.configure(state="normal")
        self._enable_course_buttons()
        self._log("✅ 登录成功！", "success")
        api = self.task_manager.get_api_session(self.current_account.id)
        if api:
            self._log(f"📋 学生信息: njdm_id={api.student_info.get('njdm_id')}, zyh_id={api.student_info.get('zyh_id')}")
            self._load_tabs_from_session(api)
            tabs = api.student_info.get('tabs', [])
            if tabs:
                self._log(f"📑 获取到课程类型: {[t['name'] for t in tabs]}")
            else:
                self._log("⚠ 未获取到课程类型选项", "warning")

    def _on_login_fail(self, error: str):
        """Update UI after failed login."""
        self._update_status("登录失败", "error")
        self.login_btn.configure(state="normal")
        self._log(f"❌ 登录失败: {error}", "error")

    def _on_load_courses(self):
        """Handle load courses button click."""
        self.load_courses_btn.configure(state="disabled")
        filter_name = self.search_entry.get().strip()
        
        # Determine selected tab
        selected_name = self.tab_combobox.get()
        selected_tab = None
        for t in self.api.student_info.get('tabs', []):
            if t['name'] == selected_name:
                selected_tab = t
                break
        
        if selected_tab:
            self.api.student_info['kklxdm'] = selected_tab['kklxdm']
            self.api.student_info['xkkz_id'] = selected_tab['xkkz_id']
            if 'rwlx' in selected_tab:
                self.api.student_info['rwlx'] = selected_tab['rwlx']
            self._log(f"📂 切换至: {selected_name}")

        self._log(f"🔄 正在加载课程列表..." + (f" (搜索: {filter_name})" if filter_name else ""))
        
        self.current_page = 1

        def do_load():
            try:
                courses = self.api.get_course_list(filter_name=filter_name if filter_name else None, page=1)
                self.root.after(0, lambda: self._update_course_list(courses, clear=True))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._on_load_fail(err))

        threading.Thread(target=do_load, daemon=True).start()

    def _update_course_list(self, courses: list, clear: bool = True):
        """Update treeview with course data."""
        if clear:
            self.course_tree.delete(*self.course_tree.get_children())
            self.courses = []
            
        self.courses.extend(courses)
        for c in courses:
            # Check if course is already selected based on xxkbj field
            selected_status = "★" if c.get("xxkbj") == "1" else ""
            self.course_tree.insert("", "end", values=(
                c.get("kch_id", ""),
                c.get("kcmc", ""),
                c.get("xf", ""),
                selected_status,
                "",
                "",
                "",
            ))
        
        self.load_courses_btn.configure(state="normal")
        if courses:
             self.load_more_btn.configure(state="normal")
        else:
             self.load_more_btn.configure(state="disabled")
             if not clear:
                  self._log("📭 没有更多课程了。")
        
        if self.courses:
            self.load_details_only_btn.configure(state="normal")
        else:
            self.load_details_only_btn.configure(state="disabled")
        
        # Update count label
        self.count_label.configure(text=f"共 {len(self.courses)} 门课程")
                   
        self._log(f"✅ 加载完成，本次 {len(courses)} 门，总共 {len(self.courses)} 门。", "success")

    def _on_load_more_courses(self):
        """Handle load more courses button click."""
        self.load_more_btn.configure(state="disabled")
        self.current_page += 1
        filter_name = self.search_entry.get().strip()
        
        self._log(f"🔄 正在加载第 {self.current_page} 页...")

        def do_load_more():
            try:
                courses = self.api.get_course_list(filter_name=filter_name if filter_name else None, page=self.current_page)
                self.root.after(0, lambda: self._update_course_list(courses, clear=False))
            except Exception as e:
                self.current_page -= 1
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._on_load_fail(err))

        threading.Thread(target=do_load_more, daemon=True).start()

    def _on_load_all_courses(self):
        """Handle load ALL courses button click."""
        self.load_courses_btn.configure(state="disabled")
        self.load_more_btn.configure(state="disabled")
        self.load_all_btn.configure(state="disabled")
        
        filter_name = self.search_entry.get().strip()
        self._log(f"🔄 开始加载全部课程...")

        def do_load_all():
            all_courses = []
            page = 1
            limit = 10
            
            try:
                while True:
                    self.root.after(0, lambda p=page: self._log(f"📄 正在获取第 {p} 页..."))
                    courses = self.api.get_course_list(filter_name=filter_name if filter_name else None, page=page, limit=limit)
                    if not courses:
                        break
                    
                    all_courses.extend(courses)
                    
                    if len(courses) < limit:
                        break
                    
                    page += 1
                    time.sleep(0.3)

                unique_courses = []
                seen_ids = set()
                for c in all_courses:
                    if c['kch_id'] not in seen_ids:
                        unique_courses.append(c)
                        seen_ids.add(c['kch_id'])
                
                self.current_page = page - 1
                self.root.after(0, lambda: self._update_course_list(unique_courses, clear=True))
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._on_load_fail(err))
            finally:
                self.root.after(0, lambda: self.load_all_btn.configure(state="normal"))

        threading.Thread(target=do_load_all, daemon=True).start()

    def _on_load_all_details(self):
        """Handle load ALL courses WITH details button click."""
        self.load_courses_btn.configure(state="disabled")
        self.load_more_btn.configure(state="disabled")
        self.load_all_btn.configure(state="disabled")
        self.load_all_details_btn.configure(state="disabled")
        
        filter_name = self.search_entry.get().strip()
        self._log(f"🔄 开始一键加载全部课程详情...")

        def do_load_all_with_details():
            all_courses = []
            page = 1
            limit = 10
            
            try:
                while True:
                    self.root.after(0, lambda p=page: self._log(f"📄 正在获取第 {p} 页课程..."))
                    courses = self.api.get_course_list(filter_name=filter_name if filter_name else None, page=page, limit=limit)
                    if not courses:
                        break
                    
                    all_courses.extend(courses)
                    
                    if len(courses) < limit:
                        break
                    
                    page += 1
                    time.sleep(0.3)

                unique_courses = []
                seen_ids = set()
                for c in all_courses:
                    if c['kch_id'] not in seen_ids:
                        unique_courses.append(c)
                        seen_ids.add(c['kch_id'])
                
                self.current_page = page - 1
                self.root.after(0, lambda: self._update_course_list(unique_courses, clear=True))
                self.root.after(0, lambda: self._log(f"📚 课程列表加载完成,共 {len(unique_courses)} 门课程", "success"))
                
                self.root.after(0, lambda: self._log(f"🔍 开始加载每门课程的教学班详情..."))
                
                for idx, course in enumerate(unique_courses, 1):
                    kch_id = course.get('kch_id')
                    if not kch_id:
                        continue
                    
                    try:
                        self.root.after(0, lambda i=idx, total=len(unique_courses), name=course.get('kcmc', ''): 
                                      self._log(f"[{i}/{total}] 加载 {name} 的教学班信息..."))
                        
                        classes = self.api.get_class_list(kch_id)
                        
                        if classes:
                            course_index = idx - 1
                            self.root.after(0, lambda ci=course_index, cls=classes: self._update_course_details_in_tree(ci, cls))
                        
                        time.sleep(0.2)
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda err=error_msg, name=course.get('kcmc', ''): 
                                      self._log(f"⚠ 加载 {name} 详情失败: {err}", "warning"))
                
                self.root.after(0, lambda: self._log(f"✅ 全部课程详情加载完成！", "success"))
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._log(f"❌ 加载失败: {err}", "error"))
            finally:
                self.root.after(0, lambda: self.load_courses_btn.configure(state="normal"))
                self.root.after(0, lambda: self.load_all_btn.configure(state="normal"))
                self.root.after(0, lambda: self.load_all_details_btn.configure(state="normal"))

        threading.Thread(target=do_load_all_with_details, daemon=True).start()

    def _on_load_details_only(self):
        """Handle load details for currently loaded courses."""
        if not self.courses:
            self._log("⚠ 警告: 请先加载课程列表。", "warning")
            return
        
        self.load_courses_btn.configure(state="disabled")
        self.load_more_btn.configure(state="disabled")
        self.load_all_btn.configure(state="disabled")
        self.load_all_details_btn.configure(state="disabled")
        self.load_details_only_btn.configure(state="disabled")
        
        self._log(f"🔍 开始为 {len(self.courses)} 门课程加载教学班详情...")

        def do_load_details():
            try:
                for idx, course in enumerate(self.courses, 1):
                    kch_id = course.get('kch_id')
                    if not kch_id:
                        continue
                    
                    try:
                        self.root.after(0, lambda i=idx, total=len(self.courses), name=course.get('kcmc', ''): 
                                      self._log(f"[{i}/{total}] 加载 {name} 的教学班信息..."))
                        
                        classes = self.api.get_class_list(kch_id)
                        
                        if classes:
                            course_index = idx - 1
                            self.root.after(0, lambda ci=course_index, cls=classes: self._update_course_details_in_tree(ci, cls))
                        
                        time.sleep(0.2)
                        
                    except Exception as e:
                        error_msg = str(e)
                        self.root.after(0, lambda err=error_msg, name=course.get('kcmc', ''): 
                                      self._log(f"⚠ 加载 {name} 详情失败: {err}", "warning"))
                
                self.root.after(0, lambda: self._log(f"✅ 课程详情加载完成！", "success"))
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._log(f"❌ 加载失败: {err}", "error"))
            finally:
                self.root.after(0, lambda: self.load_courses_btn.configure(state="normal"))
                self.root.after(0, lambda: self.load_all_btn.configure(state="normal"))
                self.root.after(0, lambda: self.load_all_details_btn.configure(state="normal"))
                self.root.after(0, lambda: self.load_details_only_btn.configure(state="normal"))

        threading.Thread(target=do_load_details, daemon=True).start()

    def _update_course_details_in_tree(self, course_index: int, classes: list):
        """Update a specific course item in the tree with class details."""
        try:
            items = self.course_tree.get_children()
            if course_index >= len(items):
                return
            
            tree_item = items[course_index]
            
            if classes:
                c = classes[0]
                current = list(self.course_tree.item(tree_item, 'values'))
                selected_status = ""
                for cls in classes:
                    if cls.get("sxbj") == "1":
                        selected_status = "✓"
                        break
                current[3] = selected_status
                current[4] = c.get("jxb_mc", "")
                current[5] = c.get("jsxx", "")
                remaining = c.get("yxzrs", "")
                total = c.get("jxbrl", "")
                capacity_display = f"{remaining}/{total}" if remaining and total else remaining or total or ""
                current[6] = capacity_display
                self.course_tree.item(tree_item, values=current)
        except Exception as e:
            self._log(f"⚠ 更新课程详情显示失败: {e}", "warning")

    def _on_view_details(self):
        """Show details for the selected course."""
        selection = self.course_tree.selection()
        if not selection:
            return
        
        if not self.classes:
            messagebox.showinfo("提示", "正在加载教学班信息，请稍候...")
            return
        
        item = self.course_tree.item(selection[0])
        course_name = item['values'][1]
        
        # Create modern popup
        top = tk.Toplevel(self.root)
        top.title(f"📖 课程详情: {course_name}")
        top.geometry("900x550")
        # No special background config needed - ttkbootstrap handles theming
        
        # Container
        container = ttk.Frame(top, style="TFrame")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ttk.Label(
            container,
            text=f"📚 {course_name}",
            font=("Segoe UI", 14, "bold"),
            bootstyle="primary"
        )
        header.pack(anchor="w", pady=(0, 15))
        
        # Details Treeview
        columns = ("jxb_mc", "jsxx", "sksj", "jxdd", "yxzrs", "xkbz")
        detail_tree = ttk.Treeview(container, columns=columns, show="headings")
        
        detail_tree.heading("jxb_mc", text="🏫 教学班")
        detail_tree.heading("jsxx", text="👨‍🏫 教师")
        detail_tree.heading("sksj", text="⏰ 上课时间")
        detail_tree.heading("jxdd", text="📍 地点")
        detail_tree.heading("yxzrs", text="📊 余量/总量")
        detail_tree.heading("xkbz", text="📝 备注")
        
        detail_tree.column("jxb_mc", width=120)
        detail_tree.column("jsxx", width=100)
        detail_tree.column("sksj", width=220)
        detail_tree.column("jxdd", width=120)
        detail_tree.column("yxzrs", width=80, anchor="center")
        detail_tree.column("xkbz", width=200)
        
        detail_tree.pack(fill="both", expand=True)
        
        # Populate
        for c in self.classes:
            remaining = c.get("yxzrs", "")
            total = c.get("jxbrl", "")
            capacity_display = f"{remaining}/{total}" if remaining and total else remaining or total or ""
            
            detail_tree.insert("", "end", values=(
                c.get("jxb_mc", ""),
                c.get("jsxx", ""),
                c.get("sksj", ""),
                c.get("jxdd", ""),
                capacity_display,
                c.get("xkbz", "")
            ))
            
        # Close button
        btn_frame = ttk.Frame(container, style="TFrame")
        btn_frame.pack(fill="x", pady=(15, 0))
        
        ttk.Button(
            btn_frame,
            text="关闭",
            command=top.destroy
        ).pack(side="right")

    def _on_load_fail(self, error: str):
        """Handle course load failure."""
        self.load_courses_btn.configure(state="normal")
        self.load_more_btn.configure(state="normal")
        self.load_all_btn.configure(state="normal")
        self._log(f"❌ 加载课程失败: {error}", "error")

    def _on_course_select(self, event):
        """Handle course selection in treeview."""
        selection = self.course_tree.selection()
        if not selection:
            return
        item = self.course_tree.item(selection[0])
        kch_id = item['values'][0]
        self._log(f"📌 选择课程: {kch_id}, 正在加载教学班...")

        def do_load_classes():
            try:
                classes = self.api.get_class_list(kch_id)
                self.classes = classes
                self.root.after(0, lambda: self._display_classes(selection[0], classes))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._log(f"❌ 加载教学班失败: {err}", "error"))

        threading.Thread(target=do_load_classes, daemon=True).start()

    def _display_classes(self, tree_item, classes: list):
        """Display class info for selected course."""
        if classes:
            c = classes[0]
            current = list(self.course_tree.item(tree_item, 'values'))
            selected_status = ""
            for cls in classes:
                if cls.get("sxbj") == "1":
                    selected_status = "✓"
                    break
            current[3] = selected_status
            current[4] = c.get("jxb_mc", "")
            current[5] = c.get("jsxx", "")
            remaining = c.get("yxzrs", "")
            total = c.get("jxbrl", "")
            capacity_display = f"{remaining}/{total}" if remaining and total else remaining or total or ""
            current[6] = capacity_display
            self.course_tree.item(tree_item, values=current)
            self.add_task_btn.configure(state="normal")
            self.view_details_btn.configure(state="normal")
            self.drop_btn.configure(state="normal")
            self._log(f"✅ 找到 {len(classes)} 个教学班。" + ("（已选）" if selected_status else ""), "success")
        else:
            self._log("⚠ 未找到教学班。", "warning")

    def _select_class_dialog(self, title: str, action_text: str) -> dict | None:
        """Show a dialog to select a teaching class. Returns the selected class dict or None if cancelled."""
        if not self.classes:
            return None
        
        # If only one class, return it directly
        if len(self.classes) == 1:
            return self.classes[0]
        
        # Result variable
        if not self.classes:
            self._log("⚠ 警告: 没有可用的教学班信息。", "warning")
            return None

        selected_class = {"result": None}
        
        # Create dialog
        dialog = ttk.Toplevel(self.root)
        dialog.title(f"选择教学班 - {action_text}")
        dialog.geometry("800x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 800) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"800x500+{x}+{y}")
        
        # Container
        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        ttk.Label(
            container,
            text=f"🎯 {title}",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        ).pack(anchor="w", pady=(0, 15))
        
        # Class list treeview
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True)
        
        columns = ("jxb_mc", "jsxx", "sksj", "yxzrs", "sxbj")
        class_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            bootstyle="info"
        )
        
        class_tree.heading("jxb_mc", text="🏫 教学班")
        class_tree.heading("jsxx", text="👨‍🏫 教师")
        class_tree.heading("sksj", text="⏰ 上课时间")
        class_tree.heading("yxzrs", text="📊 余量/总量")
        class_tree.heading("sxbj", text="📌 状态")
        
        class_tree.column("jxb_mc", width=120)
        class_tree.column("jsxx", width=100)
        class_tree.column("sksj", width=220)
        class_tree.column("yxzrs", width=80, anchor="center")
        class_tree.column("sxbj", width=60, anchor="center")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=class_tree.yview)
        class_tree.configure(yscrollcommand=scrollbar.set)
        
        class_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate tree
        for idx, c in enumerate(self.classes):
            remaining = c.get("yxzrs", "")
            total = c.get("jxbrl", "")
            capacity_display = f"{remaining}/{total}" if remaining and total else remaining or total or ""
            status = "✓ 已选" if c.get("sxbj") == "1" else ""
            
            class_tree.insert("", "end", iid=str(idx), values=(
                c.get("jxb_mc", ""),
                c.get("jsxx", ""),
                c.get("sksj", ""),
                capacity_display,
                status
            ))
        
        # Select first item by default
        if self.classes:
            class_tree.selection_set("0")
        
        # Button frame
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(15, 0))
        
        def on_confirm():
            selection = class_tree.selection()
            if selection:
                idx = int(selection[0])
                selected_class["result"] = self.classes[idx]
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        def on_double_click(event):
            on_confirm()
        
        class_tree.bind("<Double-1>", on_double_click)
        
        ttk.Button(
            btn_frame,
            text="取消",
            command=on_cancel,
            bootstyle="secondary"
        ).pack(side="right", padx=(8, 0))
        
        ttk.Button(
            btn_frame,
            text=f"确认{action_text}",
            command=on_confirm,
            bootstyle="primary"
        ).pack(side="right")
        
        # Wait for dialog to close
        dialog.wait_window()
        
        return selected_class["result"]

    # ========== TASK MANAGEMENT METHODS ==========
    
    def _refresh_task_list(self):
        """Refresh the task list in the UI, preserving selection."""
        # Save current selection before refresh
        current_selection = self.task_tree.selection()
        selected_task_id = current_selection[0] if current_selection else None
        
        self.task_tree.delete(*self.task_tree.get_children())
        tasks = self.task_manager.get_all_tasks()
        
        status_icons = {
            TaskStatus.STOPPED: "⏸",
            TaskStatus.RUNNING: "▶",
            TaskStatus.SUCCESS: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.CONFLICT: "⚠️"
        }
        
        for task in tasks:
            account = self.account_manager.get_account(task.account_id)
            account_name = account.name if account else "未知"
            status_icon = status_icons.get(task.status, "?")
            
            self.task_tree.insert("", "end", iid=task.id, values=(
                status_icon,
                task.course_info.kcmc,
                f"{task.interval}s",
                task.attempt_count,
                task.last_message[:40] if task.last_message else ""
            ))
        
        self.task_count_label.configure(text=f"共 {len(tasks)} 个任务")
        
        # Restore selection if the task still exists
        if selected_task_id and self.task_tree.exists(selected_task_id):
            self.task_tree.selection_set(selected_task_id)
            self.task_tree.focus(selected_task_id)
    
    def _on_edit_task(self):
        """Edit the selected task to modify delay and view details."""
        selection = self.task_tree.selection()
        if not selection:
            self._log("⚠ 警告: 请先选择一个任务。", "warning")
            return
        
        task_id = selection[0]
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        account = self.account_manager.get_account(task.account_id)
        account_name = account.name if account else "未知"
        
        # Create edit dialog
        dialog = ttk.Toplevel(self.root)
        dialog.title(f"✏️ 编辑任务")
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 320) // 2
        dialog.geometry(f"450x400+{x}+{y}")
        
        # Container
        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ttk.Label(
            container,
            text=f"📝 任务详情",
            font=("Segoe UI", 14, "bold"),
            bootstyle="primary"
        )
        header.pack(anchor="w", pady=(0, 15))
        
        # Info frame
        info_frame = ttk.Frame(container)
        info_frame.pack(fill="x", pady=(0, 15))
        
        # Task info display
        info_items = [
            ("账号", account_name),
            ("课程", task.course_info.kcmc),
            ("教学班", task.course_info.jxb_mc),
            ("状态", task.status.value),
            ("尝试次数", str(task.attempt_count)),
            ("最后消息", task.last_message[:50] if task.last_message else "无")
        ]
        
        for label_text, value_text in info_items:
            row = ttk.Frame(info_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label_text}:", font=("Segoe UI", 10, "bold"), width=10, anchor="e").pack(side="left", padx=(0, 8))
            ttk.Label(row, text=value_text, font=("Segoe UI", 10)).pack(side="left", fill="x")
        
        # Separator
        ttk.Separator(container, orient="horizontal").pack(fill="x", pady=10)
        
        # Editable section - Interval
        edit_frame = ttk.Frame(container)
        edit_frame.pack(fill="x", pady=(0, 15))
        
        interval_row = ttk.Frame(edit_frame)
        interval_row.pack(fill="x", pady=5)
        
        ttk.Label(interval_row, text="抢课间隔 (秒):", font=("Segoe UI", 10, "bold"), width=12, anchor="e").pack(side="left", padx=(0, 8))
        
        interval_var = tk.StringVar(value=str(task.interval))
        interval_entry = ttk.Entry(interval_row, textvariable=interval_var, width=10, font=("Segoe UI", 10))
        interval_entry.pack(side="left")
        
        ttk.Label(interval_row, text="(越小越快，建议 0.3~1.0)", bootstyle="secondary").pack(side="left", padx=(10, 0))
        
        # Button frame
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        def on_save():
            try:
                new_interval = float(interval_var.get())
                if new_interval < 0.1:
                    new_interval = 0.1
                elif new_interval > 60:
                    new_interval = 60
                
                self.task_manager.update_task(task_id, interval=new_interval)
                self._refresh_task_list()
                self._log(f"✅ 任务已更新: {task.course_info.kcmc} - 间隔 {new_interval}s", "success")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("输入错误", "请输入有效的数字")
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(
            btn_frame,
            text="取消",
            command=on_cancel,
            bootstyle="secondary"
        ).pack(side="right", padx=(8, 0))
        
        ttk.Button(
            btn_frame,
            text="保存",
            command=on_save,
            bootstyle="primary"
        ).pack(side="right")
    
    def _on_add_task(self):
        """Add a new task for the selected course."""
        if not self.current_account:
            self._log("⚠ 警告: 请先选择一个账号。", "warning")
            return
        
        selection = self.course_tree.selection()
        if not selection or not self.classes:
            self._log("⚠ 警告: 请先选择一门课程并加载教学班。", "warning")
            return

        item = self.course_tree.item(selection[0])
        kch_id = item['values'][0]
        kcmc = item['values'][1]
        
        # Let user select which class to grab
        selected_class = self._select_class_dialog(f"选择教学班 - {kcmc}", "添加任务")
        if not selected_class:
            self._log("↩ 取消添加任务。")
            return
        
        jxb_ids = selected_class.get("jxb_ids", "")
        jxb_mc = selected_class.get("jxb_mc", "")

        if not jxb_ids:
            self._log("❌ 错误: 无法获取教学班ID。", "error")
            return

        try:
            interval = float(self.interval_entry.get())
        except ValueError:
            interval = 0.5

        # Get gnmkdm from current API session
        gnmkdm = "N253512"
        if hasattr(self.api, 'student_info') and self.api.student_info:
            # Try to get from student info if available
            pass  # Default is fine

        course_info = CourseInfo(
            kch_id=kch_id,
            kcmc=kcmc,
            jxb_ids=jxb_ids,
            jxb_mc=jxb_mc,
            gnmkdm=gnmkdm
        )
        
        task = self.task_manager.create_task(
            account_id=self.current_account.id,
            course_info=course_info,
            interval=interval
        )
        
        if task:
            self._refresh_task_list()
            self._log(f"✅ 已添加任务: [{self.current_account.name}] {kcmc} - {jxb_mc}", "success")
        else:
            self._log("❌ 添加任务失败", "error")
    
    def _on_start_task(self):
        """Start the selected task."""
        selection = self.task_tree.selection()
        if not selection:
            self._log("⚠ 警告: 请先选择一个任务。", "warning")
            return
        
        task_id = selection[0]
        self.task_manager.start_task(task_id)
        self._refresh_task_list()
    
    def _on_stop_task(self):
        """Stop the selected task."""
        selection = self.task_tree.selection()
        if not selection:
            self._log("⚠ 警告: 请先选择一个任务。", "warning")
            return
        
        task_id = selection[0]
        self.task_manager.stop_task(task_id)
        self._refresh_task_list()
    
    def _on_delete_task(self):
        """Delete the selected task."""
        selection = self.task_tree.selection()
        if not selection:
            self._log("⚠ 警告: 请先选择一个任务。", "warning")
            return
        
        task_id = selection[0]
        task = self.task_manager.get_task(task_id)
        if not task:
            return
        
        confirm = messagebox.askyesno(
            "确认删除",
            f"确定要删除任务 '{task.course_info.kcmc}' 吗？"
        )
        if confirm:
            self.task_manager.remove_task(task_id)
            self._refresh_task_list()
            self._log(f"🗑 已删除任务: {task.course_info.kcmc}")
    
    def _on_start_all_tasks(self):
        """Start all stopped tasks."""
        self.task_manager.start_all_tasks()
        self._refresh_task_list()
        self._log("▶▶ 已启动所有任务")
    
    def _on_stop_all_tasks(self):
        """Stop all running tasks."""
        self.task_manager.stop_all_tasks()
        self._refresh_task_list()
        self._log("⏹ 已停止所有任务")
    
    # Task Manager Callbacks
    def _on_task_update(self, task: GrabTask):
        """Called when a task's status changes."""
        self.root.after(0, self._refresh_task_list)
    
    def _on_task_success(self, task: GrabTask, msg: str):
        """Called when a task succeeds."""
        account = self.account_manager.get_account(task.account_id)
        account_name = account.name if account else "未知"
        
        def show_success():
            self._refresh_task_list()
            messagebox.showinfo(
                "🎉 抢课成功",
                f"账号: {account_name}\n"
                f"课程: {task.course_info.kcmc}\n"
                f"教学班: {task.course_info.jxb_mc}\n\n"
                f"{msg}"
            )
        
        self.root.after(0, show_success)
    
    def _on_task_error(self, task: GrabTask, msg: str):
        """Called when a task encounters a fatal error."""
        account = self.account_manager.get_account(task.account_id)
        account_name = account.name if account else "未知"
        
        def show_error():
            self._refresh_task_list()
            messagebox.showwarning(
                "🛑 任务停止",
                f"账号: {account_name}\n"
                f"课程: {task.course_info.kcmc}\n\n"
                f"原因: {msg}"
            )
        
        self.root.after(0, show_error)
    
    def _on_task_log(self, task_id: str, message: str, level: str):
        """Called when a task logs a message."""
        self.root.after(0, lambda: self._log(message, level))

    def _on_drop(self):
        """Handle course withdrawal (退选)."""
        selection = self.course_tree.selection()
        if not selection or not self.classes:
            self._log("⚠ 警告: 请先选择一门课程并加载教学班。", "warning")
            return

        item = self.course_tree.item(selection[0])
        kch_id = item['values'][0]
        kcmc = item['values'][1]
        
        # Let user select which class to drop
        selected_class = self._select_class_dialog(f"选择教学班 - {kcmc}", "退选")
        if not selected_class:
            self._log("↩ 取消退选操作。")
            return
        
        jxb_ids = selected_class.get("jxb_ids", "")
        jxb_mc = selected_class.get("jxb_mc", "")

        if not jxb_ids:
            self._log("❌ 错误: 无法获取教学班ID。", "error")
            return

        confirm = messagebox.askyesno(
            "⚠️ 确认退选",
            f"确定要退选以下课程吗？\n\n课程名称: {kcmc}\n课程代码: {kch_id}\n\n此操作不可撤销！"
        )
        
        if not confirm:
            self._log("↩ 取消退选操作。")
            return

        self.drop_btn.configure(state="disabled")
        self._log(f"🔄 正在退选: {kcmc}...")

        def do_drop():
            try:
                result = self.api.drop_course(jxb_ids, kch_id)
                flag = result.get("flag", "-1")
                msg = result.get("msg", "未知结果")
                
                if flag == "1":
                    self.root.after(0, lambda: self._on_drop_success(kcmc, msg))
                else:
                    self.root.after(0, lambda m=msg: self._on_drop_fail(kcmc, m))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda err=error_msg: self._on_drop_fail(kcmc, err))

        threading.Thread(target=do_drop, daemon=True).start()

    def _on_drop_success(self, kcmc: str, msg: str):
        """Handle successful course withdrawal."""
        self.drop_btn.configure(state="normal")
        self._log(f"✅ 退选成功: {kcmc} - {msg}", "success")
        messagebox.showinfo("退选成功", f"✅ 已成功退选课程：\n\n{kcmc}")

    def _on_drop_fail(self, kcmc: str, msg: str):
        """Handle failed course withdrawal."""
        self.drop_btn.configure(state="normal")
        self._log(f"❌ 退选失败: {kcmc} - {msg}", "error")
        messagebox.showerror("退选失败", f"❌ 退选课程失败：\n\n{kcmc}\n\n原因: {msg}")


def main():
    # Initialize implementation with 'darkly' theme
    root = ttk.Window(themename="darkly")
    
    # Set window icon (if available)
    try:
        root.iconbitmap("icon.ico")
    except:
        pass
    
    app = CourseSelectionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
