from typing import List, Dict, Optional

class Task:
    def __init__(self, task_id: int, name: str, duration: float, estimated_cost: float):
        self.id = task_id
        self.name = name
        self.duration = duration
        self.estimated_cost = estimated_cost
        self.status = "to-do"
        self.progress = 0.0
        self.real_duration = 0.0
        self.dependencies: List[Task] = []
        self.assigned_resource: Optional['Resource'] = None

    def update_progress(self, increment: float):
        self.progress = min(1.0, self.progress + increment)
        if self.progress >= 1.0:
            self.status = "done"

class Resource:
    def __init__(self, resource_id: int, name: str, cost_per_hour: float):
        self.id = resource_id
        self.name = name
        self.cost_per_hour = cost_per_hour
        self.assigned_tasks: List[Task] = []