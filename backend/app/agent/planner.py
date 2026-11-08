import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.core.events import event_bus, AgentEvent

class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: str = ""
    status: str = "pending"  # pending, in_progress, waiting_approval, completed, failed, skipped
    result_summary: Optional[str] = None

class TaskPlan(BaseModel):
    conversation_id: str
    task_goal: str
    steps: List[PlanStep] = Field(default_factory=list)

class TaskPlanner:
    _plans: Dict[str, TaskPlan] = {}

    @classmethod
    def get_plan(cls, conversation_id: str) -> Optional[TaskPlan]:
        return cls._plans.get(conversation_id)

    @classmethod
    async def set_plan(cls, conversation_id: str, task_goal: str, step_titles: List[str]) -> TaskPlan:
        steps = [PlanStep(title=t) for t in step_titles]
        plan = TaskPlan(conversation_id=conversation_id, task_goal=task_goal, steps=steps)
        cls._plans[conversation_id] = plan
        await cls._broadcast_plan(plan)
        return plan

    @classmethod
    async def update_step_status(
        cls,
        conversation_id: str,
        step_id: str,
        status: str,
        result_summary: Optional[str] = None
    ) -> Optional[TaskPlan]:
        plan = cls._plans.get(conversation_id)
        if not plan:
            return None

        for s in plan.steps:
            if s.id == step_id:
                s.status = status
                if result_summary:
                    s.result_summary = result_summary
                break

        await cls._broadcast_plan(plan)
        return plan

    @classmethod
    async def _broadcast_plan(cls, plan: TaskPlan):
        evt = AgentEvent(
            event_type="plan_update",
            conversation_id=plan.conversation_id,
            data={"plan": plan.model_dump()}
        )
        await event_bus.publish(evt)
