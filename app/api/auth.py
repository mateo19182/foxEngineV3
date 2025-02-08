from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, HTMLResponse
from ..auth.utils import verify_password, get_user, get_password_hash
from ..auth.jwt import create_access_token
from ..database.client import users_collection
from typing import Optional
from ..utils.logging import log_api_call

router = APIRouter()

@router.post("/register", summary="Register new user",
    description="Register a new user with username and password")
async def register_user(username: str, password: str):
    try:
        if users_collection.find_one({"username": username}):
            log_api_call("/register", "POST", username, 400)
            raise HTTPException(status_code=400, detail="Username already exists")
        
        users_collection.insert_one({
            "username": username,
            "password": get_password_hash(password)
        })
        log_api_call("/register", "POST", username)
        return {"message": "User created successfully"}
    except Exception as e:
        log_api_call("/register", "POST", username, 500, str(e))
        raise

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", summary="User login",
    description="Login with username and password to get access token")
async def login(request: Request):
    try:
        form_data = await request.form()
        username = form_data.get("username")
        password = form_data.get("password")
        
        user = get_user(username)
        if not user or not verify_password(password, user['password']):
            log_api_call("/login", "POST", username, 401)
            # Read the login template and inject an error message
            with open("templates/login.html", "r", encoding="utf-8") as f:
                page = f.read()
            # Replace the placeholder with an error message
            page = page.replace(
                '<div id="error-message" style="color: red;"></div>',
                '<div id="error-message" style="color: red;">Invalid credentials</div>'
            )
            return HTMLResponse(content=page, status_code=401)
        
        access_token = create_access_token(data={"sub": username})
        log_api_call("/login", "POST", username)
        
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=False,  # Set to True in production
            samesite="lax"
        )
        return response
    except Exception as e:
        log_api_call("/login", "POST", username, 500, str(e))
        raise

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response
