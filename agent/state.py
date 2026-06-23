from typing import List, TypedDict


class AgentState(TypedDict):
    query: str
    sub_questions: List[str]
    web_results: List[dict]      # each: {url, title, content}
    conflicts: List[str]
    report: str
    reasoning_trace: List[str]
    iteration_count: int
    status: str
    max_sources: int
