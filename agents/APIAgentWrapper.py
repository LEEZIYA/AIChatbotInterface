"""
TravelBuddy — AI Travel Intelligence
FastAPI Multi-Agent Backend
"""

from fastapi import FastAPI
from fastapi import HTTPException
import uvicorn
from contextlib import asynccontextmanager
import logging

from pydantic import BaseModel, Field

from TransportAgent import planTravel


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("APIAgent")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # logger.info(f"subAgent starting — env={settings.ENV}")
    logger.info(f"subAgent starting ")
    yield
    logger.info("subAgent shutting down")

# Defining Data Models
class ChatRequest(BaseModel):
    question: str
    context: Dict[str, Any] = {}
class ChatResponse(BaseModel):
    user: str
    answer: str

app = FastAPI(
    title="API enabled subAgent",
    version="1.0.0",
    description="sub-agent of AI travel assistant",
    lifespan=lifespan,
)


# Define routes directly in main file
@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        answer = TestAgent(SYSTEM_PROMPT + request.question)
        return ChatResponse(user=request.question, answer=answer)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Agent processing failed")






def TestAgent(prompt)-> str:
    return planTravel(prompt)



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

