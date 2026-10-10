from langgraph.graph import StateGraph, START, END
from graph.state import AgentState
from graph.nodes.fund_info import fund_info_node
from graph.nodes.synthesizer import synthesizer_node

def build_graph():
    g = StateGraph(AgentState)

    # Add only the two nodes required for the assignment
    g.add_node("fund_info", fund_info_node)
    g.add_node("synthesizer", synthesizer_node)

    # Build a strict, linear pipeline
    g.add_edge(START, "fund_info")
    g.add_edge("fund_info", "synthesizer")
    g.add_edge("synthesizer", END)

    return g.compile()

graph = build_graph()