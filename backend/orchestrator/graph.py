import logging

from langgraph.graph import END, START, StateGraph

from backend.orchestrator.nodes import (
    aggregate_results,
    build_context,
    fan_out_agents,
    post_review,
)
from backend.orchestrator.state import PRReviewState

logger = logging.getLogger(__name__)

def build_review_graph():
    """
    Constructs and compiles the PR review StateGraph.

    RETURNS a compiled LangGraph graph — a callable object.
    To run a review: await graph.ainvoke(initial_state, config={"configurable": {"thread_id": workflow_id}})

    WHY IS THIS A FUNCTION AND NOT MODULE-LEVEL CODE?
    If we built the graph at module import time, we could not inject the checkpointer
    at runtime (the checkpointer needs a live Redis connection).
    Calling build_review_graph() at startup (after Redis connects) is the clean pattern.

    CHECKPOINTER:
    For now: no checkpointer (MemorySaver is used as a placeholder).
    Phase 4 gate will replace this with RedisSaver once Redis is connected.
    The graph shape and node wiring is identical — only the checkpointer changes.
    """
    # Step 1: Create a StateGraph that uses PRReviewState as its state schema.
    # LangGraph reads the TypedDict annotations to know what fields exist.
    workflow = StateGraph(PRReviewState)

    # Step 2: Register each node function with a name.
    # The name is used in edges, checkpoints, and log messages.
    workflow.add_node("build_context", build_context)
    workflow.add_node("fan_out_agents", fan_out_agents)
    workflow.add_node("aggregate_results", aggregate_results)
    workflow.add_node("post_review", post_review)

    # Step 3: Wire the edges (execution order).
    # START -> build_context: the graph always starts here
    workflow.add_edge(START, "build_context")

    # build_context -> fan_out_agents: always runs after context is ready
    workflow.add_edge("build_context", "fan_out_agents")

    # fan_out_agents -> aggregate_results: always runs after all agents finish
    workflow.add_edge("fan_out_agents", "aggregate_results")

    # aggregate_results -> post_review: always runs (post_review handles HITL internally)
    # NOTE: We could add a conditional edge here to route to a HITL node instead.
    # For Phase 4, post_review handles both paths internally.
    # Phase 19 will split this into: post_review (auto) vs hitl_queue (human).
    workflow.add_edge("aggregate_results", "post_review")

    # post_review -> END: the graph is done
    workflow.add_edge("post_review", END)

    # Step 4: Set the entry point explicitly.
    # LangGraph needs to know where to start. START -> build_context already
    # does this, but set_entry_point makes it explicit and self-documenting.
    workflow.set_entry_point("build_context")

    # Step 5: Compile the graph.
    # compile() validates the graph (checks for unreachable nodes, missing edges)
    # and returns a CompiledGraph object that can be invoked.
    #
    # CHECKPOINTER NOTE:
    # In production (after Phase 4 Redis setup): pass checkpointer=redis_saver
    # For now: no checkpointer. State lives only in memory during this run.
    # This means resume() is not yet functional — we add that in the Redis section.
    compiled = workflow.compile()

    logger.info("PR review graph compiled successfully. Nodes: %s", list(workflow.nodes))

    return compiled


# Module-level compiled graph instance.
# Built once when this module is first imported.
# The LangGraph engine imports this directly.
#
# WHY MODULE-LEVEL?
# The compiled graph is stateless — it does not hold any per-review data.
# Per-review state lives in the checkpointer (keyed by workflow_id/thread_id).
# So we can safely share one compiled graph across all concurrent reviews.
#
# CONCURRENCY:
# LangGraph compiled graphs are safe to use concurrently.
# Each .ainvoke() call gets its own state isolated by thread_id (= workflow_id).
review_graph = build_review_graph()