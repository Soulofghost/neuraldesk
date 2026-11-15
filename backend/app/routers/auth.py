import uuid
import json
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.database import get_db_connection
from app.auth import hash_password, verify_password, create_access_token, get_current_user, require_admin
from app.schemas import UserRegister, UserLogin, UserResponse, TokenResponse, UserProfileUpdate

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: UserRegister):
    email = payload.email.strip().lower()
    full_name = payload.full_name.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(payload.password)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        # First user is admin, others standard
        cursor.execute("SELECT count(*) as cnt FROM users")
        user_count = cursor.fetchone()["cnt"]
        role = "admin" if user_count == 0 else "user"

        cursor.execute("""
            INSERT INTO users (id, email, password_hash, full_name, role, plan)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, email, pw_hash, full_name, role, "pro"))
        conn.commit()

        cursor.execute("SELECT id, email, full_name, role, plan, avatar_url, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        user_res = UserResponse(
            id=str(row["id"]),
            email=str(row["email"]),
            full_name=str(row["full_name"]),
            role=str(row["role"]),
            plan=str(row["plan"]),
            avatar_url=str(row["avatar_url"]) if row["avatar_url"] else "",
            created_at=str(row["created_at"])
        )

        token = create_access_token(user_id=user_id, email=email, role=role, plan="pro")
        return TokenResponse(access_token=token, user=user_res)

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin):
    email = payload.email.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password_hash, full_name, role, plan, avatar_url, created_at FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        user_res = UserResponse(
            id=str(row["id"]),
            email=str(row["email"]),
            full_name=str(row["full_name"]),
            role=str(row["role"]),
            plan=str(row["plan"]),
            avatar_url=str(row["avatar_url"]) if row["avatar_url"] else "",
            created_at=str(row["created_at"])
        )
        token = create_access_token(user_id=row["id"], email=row["email"], role=row["role"], plan=row["plan"])
        return TokenResponse(access_token=token, user=user_res)

@router.get("/me", response_model=UserResponse)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, role, plan, avatar_url, created_at FROM users WHERE id = ?", (current_user["id"],))
        row = cursor.fetchone()
        if not row:
            # Fallback mock for demo mode
            return UserResponse(
                id=current_user["id"],
                email=current_user["email"],
                full_name=current_user["full_name"],
                role=current_user["role"],
                plan=current_user["plan"],
                avatar_url="",
                created_at="2026-11-15 00:00:00"
            )
        return UserResponse(
            id=str(row["id"]),
            email=str(row["email"]),
            full_name=str(row["full_name"]),
            role=str(row["role"]),
            plan=str(row["plan"]),
            avatar_url=str(row["avatar_url"]) if row["avatar_url"] else "",
            created_at=str(row["created_at"])
        )

@router.put("/profile", response_model=UserResponse)
def update_profile(payload: UserProfileUpdate, current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (current_user["id"],))
        existing = cursor.fetchone()
        if not existing:
            # Create user on the fly if operating in demo context
            pw_hash = hash_password("demo1234")
            cursor.execute("""
                INSERT INTO users (id, email, password_hash, full_name, role, plan)
                VALUES (?, ?, ?, ?, 'admin', 'enterprise')
            """, (current_user["id"], current_user["email"], pw_hash, current_user["full_name"]))
            conn.commit()

        full_name = payload.full_name.strip() if payload.full_name is not None else existing["full_name"]
        avatar = payload.avatar_url if payload.avatar_url is not None else existing["avatar_url"]
        prefs = json.dumps(payload.preferences) if payload.preferences is not None else existing["preferences"]

        cursor.execute("""
            UPDATE users SET full_name = ?, avatar_url = ?, preferences = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (full_name, avatar, prefs, current_user["id"]))
        conn.commit()

        cursor.execute("SELECT id, email, full_name, role, plan, avatar_url, created_at FROM users WHERE id = ?", (current_user["id"],))
        row = cursor.fetchone()
        return UserResponse(
            id=str(row["id"]),
            email=str(row["email"]),
            full_name=str(row["full_name"]),
            role=str(row["role"]),
            plan=str(row["plan"]),
            avatar_url=str(row["avatar_url"]) if row["avatar_url"] else "",
            created_at=str(row["created_at"])
        )

@router.get("/users", response_model=List[UserResponse])
def list_users(admin: Dict[str, Any] = Depends(require_admin)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, role, plan, avatar_url, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [
            UserResponse(
                id=str(r["id"]),
                email=str(r["email"]),
                full_name=str(r["full_name"]),
                role=str(r["role"]),
                plan=str(r["plan"]),
                avatar_url=str(r["avatar_url"]) if r["avatar_url"] else "",
                created_at=str(r["created_at"])
            )
            for r in rows
        ]
