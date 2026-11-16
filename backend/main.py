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
        "https://mutual-fund-analyzer-asmitbhattacharyya12-8035.vercel.app",
        "https://mutual-fund-analyzer-git-master-asmitbhattacharyya12-8035.vercel.app",
        "https://mutual-fund-analyzer-tau.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    fund_names: Optional[List[str]] = []
    period: Optional[int] = 1


@app.post("/chat")
async def chat(req: ChatRequest):
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
