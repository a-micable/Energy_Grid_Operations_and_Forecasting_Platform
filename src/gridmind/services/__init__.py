from gridmind.services.audit import AuditService

__all__ = ["AuditService"]


def __getattr__(name: str):
    if name == "OperationalCoordinator":
        from gridmind.services.coordinator import OperationalCoordinator
        return OperationalCoordinator
    if name == "WorkflowOrchestrator":
        from gridmind.services.workflow import WorkflowOrchestrator
        return WorkflowOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
