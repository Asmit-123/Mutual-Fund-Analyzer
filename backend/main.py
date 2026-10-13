from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from graph.graph import graph
from langchain_core.messages import HumanMessage
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mutual-fund-analyzer-1.onrender.com"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    fund_names: Optional[List[str]] = []  # Added to explicitly receive chosen funds
    period: Optional[int] = 1             # Added to receive the 1, 3, 5, or 10 year period


@app.post("/chat")
async def chat(req: ChatRequest):
    # Pass the period and fund_names into the LangGraph initial state
    initial_state = {
        "messages": [HumanMessage(content=req.message)],
        "fund_names": req.fund_names,
        "period": req.period
    }
    
    result = graph.invoke(initial_state)
    return {"response": result.get("tool_result")}


@app.get("/health")
def health():
    return {"status": "ok"}