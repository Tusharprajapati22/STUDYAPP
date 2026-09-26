# import os
# import re
# import hmac
# import time
# import secrets
# import traceback
# from datetime import datetime, timedelta, timezone
# from pathlib import Path
# from typing import Optional, List

# import bcrypt
# import jwt
# from dotenv import load_dotenv
# from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Depends, Header, Request
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from supabase import create_client

# env_path = Path(__file__).parent / '.env'
# load_dotenv(dotenv_path=env_path)

# app = FastAPI(title="Navjeevan Study App API")

# # CORS setup - allowing all origins during development
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# if not SUPABASE_URL or not SUPABASE_KEY:
#     print("❌ ERROR: .env file me SUPABASE_URL ya SUPABASE_KEY missing hai!")

# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# # ==========================================
# # 🟢 AUTH / RBAC CONFIGURATION
# # ==========================================
# ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
# ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# JWT_SECRET = os.getenv("JWT_SECRET")
# if not JWT_SECRET:
#     print("⚠️  JWT_SECRET missing in .env - using a temporary random one. "
#           "Everyone will be logged out whenever the server restarts. "
#           "Add a long random JWT_SECRET to .env.")
#     JWT_SECRET = secrets.token_urlsafe(48)
# JWT_ALGORITHM = "HS256"
# JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))

# # Can a CR create a brand-new subject inside their own branch+sem?
# # Set CR_CAN_CREATE_SUBJECTS=false in .env to force CRs to pick from
# # subjects the admin has already created.
# CR_CAN_CREATE_SUBJECTS = os.getenv("CR_CAN_CREATE_SUBJECTS", "true").lower() == "true"

# MAX_STAFF_UPLOAD_MB = int(os.getenv("MAX_STAFF_UPLOAD_MB", "50"))

# # Types that are NOT tied to a subject in the registry (admin-only).
# NON_SUBJECT_TYPES = {"Tool", "Skills", "Official Syllabus"}
# # Categories a teacher / CR is allowed to upload (same as the admin upload form).
# STAFF_ALLOWED_TYPES = {"Syllabus", "Notes", "PYQs", "IMP Questions",
#                        "Assignments", "YouTube Links", "Laboratory"}

# SEM_TO_YEAR = {
#     "Common": "1st Year", "Sem 1": "1st Year", "Sem 2": "1st Year",
#     "Sem 3": "2nd Year", "Sem 4": "2nd Year",
#     "Sem 5": "3rd Year", "Sem 6": "3rd Year",
#     "Sem 7": "4th Year", "Sem 8": "4th Year",
# }


# # ==========================================
# # 🟢 SMALL HELPERS
# # ==========================================
# def norm_subject(name: Optional[str]) -> str:
#     """'  math   3 ' -> 'MATH 3'  (collapse spaces, trim, uppercase)."""
#     return re.sub(r"\s+", " ", (name or "").strip()).upper()


# def clean_filename(name: Optional[str]) -> str:
#     return "".join(c for c in (name or "") if c.isalnum() or c in ".-_").strip()


# def is_unique_violation(e: Exception) -> bool:
#     s = str(e).lower()
#     return "23505" in s or "duplicate key" in s or "already exists" in s


# def valid_email(email: str) -> bool:
#     return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


# def check_password_rules(pw: str):
#     if len(pw) < 6:
#         raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
#     if len(pw.encode("utf-8")) > 72:
#         raise HTTPException(status_code=400, detail="Password is too long (max 72 bytes).")


# def hash_password(pw: str) -> str:
#     return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# def verify_password(pw: str, hashed: str) -> bool:
#     try:
#         return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
#     except Exception:
#         return False


# def create_token(role: str, user_id: Optional[int] = None) -> str:
#     payload = {
#         "role": role,
#         "sub": str(user_id) if user_id is not None else "admin",
#         "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
#     }
#     return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# # ---- very small in-memory brute-force guard for the login endpoints ----
# _FAILED_LOGINS: dict = {}


# def _throttle_key(request: Request, role: str) -> str:
#     ip = request.client.host if request.client else "unknown"
#     return f"{role}:{ip}"


# def _check_throttle(key: str, limit: int = 8, window: int = 600):
#     now = time.time()
#     hits = [t for t in _FAILED_LOGINS.get(key, []) if now - t < window]
#     _FAILED_LOGINS[key] = hits
#     if len(hits) >= limit:
#         raise HTTPException(status_code=429, detail="Too many failed attempts. Please wait a few minutes and try again.")


# def _record_failure(key: str):
#     _FAILED_LOGINS.setdefault(key, []).append(time.time())


# # ==========================================
# # 🟢 SUBJECT REGISTRY HELPERS
# # ==========================================
# def find_subject(name_upper: str, branch: str, sem: str) -> Optional[dict]:
#     res = (supabase.table("subjects").select("*")
#            .eq("name", name_upper).eq("branch", branch).eq("sem", sem)
#            .limit(1).execute())
#     return res.data[0] if res.data else None


# def get_or_create_subject(name_upper: str, year: str, branch: str, sem: str) -> dict:
#     """Return the subject for (name, branch, sem); create it only if it doesn't exist yet.
#     The DB has a unique index on (upper(name), branch, sem), so duplicates are impossible
#     even if two uploads race each other."""
#     existing = find_subject(name_upper, branch, sem)
#     if existing:
#         return existing
#     try:
#         res = supabase.table("subjects").insert({
#             "name": name_upper, "year": year, "branch": branch, "sem": sem
#         }).execute()
#         print(f"🆕 Subject created: {name_upper} | {branch} | {sem}")
#         return res.data[0]
#     except Exception as e:
#         if is_unique_violation(e):
#             again = find_subject(name_upper, branch, sem)
#             if again:
#                 return again
#         raise


# def teacher_subject_ids(teacher_id: int) -> set:
#     res = supabase.table("teacher_assignments").select("subject_id").eq("teacher_id", teacher_id).execute()
#     return {r["subject_id"] for r in (res.data or [])}


# def teacher_subjects(teacher_id: int) -> list:
#     ids = list(teacher_subject_ids(teacher_id))
#     if not ids:
#         return []
#     res = (supabase.table("subjects").select("*").in_("id", ids)
#            .order("branch").order("sem").order("name").execute())
#     return res.data or []


# # ==========================================
# # 🟢 AUTH DEPENDENCIES
# # ==========================================
# def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
#     """Decode the Bearer token and load the *current* account from the DB, so a deleted
#     teacher/CR loses access immediately and assignment changes apply instantly."""
#     if not authorization or not authorization.lower().startswith("bearer "):
#         raise HTTPException(status_code=401, detail="Not authenticated.")
#     token = authorization[7:].strip()
#     try:
#         payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
#     except jwt.PyJWTError:
#         raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")

#     role = payload.get("role")

#     if role == "admin":
#         return {"role": "admin", "id": None, "name": "Admin"}

#     try:
#         uid = int(payload.get("sub"))
#     except (TypeError, ValueError):
#         raise HTTPException(status_code=401, detail="Invalid session.")

#     if role == "teacher":
#         res = supabase.table("teachers").select("id,name,email").eq("id", uid).execute()
#         if not res.data:
#             raise HTTPException(status_code=401, detail="This account no longer exists.")
#         t = res.data[0]
#         return {"role": "teacher", "id": t["id"], "name": t["name"], "email": t["email"],
#                 "subject_ids": teacher_subject_ids(t["id"])}

#     if role == "cr":
#         res = supabase.table("class_representatives").select("id,name,email,branch,sem").eq("id", uid).execute()
#         if not res.data:
#             raise HTTPException(status_code=401, detail="This account no longer exists.")
#         c = res.data[0]
#         return {"role": "cr", "id": c["id"], "name": c["name"], "email": c["email"],
#                 "branch": c["branch"], "sem": c["sem"], "year": SEM_TO_YEAR.get(c["sem"], "")}

#     raise HTTPException(status_code=401, detail="Invalid session.")


# def require_admin(user: dict = Depends(get_current_user)) -> dict:
#     if user["role"] != "admin":
#         raise HTTPException(status_code=403, detail="Admin access required.")
#     return user


# # ==========================================
# # 🟢 SCOPE ENFORCEMENT (the heart of the RBAC)
# # ==========================================
# def authorize_target(user: dict, year: str, branch: str, sem: str, subject: str, note_type: str):
#     """Validate that `user` may put material of `note_type` into (branch, sem, subject).
#     Returns the normalised (year, branch, sem, subject). Admin = unrestricted (as before)."""
#     subject = norm_subject(subject)

#     if user["role"] == "admin":
#         if not subject and note_type not in NON_SUBJECT_TYPES:
#             raise HTTPException(status_code=400, detail="Subject name is required.")
#         return year, branch, sem, subject

#     # ---- teacher / CR from here on ----
#     if note_type not in STAFF_ALLOWED_TYPES:
#         raise HTTPException(status_code=403, detail=f"You are not allowed to upload '{note_type}'.")
#     if not subject:
#         raise HTTPException(status_code=400, detail="Subject name is required.")
#     if sem not in SEM_TO_YEAR:
#         raise HTTPException(status_code=400, detail="Invalid semester.")

#     # Never trust the year sent by the browser - derive it from the semester.
#     year = SEM_TO_YEAR[sem]

#     if user["role"] == "cr":
#         if branch != user["branch"] or sem != user["sem"]:
#             raise HTTPException(status_code=403, detail="You can only upload for your own branch and semester.")
#         return year, branch, sem, subject

#     if user["role"] == "teacher":
#         rec = find_subject(subject, branch, sem)
#         if not rec or rec["id"] not in user["subject_ids"]:
#             raise HTTPException(status_code=403, detail="You are not assigned to this subject / branch / semester.")
#         return year, branch, sem, subject

#     raise HTTPException(status_code=403, detail="Forbidden.")


# def ensure_subject(user: dict, subject: str, year: str, branch: str, sem: str, note_type: str):
#     """Make sure the subject exists in the registry (get-or-create), respecting who may create."""
#     if note_type in NON_SUBJECT_TYPES:
#         return None
#     if user["role"] == "teacher":
#         return None  # already verified as an assigned, existing subject
#     if user["role"] == "cr" and not CR_CAN_CREATE_SUBJECTS:
#         rec = find_subject(subject, branch, sem)
#         if not rec:
#             raise HTTPException(status_code=403, detail="This subject doesn't exist yet. Ask the admin to create it first.")
#         return rec
#     return get_or_create_subject(subject, year, branch, sem)


# def get_note_or_404(note_id: int) -> dict:
#     res = supabase.table("notes").select("*").eq("id", note_id).execute()
#     if not res.data:
#         raise HTTPException(status_code=404, detail="Item not found.")
#     return res.data[0]


# def assert_can_modify(user: dict, note: dict):
#     """Can this user edit/delete this existing item?"""
#     role = user["role"]
#     if role == "admin":
#         return
#     if note.get("type") in NON_SUBJECT_TYPES:
#         raise HTTPException(status_code=403, detail="You can't modify this item.")
#     if role == "cr":
#         if note.get("branch") == user["branch"] and note.get("sem") == user["sem"]:
#             return
#     elif role == "teacher":
#         rec = find_subject(norm_subject(note.get("subject")), note.get("branch"), note.get("sem"))
#         if rec and rec["id"] in user["subject_ids"]:
#             return
#     raise HTTPException(status_code=403, detail="This item is outside your assigned scope.")


# async def store_file(file: UploadFile, year: str, branch: str, sem: str, subject: str, user: dict) -> str:
#     """Upload a PDF to the 'notes' bucket and return its public URL (same path scheme as before)."""
#     clean_name = clean_filename(file.filename) or "file.pdf"
#     file_bytes = await file.read()

#     if user["role"] != "admin":
#         if not clean_name.lower().endswith(".pdf"):
#             raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
#         if len(file_bytes) > MAX_STAFF_UPLOAD_MB * 1024 * 1024:
#             raise HTTPException(status_code=413, detail=f"File too large (max {MAX_STAFF_UPLOAD_MB} MB).")

#     storage_path = f"{year}/{branch}/{sem}/{subject}/{clean_name}"
#     print(f"📦 Uploading file to path: {storage_path}")

#     # "upsert": "true" allows overwriting if the same file is uploaded again
#     supabase.storage.from_("notes").upload(
#         path=storage_path,
#         file=file_bytes,
#         file_options={"content-type": "application/pdf", "upsert": "true"}
#     )
#     return supabase.storage.from_("notes").get_public_url(storage_path)


# # ==========================================
# # 🟢 LOGIN ENDPOINTS
# # ==========================================
# @app.post("/auth/admin-login")
# def admin_login(request: Request, password: str = Form(...), username: Optional[str] = Form(None)):
#     if not ADMIN_PASSWORD:
#         raise HTTPException(status_code=500, detail="ADMIN_PASSWORD is not set in the backend .env file.")
#     key = _throttle_key(request, "admin")
#     _check_throttle(key)

#     pw_ok = hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
#     user_ok = True
#     if username and ADMIN_USERNAME:
#         user_ok = hmac.compare_digest(username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8"))
#     if not (pw_ok and user_ok):
#         _record_failure(key)
#         raise HTTPException(status_code=401, detail="Wrong password.")

#     _FAILED_LOGINS.pop(key, None)
#     return {"token": create_token("admin"), "role": "admin", "user": {"name": "Admin"}}


# def _staff_login(request: Request, role: str, table: str, columns: str, email: str, password: str) -> dict:
#     key = _throttle_key(request, role)
#     _check_throttle(key)
#     res = supabase.table(table).select(columns + ",password_hash").eq("email", email.strip().lower()).execute()
#     row = res.data[0] if res.data else None
#     if not row or not verify_password(password, row["password_hash"]):
#         _record_failure(key)
#         raise HTTPException(status_code=401, detail="Invalid email or password.")
#     _FAILED_LOGINS.pop(key, None)
#     row.pop("password_hash", None)
#     return row


# @app.post("/auth/teacher-login")
# def teacher_login(request: Request, email: str = Form(...), password: str = Form(...)):
#     t = _staff_login(request, "teacher", "teachers", "id,name,email", email, password)
#     return {"token": create_token("teacher", t["id"]), "role": "teacher", "user": t}


# @app.post("/auth/cr-login")
# def cr_login(request: Request, email: str = Form(...), password: str = Form(...)):
#     c = _staff_login(request, "cr", "class_representatives", "id,name,email,branch,sem", email, password)
#     return {"token": create_token("cr", c["id"]), "role": "cr", "user": c}


# @app.get("/auth/me")
# def auth_me(user: dict = Depends(get_current_user)):
#     """Used by the dashboards to (re)load the logged-in user and their exact scope."""
#     out = {"role": user["role"], "user": {"id": user["id"], "name": user["name"], "email": user.get("email")}}
#     if user["role"] == "cr":
#         out["scope"] = {"year": user["year"], "branch": user["branch"], "sem": user["sem"]}
#     return out


# # ==========================================
# # 🟢 SUBJECT ENDPOINTS
# # ==========================================
# class SubjectIn(BaseModel):
#     name: str
#     branch: str
#     sem: str


# @app.get("/subjects")
# def list_subjects(user: dict = Depends(get_current_user)):
#     """Scope-aware list: admin -> all, teacher -> only assigned, CR -> own branch+sem."""
#     try:
#         if user["role"] == "admin":
#             res = supabase.table("subjects").select("*").order("branch").order("sem").order("name").execute()
#             return res.data or []
#         if user["role"] == "teacher":
#             return teacher_subjects(user["id"])
#         res = (supabase.table("subjects").select("*")
#                .eq("branch", user["branch"]).eq("sem", user["sem"]).order("name").execute())
#         return res.data or []
#     except HTTPException:
#         raise
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/subjects")
# def create_subject(body: SubjectIn, user: dict = Depends(require_admin)):
#     name = norm_subject(body.name)
#     if not name:
#         raise HTTPException(status_code=400, detail="Subject name is required.")
#     if body.sem not in SEM_TO_YEAR:
#         raise HTTPException(status_code=400, detail="Invalid semester.")
#     if not body.branch.strip():
#         raise HTTPException(status_code=400, detail="Branch is required.")

#     if find_subject(name, body.branch, body.sem):
#         raise HTTPException(status_code=409, detail=f"'{name}' already exists in {body.branch} · {body.sem}.")
#     try:
#         res = supabase.table("subjects").insert({
#             "name": name, "year": SEM_TO_YEAR[body.sem], "branch": body.branch, "sem": body.sem
#         }).execute()
#         return {"message": "Subject created", "data": res.data[0]}
#     except Exception as e:
#         if is_unique_violation(e):
#             raise HTTPException(status_code=409, detail=f"'{name}' already exists in {body.branch} · {body.sem}.")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ==========================================
# # 🟢 NOTES ENDPOINTS (upload / list / update / delete)
# # ==========================================
# @app.post("/upload")
# async def upload_note(
#     file: Optional[UploadFile] = File(None),
#     year: str = Form(...),
#     branch: str = Form(...),
#     sem: str = Form(...),
#     subject: str = Form(...),
#     unit: str = Form(...),
#     type: str = Form(...),
#     title: str = Form(...),
#     pdf_url: Optional[str] = Form(None),
#     youtube_url: Optional[str] = Form(None),
#     user: dict = Depends(get_current_user)
# ):
#     try:
#         # 1) RBAC: is this user allowed to upload into this year/branch/sem/subject?
#         year, branch, sem, subject = authorize_target(user, year, branch, sem, subject, type)

#         # 2) Subject registry: get-or-create (never creates a duplicate in the same branch+sem)
#         ensure_subject(user, subject, year, branch, sem, type)

#         final_url = pdf_url

#         # File Storage Upload logic
#         if file:
#             final_url = await store_file(file, year, branch, sem, subject, user)

#         if user["role"] != "admin" and not final_url:
#             raise HTTPException(status_code=400, detail="Please attach a PDF or provide a link.")

#         print(f"💾 Inserting record into database with URL: {final_url}")

#         db_res = supabase.table("notes").insert({
#             "year": year,
#             "branch": branch,
#             "sem": sem,
#             "subject": subject,
#             "unit": unit,
#             "type": type,
#             "title": title,
#             "pdf_url": final_url,
#             "uploaded_by_role": user["role"],
#             "uploaded_by_id": user["id"]
#         }).execute()

#         print("✅ Insert Success:", db_res.data)
#         return {"message": "Uploaded successfully"}

#     except HTTPException:
#         raise
#     except Exception as e:
#         print("\n❌ --- UPLOAD ERROR TRACEBACK ---")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/notes-all")
# def get_all_notes():
#     # Public on purpose: the student app needs it.
#     try:
#         response = supabase.table("notes").select("*").execute()
#         print(f"📥 Fetched {len(response.data)} notes from database.")
#         return response.data
#     except Exception as e:
#         print("\n❌ --- FETCH ERROR TRACEBACK ---")
#         traceback.print_exc()
#         return []


# @app.get("/staff/notes")
# def get_my_scope_notes(user: dict = Depends(get_current_user)):
#     """Materials a logged-in user is allowed to manage (admin: everything)."""
#     try:
#         if user["role"] == "admin":
#             res = supabase.table("notes").select("*").order("id", desc=True).execute()
#             return res.data or []

#         if user["role"] == "cr":
#             res = (supabase.table("notes").select("*")
#                    .eq("branch", user["branch"]).eq("sem", user["sem"]).order("id", desc=True).execute())
#             return [n for n in (res.data or []) if n.get("type") not in NON_SUBJECT_TYPES]

#         subs = teacher_subjects(user["id"])
#         if not subs:
#             return []
#         allowed = {(s["name"], s["branch"], s["sem"]) for s in subs}
#         res = (supabase.table("notes").select("*")
#                .in_("branch", sorted({s["branch"] for s in subs}))
#                .in_("sem", sorted({s["sem"] for s in subs}))
#                .order("id", desc=True).execute())
#         return [n for n in (res.data or [])
#                 if n.get("type") not in NON_SUBJECT_TYPES
#                 and (norm_subject(n.get("subject")), n.get("branch"), n.get("sem")) in allowed]
#     except HTTPException:
#         raise
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.delete("/delete/{note_id}")
# def delete_note(note_id: int, user: dict = Depends(get_current_user)):
#     try:
#         note = get_note_or_404(note_id)
#         assert_can_modify(user, note)
#         supabase.table("notes").delete().eq("id", note_id).execute()
#         return {"message": "Deleted successfully"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.put("/update/{note_id}")
# async def update_note(
#     note_id: int,
#     title: Optional[str] = Form(None),
#     subject: Optional[str] = Form(None),
#     year: Optional[str] = Form(None),
#     branch: Optional[str] = Form(None),
#     sem: Optional[str] = Form(None),
#     unit: Optional[str] = Form(None),
#     type: Optional[str] = Form(None),
#     pdf_url: Optional[str] = Form(None),
#     file: Optional[UploadFile] = File(None),
#     user: dict = Depends(get_current_user)
# ):
#     """Edit details and/or replace the file. Every field is optional; only what is sent changes."""
#     try:
#         existing = get_note_or_404(note_id)
#         assert_can_modify(user, existing)   # is the CURRENT item inside my scope?

#         def pick(new, key):
#             return new if new is not None else existing.get(key)

#         merged = {
#             "title": pick(title, "title"),
#             "subject": pick(subject, "subject"),
#             "year": pick(year, "year"),
#             "branch": pick(branch, "branch"),
#             "sem": pick(sem, "sem"),
#             "unit": pick(unit, "unit"),
#             "type": pick(type, "type"),
#         }

#         # ...and is the NEW target inside my scope too? (stops a teacher moving items elsewhere)
#         m_year, m_branch, m_sem, m_subject = authorize_target(
#             user, merged["year"], merged["branch"], merged["sem"], merged["subject"], merged["type"]
#         )
#         ensure_subject(user, m_subject, m_year, m_branch, m_sem, merged["type"])

#         payload = {
#             "title": merged["title"],
#             "unit": merged["unit"],
#             "type": merged["type"],
#             "year": m_year,
#             "branch": m_branch,
#             "sem": m_sem,
#             "subject": m_subject,
#         }

#         if file:
#             payload["pdf_url"] = await store_file(file, m_year, m_branch, m_sem, m_subject, user)
#         elif pdf_url is not None and pdf_url.strip():
#             payload["pdf_url"] = pdf_url.strip()

#         supabase.table("notes").update(payload).eq("id", note_id).execute()
#         return {"message": "Updated successfully"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ==========================================
# # 🟢 ADMIN: TEACHER MANAGEMENT
# # ==========================================
# class TeacherIn(BaseModel):
#     name: str
#     email: str
#     password: Optional[str] = None      # required on create, optional on edit
#     subject_ids: List[int] = []


# def _validate_subject_ids(ids: List[int]) -> List[int]:
#     ids = sorted(set(ids))
#     if not ids:
#         raise HTTPException(status_code=400, detail="Assign at least one subject to the teacher.")
#     res = supabase.table("subjects").select("id").in_("id", ids).execute()
#     if len(res.data or []) != len(ids):
#         raise HTTPException(status_code=400, detail="One or more selected subjects no longer exist.")
#     return ids


# def _set_teacher_assignments(teacher_id: int, ids: List[int]):
#     supabase.table("teacher_assignments").delete().eq("teacher_id", teacher_id).execute()
#     supabase.table("teacher_assignments").insert(
#         [{"teacher_id": teacher_id, "subject_id": sid} for sid in ids]
#     ).execute()


# @app.get("/admin/teachers")
# def list_teachers(_: dict = Depends(require_admin)):
#     try:
#         teachers = supabase.table("teachers").select("id,name,email,created_at").order("name").execute().data or []
#         assigns = supabase.table("teacher_assignments").select("teacher_id,subject_id").execute().data or []
#         subj = {s["id"]: s for s in (supabase.table("subjects").select("*").execute().data or [])}
#         by_teacher: dict = {}
#         for a in assigns:
#             s = subj.get(a["subject_id"])
#             if s:
#                 by_teacher.setdefault(a["teacher_id"], []).append(s)
#         for t in teachers:
#             t["assignments"] = sorted(by_teacher.get(t["id"], []),
#                                       key=lambda s: (s["branch"], s["sem"], s["name"]))
#         return teachers
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/admin/teachers")
# def create_teacher(body: TeacherIn, _: dict = Depends(require_admin)):
#     name = body.name.strip()
#     email = body.email.strip().lower()
#     if not name:
#         raise HTTPException(status_code=400, detail="Teacher name is required.")
#     if not valid_email(email):
#         raise HTTPException(status_code=400, detail="Enter a valid email address.")
#     if not body.password:
#         raise HTTPException(status_code=400, detail="Password is required.")
#     check_password_rules(body.password)
#     ids = _validate_subject_ids(body.subject_ids)

#     if supabase.table("teachers").select("id").eq("email", email).execute().data:
#         raise HTTPException(status_code=409, detail="A teacher with this email already exists.")
#     try:
#         res = supabase.table("teachers").insert({
#             "name": name, "email": email, "password_hash": hash_password(body.password)
#         }).execute()
#         tid = res.data[0]["id"]
#         _set_teacher_assignments(tid, ids)
#         return {"message": "Teacher registered successfully", "id": tid}
#     except Exception as e:
#         if is_unique_violation(e):
#             raise HTTPException(status_code=409, detail="A teacher with this email already exists.")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.put("/admin/teachers/{teacher_id}")
# def update_teacher(teacher_id: int, body: TeacherIn, _: dict = Depends(require_admin)):
#     name = body.name.strip()
#     email = body.email.strip().lower()
#     if not name:
#         raise HTTPException(status_code=400, detail="Teacher name is required.")
#     if not valid_email(email):
#         raise HTTPException(status_code=400, detail="Enter a valid email address.")
#     ids = _validate_subject_ids(body.subject_ids)

#     if not supabase.table("teachers").select("id").eq("id", teacher_id).execute().data:
#         raise HTTPException(status_code=404, detail="Teacher not found.")
#     clash = supabase.table("teachers").select("id").eq("email", email).neq("id", teacher_id).execute().data
#     if clash:
#         raise HTTPException(status_code=409, detail="Another teacher already uses this email.")

#     payload = {"name": name, "email": email}
#     if body.password:
#         check_password_rules(body.password)
#         payload["password_hash"] = hash_password(body.password)
#     try:
#         supabase.table("teachers").update(payload).eq("id", teacher_id).execute()
#         _set_teacher_assignments(teacher_id, ids)
#         return {"message": "Teacher updated successfully"}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.delete("/admin/teachers/{teacher_id}")
# def delete_teacher(teacher_id: int, _: dict = Depends(require_admin)):
#     try:
#         supabase.table("teachers").delete().eq("id", teacher_id).execute()   # assignments cascade
#         return {"message": "Teacher deleted"}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ==========================================
# # 🟢 ADMIN: CLASS REPRESENTATIVE MANAGEMENT
# # ==========================================
# class CRIn(BaseModel):
#     name: str
#     email: str
#     password: Optional[str] = None
#     branch: str
#     sem: str


# def _validate_cr(body: CRIn):
#     if not body.name.strip():
#         raise HTTPException(status_code=400, detail="CR name is required.")
#     if not valid_email(body.email.strip().lower()):
#         raise HTTPException(status_code=400, detail="Enter a valid email address.")
#     if not body.branch.strip():
#         raise HTTPException(status_code=400, detail="Branch is required.")
#     if body.sem not in SEM_TO_YEAR:
#         raise HTTPException(status_code=400, detail="Invalid semester.")


# @app.get("/admin/crs")
# def list_crs(_: dict = Depends(require_admin)):
#     try:
#         res = (supabase.table("class_representatives")
#                .select("id,name,email,branch,sem,created_at").order("name").execute())
#         return res.data or []
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/admin/crs")
# def create_cr(body: CRIn, _: dict = Depends(require_admin)):
#     _validate_cr(body)
#     if not body.password:
#         raise HTTPException(status_code=400, detail="Password is required.")
#     check_password_rules(body.password)
#     email = body.email.strip().lower()

#     if supabase.table("class_representatives").select("id").eq("email", email).execute().data:
#         raise HTTPException(status_code=409, detail="A CR with this email already exists.")
#     try:
#         res = supabase.table("class_representatives").insert({
#             "name": body.name.strip(), "email": email,
#             "password_hash": hash_password(body.password),
#             "branch": body.branch.strip(), "sem": body.sem
#         }).execute()
#         return {"message": "CR registered successfully", "id": res.data[0]["id"]}
#     except Exception as e:
#         if is_unique_violation(e):
#             raise HTTPException(status_code=409, detail="A CR with this email already exists.")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.put("/admin/crs/{cr_id}")
# def update_cr(cr_id: int, body: CRIn, _: dict = Depends(require_admin)):
#     _validate_cr(body)
#     email = body.email.strip().lower()

#     if not supabase.table("class_representatives").select("id").eq("id", cr_id).execute().data:
#         raise HTTPException(status_code=404, detail="CR not found.")
#     clash = supabase.table("class_representatives").select("id").eq("email", email).neq("id", cr_id).execute().data
#     if clash:
#         raise HTTPException(status_code=409, detail="Another CR already uses this email.")

#     payload = {"name": body.name.strip(), "email": email, "branch": body.branch.strip(), "sem": body.sem}
#     if body.password:
#         check_password_rules(body.password)
#         payload["password_hash"] = hash_password(body.password)
#     try:
#         supabase.table("class_representatives").update(payload).eq("id", cr_id).execute()
#         return {"message": "CR updated successfully"}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.delete("/admin/crs/{cr_id}")
# def delete_cr(cr_id: int, _: dict = Depends(require_admin)):
#     try:
#         supabase.table("class_representatives").delete().eq("id", cr_id).execute()
#         return {"message": "CR deleted"}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# # ==========================================
# # 🟢 NOTICE BOARD CRUD ENDPOINTS  (write access is now admin-only)
# # ==========================================
# # Notices are stored in their own "notices" table (see schema.sql).
# # Attached PDFs (e.g. exam timetables) reuse the existing "notes" storage
# # bucket, but are kept under a dedicated "notices/" folder so they don't
# # mix with subject material.

# @app.post("/notices")
# async def create_notice(
#     title: str = Form(...),
#     content: str = Form(...),
#     file: Optional[UploadFile] = File(None),
#     _: dict = Depends(require_admin)
# ):
#     try:
#         final_url = None

#         if file:
#             clean_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_").strip()
#             file_bytes = await file.read()
#             storage_path = f"notices/{clean_name}"

#             print(f"📌 Uploading notice PDF to path: {storage_path}")

#             supabase.storage.from_("notes").upload(
#                 path=storage_path,
#                 file=file_bytes,
#                 file_options={"content-type": "application/pdf", "upsert": "true"}
#             )
#             final_url = supabase.storage.from_("notes").get_public_url(storage_path)

#         db_res = supabase.table("notices").insert({
#             "title": title,
#             "content": content,
#             "pdf_url": final_url
#         }).execute()

#         print("✅ Notice Insert Success:", db_res.data)
#         return {"message": "Notice created successfully", "data": db_res.data}

#     except Exception as e:
#         print("\n❌ --- NOTICE CREATE ERROR TRACEBACK ---")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/notices-all")
# def get_all_notices():
#     try:
#         response = supabase.table("notices").select("*").order("created_at", desc=True).execute()
#         print(f"📥 Fetched {len(response.data)} notices from database.")
#         return response.data
#     except Exception as e:
#         print("\n❌ --- NOTICE FETCH ERROR TRACEBACK ---")
#         traceback.print_exc()
#         return []


# @app.put("/notices/{notice_id}")
# async def update_notice(
#     notice_id: int,
#     title: str = Form(...),
#     content: str = Form(...),
#     file: Optional[UploadFile] = File(None),
#     _: dict = Depends(require_admin)
# ):
#     try:
#         update_payload = {
#             "title": title,
#             "content": content,
#         }

#         # Only touch pdf_url if the admin uploaded a replacement file,
#         # so existing attachments aren't wiped out on a text-only edit.
#         if file:
#             clean_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_").strip()
#             file_bytes = await file.read()
#             storage_path = f"notices/{clean_name}"

#             supabase.storage.from_("notes").upload(
#                 path=storage_path,
#                 file=file_bytes,
#                 file_options={"content-type": "application/pdf", "upsert": "true"}
#             )
#             update_payload["pdf_url"] = supabase.storage.from_("notes").get_public_url(storage_path)

#         supabase.table("notices").update(update_payload).eq("id", notice_id).execute()
#         return {"message": "Notice updated successfully"}

#     except Exception as e:
#         print("\n❌ --- NOTICE UPDATE ERROR TRACEBACK ---")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


# @app.delete("/notices/{notice_id}")
# def delete_notice(notice_id: int, _: dict = Depends(require_admin)):
#     try:
#         supabase.table("notices").delete().eq("id", notice_id).execute()
#         return {"message": "Notice deleted successfully"}
#     except Exception as e:
#         print("\n❌ --- NOTICE DELETE ERROR TRACEBACK ---")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

# newwwwwwwwwwwwwwwwwwwwwwwww

import os
import re
import hmac
import time
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, Form, File, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Navjeevan Study App API")

# CORS setup - allowing all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: .env file me SUPABASE_URL ya SUPABASE_KEY missing hai!")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 🟢 AUTH / RBAC CONFIGURATION
# ==========================================
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    print("⚠️  JWT_SECRET missing in .env - using a temporary random one. "
          "Everyone will be logged out whenever the server restarts. "
          "Add a long random JWT_SECRET to .env.")
    JWT_SECRET = secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))

# Can a CR create a brand-new subject inside their own branch+sem?
# Set CR_CAN_CREATE_SUBJECTS=false in .env to force CRs to pick from
# subjects the admin has already created.
CR_CAN_CREATE_SUBJECTS = os.getenv("CR_CAN_CREATE_SUBJECTS", "true").lower() == "true"

MAX_STAFF_UPLOAD_MB = int(os.getenv("MAX_STAFF_UPLOAD_MB", "50"))

# Types that are NOT tied to a subject in the registry (admin-only).
NON_SUBJECT_TYPES = {"Tool", "Skills", "Official Syllabus"}
# Categories a teacher / CR is allowed to upload (same as the admin upload form).
STAFF_ALLOWED_TYPES = {"Syllabus", "Notes", "PYQs", "IMP Questions",
                       "Assignments", "YouTube Links", "Laboratory"}

SEM_TO_YEAR = {
    "Common": "1st Year", "Sem 1": "1st Year", "Sem 2": "1st Year",
    "Sem 3": "2nd Year", "Sem 4": "2nd Year",
    "Sem 5": "3rd Year", "Sem 6": "3rd Year",
    "Sem 7": "4th Year", "Sem 8": "4th Year",
}


# ==========================================
# 🟢 SMALL HELPERS
# ==========================================
def norm_subject(name: Optional[str]) -> str:
    """'  math   3 ' -> 'MATH 3'  (collapse spaces, trim, uppercase)."""
    return re.sub(r"\s+", " ", (name or "").strip()).upper()


def clean_filename(name: Optional[str]) -> str:
    return "".join(c for c in (name or "") if c.isalnum() or c in ".-_").strip()


def is_unique_violation(e: Exception) -> bool:
    s = str(e).lower()
    return "23505" in s or "duplicate key" in s or "already exists" in s


def valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))


def check_password_rules(pw: str):
    if len(pw) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if len(pw.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password is too long (max 72 bytes).")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(role: str, user_id: Optional[int] = None) -> str:
    payload = {
        "role": role,
        "sub": str(user_id) if user_id is not None else "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---- very small in-memory brute-force guard for the login endpoints ----
_FAILED_LOGINS: dict = {}


def _throttle_key(request: Request, role: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"{role}:{ip}"


def _check_throttle(key: str, limit: int = 8, window: int = 600):
    now = time.time()
    hits = [t for t in _FAILED_LOGINS.get(key, []) if now - t < window]
    _FAILED_LOGINS[key] = hits
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please wait a few minutes and try again.")


def _record_failure(key: str):
    _FAILED_LOGINS.setdefault(key, []).append(time.time())


# ==========================================
# 🟢 SUBJECT REGISTRY HELPERS
# ==========================================
def find_subject(name_upper: str, branch: str, sem: str) -> Optional[dict]:
    res = (supabase.table("subjects").select("*")
           .eq("name", name_upper).eq("branch", branch).eq("sem", sem)
           .limit(1).execute())
    return res.data[0] if res.data else None


def get_or_create_subject(name_upper: str, year: str, branch: str, sem: str) -> dict:
    """Return the subject for (name, branch, sem); create it only if it doesn't exist yet.
    The DB has a unique index on (upper(name), branch, sem), so duplicates are impossible
    even if two uploads race each other."""
    existing = find_subject(name_upper, branch, sem)
    if existing:
        return existing
    try:
        res = supabase.table("subjects").insert({
            "name": name_upper, "year": year, "branch": branch, "sem": sem
        }).execute()
        print(f"🆕 Subject created: {name_upper} | {branch} | {sem}")
        return res.data[0]
    except Exception as e:
        if is_unique_violation(e):
            again = find_subject(name_upper, branch, sem)
            if again:
                return again
        raise


def teacher_subject_ids(teacher_id: int) -> set:
    res = supabase.table("teacher_assignments").select("subject_id").eq("teacher_id", teacher_id).execute()
    return {r["subject_id"] for r in (res.data or [])}


def teacher_subjects(teacher_id: int) -> list:
    ids = list(teacher_subject_ids(teacher_id))
    if not ids:
        return []
    res = (supabase.table("subjects").select("*").in_("id", ids)
           .order("branch").order("sem").order("name").execute())
    return res.data or []


# ==========================================
# 🟢 AUTH DEPENDENCIES
# ==========================================
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Decode the Bearer token and load the *current* account from the DB, so a deleted
    teacher/CR loses access immediately and assignment changes apply instantly."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    token = authorization[7:].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")

    role = payload.get("role")

    if role == "admin":
        return {"role": "admin", "id": None, "name": "Admin"}

    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid session.")

    if role == "teacher":
        res = supabase.table("teachers").select("id,name,email").eq("id", uid).execute()
        if not res.data:
            raise HTTPException(status_code=401, detail="This account no longer exists.")
        t = res.data[0]
        return {"role": "teacher", "id": t["id"], "name": t["name"], "email": t["email"],
                "subject_ids": teacher_subject_ids(t["id"])}

    if role == "cr":
        res = supabase.table("class_representatives").select("id,name,email,branch,sem").eq("id", uid).execute()
        if not res.data:
            raise HTTPException(status_code=401, detail="This account no longer exists.")
        c = res.data[0]
        return {"role": "cr", "id": c["id"], "name": c["name"], "email": c["email"],
                "branch": c["branch"], "sem": c["sem"], "year": SEM_TO_YEAR.get(c["sem"], "")}

    raise HTTPException(status_code=401, detail="Invalid session.")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


# ==========================================
# 🟢 SCOPE ENFORCEMENT (the heart of the RBAC)
# ==========================================
def authorize_target(user: dict, year: str, branch: str, sem: str, subject: str, note_type: str):
    """Validate that `user` may put material of `note_type` into (branch, sem, subject).
    Returns the normalised (year, branch, sem, subject). Admin = unrestricted (as before)."""
    subject = norm_subject(subject)

    if user["role"] == "admin":
        if not subject and note_type not in NON_SUBJECT_TYPES:
            raise HTTPException(status_code=400, detail="Subject name is required.")
        return year, branch, sem, subject

    # ---- teacher / CR from here on ----
    if note_type not in STAFF_ALLOWED_TYPES:
        raise HTTPException(status_code=403, detail=f"You are not allowed to upload '{note_type}'.")
    if not subject:
        raise HTTPException(status_code=400, detail="Subject name is required.")
    if sem not in SEM_TO_YEAR:
        raise HTTPException(status_code=400, detail="Invalid semester.")

    # Never trust the year sent by the browser - derive it from the semester.
    year = SEM_TO_YEAR[sem]

    if user["role"] == "cr":
        if branch != user["branch"] or sem != user["sem"]:
            raise HTTPException(status_code=403, detail="You can only upload for your own branch and semester.")
        return year, branch, sem, subject

    if user["role"] == "teacher":
        assigned = teacher_subjects(user["id"])
        # Normalise BOTH sides before comparing. Subjects created before this RBAC
        # system existed were only trim()'d in SQL (no internal-whitespace collapse),
        # so a name like "OPEN ELECTIVE ( QUANTUM COMPUTING)" can be stored with
        # slightly different internal spacing than what a fresh upload normalises
        # the same name to - even though it looks identical on screen. Normalising
        # the stored name here too makes the match immune to that.
        is_assigned = any(
            norm_subject(s["name"]) == subject and s["branch"] == branch and s["sem"] == sem
            for s in assigned
        )
        if not is_assigned:
            raise HTTPException(status_code=403, detail="You are not assigned to this subject / branch / semester.")
        return year, branch, sem, subject

    raise HTTPException(status_code=403, detail="Forbidden.")


def ensure_subject(user: dict, subject: str, year: str, branch: str, sem: str, note_type: str):
    """Make sure the subject exists in the registry (get-or-create), respecting who may create."""
    if note_type in NON_SUBJECT_TYPES:
        return None
    if user["role"] == "teacher":
        return None  # already verified as an assigned, existing subject
    if user["role"] == "cr" and not CR_CAN_CREATE_SUBJECTS:
        rec = find_subject(subject, branch, sem)
        if not rec:
            raise HTTPException(status_code=403, detail="This subject doesn't exist yet. Ask the admin to create it first.")
        return rec
    return get_or_create_subject(subject, year, branch, sem)


def get_note_or_404(note_id: int) -> dict:
    res = supabase.table("notes").select("*").eq("id", note_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Item not found.")
    return res.data[0]


def assert_can_modify(user: dict, note: dict):
    """Can this user edit/delete this existing item?"""
    role = user["role"]
    if role == "admin":
        return
    if note.get("type") in NON_SUBJECT_TYPES:
        raise HTTPException(status_code=403, detail="You can't modify this item.")
    if role == "cr":
        if note.get("branch") == user["branch"] and note.get("sem") == user["sem"]:
            return
    elif role == "teacher":
        subj = norm_subject(note.get("subject"))
        assigned = teacher_subjects(user["id"])
        if any(norm_subject(s["name"]) == subj and s["branch"] == note.get("branch") and s["sem"] == note.get("sem") for s in assigned):
            return
    raise HTTPException(status_code=403, detail="This item is outside your assigned scope.")


async def store_file(file: UploadFile, year: str, branch: str, sem: str, subject: str, user: dict) -> str:
    """Upload a PDF to the 'notes' bucket and return its public URL (same path scheme as before)."""
    clean_name = clean_filename(file.filename) or "file.pdf"
    file_bytes = await file.read()

    if user["role"] != "admin":
        if not clean_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        if len(file_bytes) > MAX_STAFF_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File too large (max {MAX_STAFF_UPLOAD_MB} MB).")

    storage_path = f"{year}/{branch}/{sem}/{subject}/{clean_name}"
    print(f"📦 Uploading file to path: {storage_path}")

    # "upsert": "true" allows overwriting if the same file is uploaded again
    supabase.storage.from_("notes").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"}
    )
    return supabase.storage.from_("notes").get_public_url(storage_path)


# ==========================================
# 🟢 LOGIN ENDPOINTS
# ==========================================
@app.post("/auth/admin-login")
def admin_login(request: Request, password: str = Form(...), username: Optional[str] = Form(None)):
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD is not set in the backend .env file.")
    key = _throttle_key(request, "admin")
    _check_throttle(key)

    pw_ok = hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    user_ok = True
    if username and ADMIN_USERNAME:
        user_ok = hmac.compare_digest(username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8"))
    if not (pw_ok and user_ok):
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Wrong password.")

    _FAILED_LOGINS.pop(key, None)
    return {"token": create_token("admin"), "role": "admin", "user": {"name": "Admin"}}


def _staff_login(request: Request, role: str, table: str, columns: str, email: str, password: str) -> dict:
    key = _throttle_key(request, role)
    _check_throttle(key)
    res = supabase.table(table).select(columns + ",password_hash").eq("email", email.strip().lower()).execute()
    row = res.data[0] if res.data else None
    if not row or not verify_password(password, row["password_hash"]):
        _record_failure(key)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _FAILED_LOGINS.pop(key, None)
    row.pop("password_hash", None)
    return row


@app.post("/auth/teacher-login")
def teacher_login(request: Request, email: str = Form(...), password: str = Form(...)):
    t = _staff_login(request, "teacher", "teachers", "id,name,email", email, password)
    return {"token": create_token("teacher", t["id"]), "role": "teacher", "user": t}


@app.post("/auth/cr-login")
def cr_login(request: Request, email: str = Form(...), password: str = Form(...)):
    c = _staff_login(request, "cr", "class_representatives", "id,name,email,branch,sem", email, password)
    return {"token": create_token("cr", c["id"]), "role": "cr", "user": c}


@app.get("/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    """Used by the dashboards to (re)load the logged-in user and their exact scope."""
    out = {"role": user["role"], "user": {"id": user["id"], "name": user["name"], "email": user.get("email")}}
    if user["role"] == "cr":
        out["scope"] = {"year": user["year"], "branch": user["branch"], "sem": user["sem"]}
    return out


# ==========================================
# 🟢 SUBJECT ENDPOINTS
# ==========================================
class SubjectIn(BaseModel):
    name: str
    branch: str
    sem: str


@app.get("/subjects")
def list_subjects(user: dict = Depends(get_current_user)):
    """Scope-aware list: admin -> all, teacher -> only assigned, CR -> own branch+sem."""
    try:
        if user["role"] == "admin":
            res = supabase.table("subjects").select("*").order("branch").order("sem").order("name").execute()
            return res.data or []
        if user["role"] == "teacher":
            return teacher_subjects(user["id"])
        res = (supabase.table("subjects").select("*")
               .eq("branch", user["branch"]).eq("sem", user["sem"]).order("name").execute())
        return res.data or []
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/subjects")
def create_subject(body: SubjectIn, user: dict = Depends(require_admin)):
    name = norm_subject(body.name)
    if not name:
        raise HTTPException(status_code=400, detail="Subject name is required.")
    if body.sem not in SEM_TO_YEAR:
        raise HTTPException(status_code=400, detail="Invalid semester.")
    if not body.branch.strip():
        raise HTTPException(status_code=400, detail="Branch is required.")

    if find_subject(name, body.branch, body.sem):
        raise HTTPException(status_code=409, detail=f"'{name}' already exists in {body.branch} · {body.sem}.")
    try:
        res = supabase.table("subjects").insert({
            "name": name, "year": SEM_TO_YEAR[body.sem], "branch": body.branch, "sem": body.sem
        }).execute()
        return {"message": "Subject created", "data": res.data[0]}
    except Exception as e:
        if is_unique_violation(e):
            raise HTTPException(status_code=409, detail=f"'{name}' already exists in {body.branch} · {body.sem}.")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 🟢 NOTES ENDPOINTS (upload / list / update / delete)
# ==========================================
@app.post("/upload")
async def upload_note(
    file: Optional[UploadFile] = File(None),
    year: str = Form(...),
    branch: str = Form(...),
    sem: str = Form(...),
    subject: str = Form(...),
    unit: str = Form(...),
    type: str = Form(...),
    title: str = Form(...),
    pdf_url: Optional[str] = Form(None),
    youtube_url: Optional[str] = Form(None),
    user: dict = Depends(get_current_user)
):
    try:
        # 1) RBAC: is this user allowed to upload into this year/branch/sem/subject?
        year, branch, sem, subject = authorize_target(user, year, branch, sem, subject, type)

        # 2) Subject registry: get-or-create (never creates a duplicate in the same branch+sem)
        ensure_subject(user, subject, year, branch, sem, type)

        final_url = pdf_url

        # File Storage Upload logic
        if file:
            final_url = await store_file(file, year, branch, sem, subject, user)

        if user["role"] != "admin" and not final_url:
            raise HTTPException(status_code=400, detail="Please attach a PDF or provide a link.")

        print(f"💾 Inserting record into database with URL: {final_url}")

        db_res = supabase.table("notes").insert({
            "year": year,
            "branch": branch,
            "sem": sem,
            "subject": subject,
            "unit": unit,
            "type": type,
            "title": title,
            "pdf_url": final_url,
            "uploaded_by_role": user["role"],
            "uploaded_by_id": user["id"]
        }).execute()

        print("✅ Insert Success:", db_res.data)
        return {"message": "Uploaded successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print("\n❌ --- UPLOAD ERROR TRACEBACK ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notes-all")
def get_all_notes():
    # Public on purpose: the student app needs it.
    try:
        response = supabase.table("notes").select("*").execute()
        print(f"📥 Fetched {len(response.data)} notes from database.")
        return response.data
    except Exception as e:
        print("\n❌ --- FETCH ERROR TRACEBACK ---")
        traceback.print_exc()
        return []


@app.get("/staff/notes")
def get_my_scope_notes(user: dict = Depends(get_current_user)):
    """Materials a logged-in user is allowed to manage (admin: everything)."""
    try:
        if user["role"] == "admin":
            res = supabase.table("notes").select("*").order("id", desc=True).execute()
            return res.data or []

        if user["role"] == "cr":
            res = (supabase.table("notes").select("*")
                   .eq("branch", user["branch"]).eq("sem", user["sem"]).order("id", desc=True).execute())
            return [n for n in (res.data or []) if n.get("type") not in NON_SUBJECT_TYPES]

        subs = teacher_subjects(user["id"])
        if not subs:
            return []
        allowed = {(s["name"], s["branch"], s["sem"]) for s in subs}
        res = (supabase.table("notes").select("*")
               .in_("branch", sorted({s["branch"] for s in subs}))
               .in_("sem", sorted({s["sem"] for s in subs}))
               .order("id", desc=True).execute())
        return [n for n in (res.data or [])
                if n.get("type") not in NON_SUBJECT_TYPES
                and (norm_subject(n.get("subject")), n.get("branch"), n.get("sem")) in allowed]
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete/{note_id}")
def delete_note(note_id: int, user: dict = Depends(get_current_user)):
    try:
        note = get_note_or_404(note_id)
        assert_can_modify(user, note)
        supabase.table("notes").delete().eq("id", note_id).execute()
        return {"message": "Deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/update/{note_id}")
async def update_note(
    note_id: int,
    title: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    branch: Optional[str] = Form(None),
    sem: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    pdf_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user)
):
    """Edit details and/or replace the file. Every field is optional; only what is sent changes."""
    try:
        existing = get_note_or_404(note_id)
        assert_can_modify(user, existing)   # is the CURRENT item inside my scope?

        def pick(new, key):
            return new if new is not None else existing.get(key)

        merged = {
            "title": pick(title, "title"),
            "subject": pick(subject, "subject"),
            "year": pick(year, "year"),
            "branch": pick(branch, "branch"),
            "sem": pick(sem, "sem"),
            "unit": pick(unit, "unit"),
            "type": pick(type, "type"),
        }

        # ...and is the NEW target inside my scope too? (stops a teacher moving items elsewhere)
        m_year, m_branch, m_sem, m_subject = authorize_target(
            user, merged["year"], merged["branch"], merged["sem"], merged["subject"], merged["type"]
        )
        ensure_subject(user, m_subject, m_year, m_branch, m_sem, merged["type"])

        payload = {
            "title": merged["title"],
            "unit": merged["unit"],
            "type": merged["type"],
            "year": m_year,
            "branch": m_branch,
            "sem": m_sem,
            "subject": m_subject,
        }

        if file:
            payload["pdf_url"] = await store_file(file, m_year, m_branch, m_sem, m_subject, user)
        elif pdf_url is not None and pdf_url.strip():
            payload["pdf_url"] = pdf_url.strip()

        supabase.table("notes").update(payload).eq("id", note_id).execute()
        return {"message": "Updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 🟢 ADMIN: TEACHER MANAGEMENT
# ==========================================
class TeacherIn(BaseModel):
    name: str
    email: str
    password: Optional[str] = None      # required on create, optional on edit
    subject_ids: List[int] = []


def _validate_subject_ids(ids: List[int]) -> List[int]:
    ids = sorted(set(ids))
    if not ids:
        raise HTTPException(status_code=400, detail="Assign at least one subject to the teacher.")
    res = supabase.table("subjects").select("id").in_("id", ids).execute()
    if len(res.data or []) != len(ids):
        raise HTTPException(status_code=400, detail="One or more selected subjects no longer exist.")
    return ids


def _set_teacher_assignments(teacher_id: int, ids: List[int]):
    supabase.table("teacher_assignments").delete().eq("teacher_id", teacher_id).execute()
    supabase.table("teacher_assignments").insert(
        [{"teacher_id": teacher_id, "subject_id": sid} for sid in ids]
    ).execute()


@app.get("/admin/teachers")
def list_teachers(_: dict = Depends(require_admin)):
    try:
        teachers = supabase.table("teachers").select("id,name,email,created_at").order("name").execute().data or []
        assigns = supabase.table("teacher_assignments").select("teacher_id,subject_id").execute().data or []
        subj = {s["id"]: s for s in (supabase.table("subjects").select("*").execute().data or [])}
        by_teacher: dict = {}
        for a in assigns:
            s = subj.get(a["subject_id"])
            if s:
                by_teacher.setdefault(a["teacher_id"], []).append(s)
        for t in teachers:
            t["assignments"] = sorted(by_teacher.get(t["id"], []),
                                      key=lambda s: (s["branch"], s["sem"], s["name"]))
        return teachers
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/teachers")
def create_teacher(body: TeacherIn, _: dict = Depends(require_admin)):
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Teacher name is required.")
    if not valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required.")
    check_password_rules(body.password)
    ids = _validate_subject_ids(body.subject_ids)

    if supabase.table("teachers").select("id").eq("email", email).execute().data:
        raise HTTPException(status_code=409, detail="A teacher with this email already exists.")
    try:
        res = supabase.table("teachers").insert({
            "name": name, "email": email, "password_hash": hash_password(body.password)
        }).execute()
        tid = res.data[0]["id"]
        _set_teacher_assignments(tid, ids)
        return {"message": "Teacher registered successfully", "id": tid}
    except Exception as e:
        if is_unique_violation(e):
            raise HTTPException(status_code=409, detail="A teacher with this email already exists.")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/admin/teachers/{teacher_id}")
def update_teacher(teacher_id: int, body: TeacherIn, _: dict = Depends(require_admin)):
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Teacher name is required.")
    if not valid_email(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    ids = _validate_subject_ids(body.subject_ids)

    if not supabase.table("teachers").select("id").eq("id", teacher_id).execute().data:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    clash = supabase.table("teachers").select("id").eq("email", email).neq("id", teacher_id).execute().data
    if clash:
        raise HTTPException(status_code=409, detail="Another teacher already uses this email.")

    payload = {"name": name, "email": email}
    if body.password:
        check_password_rules(body.password)
        payload["password_hash"] = hash_password(body.password)
    try:
        supabase.table("teachers").update(payload).eq("id", teacher_id).execute()
        _set_teacher_assignments(teacher_id, ids)
        return {"message": "Teacher updated successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, _: dict = Depends(require_admin)):
    try:
        supabase.table("teachers").delete().eq("id", teacher_id).execute()   # assignments cascade
        return {"message": "Teacher deleted"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 🟢 ADMIN: CLASS REPRESENTATIVE MANAGEMENT
# ==========================================
class CRIn(BaseModel):
    name: str
    email: str
    password: Optional[str] = None
    branch: str
    sem: str


def _validate_cr(body: CRIn):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="CR name is required.")
    if not valid_email(body.email.strip().lower()):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if not body.branch.strip():
        raise HTTPException(status_code=400, detail="Branch is required.")
    if body.sem not in SEM_TO_YEAR:
        raise HTTPException(status_code=400, detail="Invalid semester.")


@app.get("/admin/crs")
def list_crs(_: dict = Depends(require_admin)):
    try:
        res = (supabase.table("class_representatives")
               .select("id,name,email,branch,sem,created_at").order("name").execute())
        return res.data or []
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/crs")
def create_cr(body: CRIn, _: dict = Depends(require_admin)):
    _validate_cr(body)
    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required.")
    check_password_rules(body.password)
    email = body.email.strip().lower()

    if supabase.table("class_representatives").select("id").eq("email", email).execute().data:
        raise HTTPException(status_code=409, detail="A CR with this email already exists.")
    try:
        res = supabase.table("class_representatives").insert({
            "name": body.name.strip(), "email": email,
            "password_hash": hash_password(body.password),
            "branch": body.branch.strip(), "sem": body.sem
        }).execute()
        return {"message": "CR registered successfully", "id": res.data[0]["id"]}
    except Exception as e:
        if is_unique_violation(e):
            raise HTTPException(status_code=409, detail="A CR with this email already exists.")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/admin/crs/{cr_id}")
def update_cr(cr_id: int, body: CRIn, _: dict = Depends(require_admin)):
    _validate_cr(body)
    email = body.email.strip().lower()

    if not supabase.table("class_representatives").select("id").eq("id", cr_id).execute().data:
        raise HTTPException(status_code=404, detail="CR not found.")
    clash = supabase.table("class_representatives").select("id").eq("email", email).neq("id", cr_id).execute().data
    if clash:
        raise HTTPException(status_code=409, detail="Another CR already uses this email.")

    payload = {"name": body.name.strip(), "email": email, "branch": body.branch.strip(), "sem": body.sem}
    if body.password:
        check_password_rules(body.password)
        payload["password_hash"] = hash_password(body.password)
    try:
        supabase.table("class_representatives").update(payload).eq("id", cr_id).execute()
        return {"message": "CR updated successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/admin/crs/{cr_id}")
def delete_cr(cr_id: int, _: dict = Depends(require_admin)):
    try:
        supabase.table("class_representatives").delete().eq("id", cr_id).execute()
        return {"message": "CR deleted"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 🟢 NOTICE BOARD CRUD ENDPOINTS  (write access is now admin-only)
# ==========================================
# Notices are stored in their own "notices" table (see schema.sql).
# Attached PDFs (e.g. exam timetables) reuse the existing "notes" storage
# bucket, but are kept under a dedicated "notices/" folder so they don't
# mix with subject material.

@app.post("/notices")
async def create_notice(
    title: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    _: dict = Depends(require_admin)
):
    try:
        final_url = None

        if file:
            clean_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_").strip()
            file_bytes = await file.read()
            storage_path = f"notices/{clean_name}"

            print(f"📌 Uploading notice PDF to path: {storage_path}")

            supabase.storage.from_("notes").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            final_url = supabase.storage.from_("notes").get_public_url(storage_path)

        db_res = supabase.table("notices").insert({
            "title": title,
            "content": content,
            "pdf_url": final_url
        }).execute()

        print("✅ Notice Insert Success:", db_res.data)
        return {"message": "Notice created successfully", "data": db_res.data}

    except Exception as e:
        print("\n❌ --- NOTICE CREATE ERROR TRACEBACK ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/notices-all")
def get_all_notices():
    try:
        response = supabase.table("notices").select("*").order("created_at", desc=True).execute()
        print(f"📥 Fetched {len(response.data)} notices from database.")
        return response.data
    except Exception as e:
        print("\n❌ --- NOTICE FETCH ERROR TRACEBACK ---")
        traceback.print_exc()
        return []


@app.put("/notices/{notice_id}")
async def update_notice(
    notice_id: int,
    title: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    _: dict = Depends(require_admin)
):
    try:
        update_payload = {
            "title": title,
            "content": content,
        }

        # Only touch pdf_url if the admin uploaded a replacement file,
        # so existing attachments aren't wiped out on a text-only edit.
        if file:
            clean_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_").strip()
            file_bytes = await file.read()
            storage_path = f"notices/{clean_name}"

            supabase.storage.from_("notes").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            update_payload["pdf_url"] = supabase.storage.from_("notes").get_public_url(storage_path)

        supabase.table("notices").update(update_payload).eq("id", notice_id).execute()
        return {"message": "Notice updated successfully"}

    except Exception as e:
        print("\n❌ --- NOTICE UPDATE ERROR TRACEBACK ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/notices/{notice_id}")
def delete_notice(notice_id: int, _: dict = Depends(require_admin)):
    try:
        supabase.table("notices").delete().eq("id", notice_id).execute()
        return {"message": "Notice deleted successfully"}
    except Exception as e:
        print("\n❌ --- NOTICE DELETE ERROR TRACEBACK ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))