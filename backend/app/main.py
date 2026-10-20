from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, BODY_METRICS_FILE, PROFILE_FILE, RECORDS_FILE, SETTINGS, SHORT_MEMORY_DIR, STORAGE_DIR, UPLOAD_DIR
from app.schemas import AgentChatRequest, BodyMetricRecord, ChatRequest, FoodLogRequest, HealthProfile
from app.services.agent import agent
from app.services.body_metrics import add_body_metric, list_body_metrics, trend_summary
from app.services.food import add_records, daily_summary, estimate_item, list_records, load_foods
from app.services.health import calculate_profile
from app.services.memory import get_recent_context, list_sessions, new_session_id
from app.services.rag import rag_service
from app.services.storage import read_json, write_json
from app.services.vision import recognize_food_image


app = FastAPI(title="NutriFit AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.get("server", {}).get("cors_origins", ["*"]) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")


@app.get("/api/dashboard/summary")
def dashboard_summary():
    profile = read_json(PROFILE_FILE, None)
    health = calculate_profile(HealthProfile(**profile)) if profile else calculate_profile(HealthProfile())
    records = daily_summary()
    return {
        "knowledge_files": 6,
        "food_items": len(load_foods()),
        "knowledge_chunks": len(rag_service.docs),
        "health": health,
        "today": records,
        "memory": trend_summary("default_user"),
    }


@app.post("/api/profile/calculate")
def profile_calculate(profile: HealthProfile):
    write_json(PROFILE_FILE, profile.model_dump())
    return calculate_profile(profile)


@app.get("/api/food/search")
def food_search(q: str = ""):
    foods = load_foods()
    if q:
        foods = [x for x in foods if q in x["food_name"] or q.lower() in x["food_name"].lower()]
    return foods[:30]


@app.post("/api/food/log")
def food_log(req: FoodLogRequest):
    records = [estimate_item(item, source="manual") for item in req.items]
    for record in records:
        record.note = req.note
    all_records = add_records(records)
    return {"records": [x.model_dump() for x in records], "summary": daily_summary(), "total_records": len(all_records)}


@app.get("/api/food/records")
def food_records():
    return {"records": list_records(), "summary": daily_summary()}


@app.post("/api/food/recognize")
async def food_recognize(file: UploadFile = File(...), meal_type: str = Form("拍照记录")):
    return await recognize_food_image(file, meal_type)


@app.post("/api/rag/retrieve")
def rag_retrieve(req: ChatRequest):
    return {"sources": rag_service.retrieve(req.question, req.top_k)}


@app.post("/api/rag/chat")
def rag_chat(req: ChatRequest):
    return rag_service.answer(req.question, req.top_k)


@app.post("/api/agent/chat")
def agent_chat(req: AgentChatRequest):
    return agent.chat(req)


@app.post("/api/chat/session")
def create_chat_session():
    session_id = new_session_id()
    return {"session_id": session_id, "history": get_recent_context(session_id)}


@app.get("/api/chat/sessions")
def chat_sessions():
    return {"sessions": list_sessions()}


@app.get("/api/chat/history/{session_id}")
def chat_history(session_id: str):
    return get_recent_context(session_id)


@app.post("/api/memory/body-metrics")
def save_body_metric(record: BodyMetricRecord):
    saved = add_body_metric(record)
    return {"record": saved, "trend": trend_summary(record.user_id)}


@app.get("/api/memory/body-metrics")
def get_body_metrics(user_id: str = "default_user"):
    return {"records": list_body_metrics(user_id), "trend": trend_summary(user_id)}


@app.get("/api/config/public")
def public_config():
    llm = SETTINGS.get("llm", {})
    return {
        "base_url": llm.get("base_url"),
        "chat_model": llm.get("chat_model"),
        "vision_model": llm.get("vision_model"),
        "has_api_key": bool(llm.get("api_key")),
        "features": SETTINGS.get("features", {}),
    }


def _clear_uploads():
    removed = 0
    for path in UPLOAD_DIR.glob("*"):
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _clear_short_memory():
    removed = 0
    for path in SHORT_MEMORY_DIR.glob("*.json"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed


@app.post("/api/admin/clear-food-records")
def clear_food_records():
    removed_uploads = _clear_uploads()
    write_json(RECORDS_FILE, [])
    return {
        "message": "热量记录已清空",
        "cleared": {
            "meal_records": True,
            "uploaded_images": removed_uploads,
        },
        "summary": daily_summary(),
    }


@app.post("/api/admin/clear-all-data")
def clear_all_data():
    removed_uploads = _clear_uploads()
    removed_sessions = _clear_short_memory()
    write_json(RECORDS_FILE, [])
    write_json(BODY_METRICS_FILE, [])
    if PROFILE_FILE.exists():
        PROFILE_FILE.unlink()
    return {
        "message": "所有运行态数据已清空",
        "cleared": {
            "meal_records": True,
            "body_metrics": True,
            "user_profile": True,
            "chat_sessions": removed_sessions,
            "uploaded_images": removed_uploads,
        },
        "summary": dashboard_summary(),
    }


@app.get("/api/knowledge/stats")
def knowledge_stats():
    domains = {}
    for doc in rag_service.docs:
        domains[doc["domain"]] = domains.get(doc["domain"], 0) + 1
    return {"chunks": len(rag_service.docs), "domains": domains}


# 若存在前端构建产物（frontend/dist），由后端直接托管，实现单端口部署。
# 这样上公网时只需运行一个 uvicorn 进程，不用另外装 Nginx。
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
FRONTEND_READY = (FRONTEND_DIST / "index.html").exists()

if FRONTEND_READY:
    _assets = FRONTEND_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        # 未定义的 API 路径应交由 FastAPI 返回 404，而不是回退到前端页面
        if full_path.startswith(("api/", "storage/")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        target = (FRONTEND_DIST / full_path).resolve()
        root = FRONTEND_DIST.resolve()
        if target.is_file() and root in target.parents:
            return FileResponse(target)
        # 其余路径交给前端路由（SPA 单页应用）
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def root():
        return {"name": "NutriFit AI", "docs": "/docs", "hint": "前端未构建，开发模式请访问 Vite 的 5175 端口"}
