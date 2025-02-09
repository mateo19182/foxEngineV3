from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..auth.jwt import get_current_user

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with dashboard."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Search page with advanced search and record management."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/search.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """CSV upload page."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/upload.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    """Login page."""
    with open("templates/login.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    """Files management page."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/files.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read()) 