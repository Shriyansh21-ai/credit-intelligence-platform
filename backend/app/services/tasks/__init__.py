"""Task Management.

Application-scoped tasks with owner / priority / due date / status / comments.
Assignment, completion and due/overdue scans emit notifications via the M10
notification engine, and mutations are audited.
"""

from backend.app.services.tasks.service import (
    TASK_TYPES,
    add_comment,
    create_task,
    list_comments,
    list_tasks,
    scan_due_tasks,
    serialize_task,
    update_task,
)

__all__ = [
    "TASK_TYPES",
    "create_task",
    "update_task",
    "add_comment",
    "list_comments",
    "list_tasks",
    "scan_due_tasks",
    "serialize_task",
]
