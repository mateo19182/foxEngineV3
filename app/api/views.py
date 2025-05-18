from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..auth.jwt import get_current_user, create_access_token
from ..auth.utils import get_user, verify_password
from ..utils.logging import log_api_call

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

@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    """Process login form submission."""
    try:
        form_data = await request.form()
        username = form_data.get("username")
        password = form_data.get("password")
        
        user = await get_user(username)
        if not user or not verify_password(password, user['password']):
            await log_api_call("/login", "POST", username, 401)
            with open("templates/login.html", "r", encoding="utf-8") as f:
                page = f.read()
            page = page.replace(
                '<div id="error-message" class="status-message error d-none"></div>',
                '<div id="error-message" class="status-message error">Invalid username or password</div>'
            )
            return HTMLResponse(content=page, status_code=401)
        
        access_token = create_access_token(data={"sub": username})
        await log_api_call("/login", "POST", username)
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=False,  # Set to True in production
            samesite="lax"
        )
        return response
    except Exception as e:
        await log_api_call("/login", "POST", username if 'username' in locals() else 'unknown', 500, str(e))
        raise

@router.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    """Files management page."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/files.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.get("/tools", response_class=HTMLResponse)
async def tools_page(request: Request):
    """Tools page with various utilities."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/tools.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@router.get("/tools/header-extractor", response_class=HTMLResponse)
async def header_extractor_page(request: Request):
    """CSV Header Extractor tool page."""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    with open("templates/header-extractor.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())