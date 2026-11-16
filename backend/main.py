from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from graph.graph import graph
from langchain_core.messages import HumanMessage
from fastapi.middleware.cors import CORSMiddleware
from data_sources.fund_comparison import compare_funds, search_schemes
from data_sources.mutual_fund_nav import MarketDataError


app = FastAPI(
    title="Mutual Fund Analyzer API",
    description="Live AMFI-backed NAV analytics and AI-assisted multi-fund comparison.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mutual-fund-analyzer-rho.vercel.app",
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
    fund_names: Optional[List[str]] = None
    period: Optional[int] = 1


class CompareRequest(BaseModel):
    fund_names: List[str] = Field(min_length=2, max_length=10)
    period: int = Field(default=1, description="Supported values: 1, 3, 5, 10")


@app.post("/chat")
async def chat(req: ChatRequest):
    initial_state = {
        "messages": [HumanMessage(content=req.message)],
        "fund_names": req.fund_names or [],
        "period": req.period or 1,
    }
    result = graph.invoke(initial_state)
    return {"response": result.get("tool_result")}


@app.get("/funds/search")
def fund_search(
    q: str = Query(min_length=2, description="Search AMFI scheme names"),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Search the current AMFI scheme master; results are live, not hard-coded."""
    try:
        return {"query": q, "results": search_schemes(q, limit)}
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AMFI scheme search is temporarily unavailable ({type(exc).__name__}).",
        ) from exc


@app.post("/compare")
def compare(request: CompareRequest):
    """Generate a ranked, AI-explained report for 2–10 selected schemes."""
    try:
        return compare_funds(request.fund_names, request.period)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok"}
