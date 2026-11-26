"""Agent runner and Phase 1 agents (Day 3: Product Strategist, Android Architect; Day 4: UI, Data, Build Doctor, failure memory)."""
from .architect import ANDROID_ARCHITECT
from .code_agents import DATA_ENGINEER, UI_ENGINEER, run_code_agent
from .doctor import BUILD_DOCTOR, BuildDoctor, DoctorReport
from .memory import FailureMemory, FixEntry, signature
from .client import AnthropicClient, ModelClient, ModelError, RecordedClient
from .runner import AgentDef, AgentOutputError, AgentRunner, extract_json
from .strategist import PRODUCT_STRATEGIST

ALL_AGENTS = {"product-strategist": PRODUCT_STRATEGIST, "android-architect": ANDROID_ARCHITECT,
              "ui-engineer": UI_ENGINEER, "data-engineer": DATA_ENGINEER, "build-doctor": BUILD_DOCTOR}

__all__ = [n for n in dir() if not n.startswith("_")]
