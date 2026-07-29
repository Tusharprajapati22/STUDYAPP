


# testing checkig coe==============================================================

import os
import traceback
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, Form, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    youtube_url: Optional[str] = Form(None)
):
    try:
        final_url = pdf_url

        # 🟢 YAHAN LAGANA HAI: Subject ko uppercase me convert karne ke liye
        subject = subject.upper()

        # File Storage Upload logic
        if file:
            clean_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_").strip()
            file_bytes = await file.read()
            storage_path = f"{year}/{branch}/{sem}/{subject}/{clean_name}"
            
            print(f"📦 Uploading file to path: {storage_path}")

            # Added "upsert": "true" to allow overwriting if same file uploaded again
            supabase.storage.from_("notes").upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
            final_url = supabase.storage.from_("notes").get_public_url(storage_path)

        print(f"💾 Inserting record into database with URL: {final_url}")

        # ==========================================
        # 🟢 DUPLICATE CHECK & HANDLING LOGIC START
        # ==========================================
        # Pehle check karenge ki kya same year, branch, sem, aur subject ka record pehle se hai
        existing_check = supabase.table("notes").select("id").eq("year", year).eq("branch", branch).eq("sem", sem).eq("subject", subject).execute()

        if existing_check.data and len(existing_check.data) > 0:
            print(f"ℹ️ Same subject '{subject}' already exists. Inserting/Appending under the same category.")
        # ==========================================
        # 🟢 DUPLICATE CHECK & HANDLING LOGIC END
        # ==========================================

        # Database Insert Logic (Aapki requirement ke mutabiq ye same subject ke liye naya entry insert karega taki ek hi subject me multiple notes/units show ho sakein)
        db_res = supabase.table("notes").insert({
            "year": year,
            "branch": branch,
            "sem": sem,
            "subject": subject,
            "unit": unit,
            "type": type,
            "title": title,
            "pdf_url": final_url
        }).execute()

        print("✅ Insert Success:", db_res.data)
        return {"message": "Uploaded successfully"}

    except Exception as e:
        print("\n❌ --- UPLOAD ERROR TRACEBACK ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/notes-all")
def get_all_notes():
    try:
        response = supabase.table("notes").select("*").execute()
        print(f"📥 Fetched {len(response.data)} notes from database.")
        return response.data
    except Exception as e:
        print("\n❌ --- FETCH ERROR TRACEBACK ---")
        traceback.print_exc()
        return []

@app.delete("/delete/{note_id}")
def delete_note(note_id: int):
    try:
        supabase.table("notes").delete().eq("id", note_id).execute()
        return {"message": "Deleted successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/update/{note_id}")
async def update_note(
    note_id: int,
    title: str = Form(...),
    subject: str = Form(...),
    year: str = Form(...),
    branch: str = Form(...),
    sem: str = Form(...)
):
    try:
        supabase.table("notes").update({
            "title": title,
            "subject": subject,
            "year": year,
            "branch": branch,
            "sem": sem
        }).eq("id", note_id).execute()
        return {"message": "Updated successfully"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


#===================================

# # testing checkig coe==============================================================

# import os
# import traceback
# from pathlib import Path
# from typing import Optional
# from dotenv import load_dotenv
# from fastapi import FastAPI, UploadFile, Form, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from supabase import create_client
# from pydantic import BaseModel # 🟢 ADDED: Required for parsing JSON body

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
#     youtube_url: Optional[str] = Form(None)
# ):
#     try:
#         final_url = pdf_url

#         # 🟢 YAHAN LAGANA HAI: Subject ko uppercase me convert karne ke liye
#         subject = subject.upper()

#         # File Storage Upload logic
#         if file:
#             clean_name = "".join(c for c in file.filename if c.isalnum() or c in ".-_").strip()
#             file_bytes = await file.read()
#             storage_path = f"{year}/{branch}/{sem}/{subject}/{clean_name}"
            
#             print(f"📦 Uploading file to path: {storage_path}")

#             # Added "upsert": "true" to allow overwriting if same file uploaded again
#             supabase.storage.from_("notes").upload(
#                 path=storage_path,
#                 file=file_bytes,
#                 file_options={"content-type": "application/pdf", "upsert": "true"}
#             )
#             final_url = supabase.storage.from_("notes").get_public_url(storage_path)

#         print(f"💾 Inserting record into database with URL: {final_url}")

#         # ==========================================
#         # 🟢 DUPLICATE CHECK & HANDLING LOGIC START
#         # ==========================================
#         # Pehle check karenge ki kya same year, branch, sem, aur subject ka record pehle se hai
#         existing_check = supabase.table("notes").select("id").eq("year", year).eq("branch", branch).eq("sem", sem).eq("subject", subject).execute()

#         if existing_check.data and len(existing_check.data) > 0:
#             print(f"ℹ️ Same subject '{subject}' already exists. Inserting/Appending under the same category.")
#         # ==========================================
#         # 🟢 DUPLICATE CHECK & HANDLING LOGIC END
#         # ==========================================

#         # Database Insert Logic (Aapki requirement ke mutabiq ye same subject ke liye naya entry insert karega taki ek hi subject me multiple notes/units show ho sakein)
#         db_res = supabase.table("notes").insert({
#             "year": year,
#             "branch": branch,
#             "sem": sem,
#             "subject": subject,
#             "unit": unit,
#             "type": type,
#             "title": title,
#             "pdf_url": final_url
#         }).execute()

#         print("✅ Insert Success:", db_res.data)
#         return {"message": "Uploaded successfully"}

#     except Exception as e:
#         print("\n❌ --- UPLOAD ERROR TRACEBACK ---")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/notes-all")
# def get_all_notes():
#     try:
#         response = supabase.table("notes").select("*").execute()
#         print(f"📥 Fetched {len(response.data)} notes from database.")
#         return response.data
#     except Exception as e:
#         print("\n❌ --- FETCH ERROR TRACEBACK ---")
#         traceback.print_exc()
#         return []

# @app.delete("/delete/{note_id}")
# def delete_note(note_id: int):
#     try:
#         supabase.table("notes").delete().eq("id", note_id).execute()
#         return {"message": "Deleted successfully"}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

# @app.put("/update/{note_id}")
# async def update_note(
#     note_id: int,
#     title: str = Form(...),
#     subject: str = Form(...),
#     year: str = Form(...),
#     branch: str = Form(...),
#     sem: str = Form(...)
# ):
#     try:
#         supabase.table("notes").update({
#             "title": title,
#             "subject": subject,
#             "year": year,
#             "branch": branch,
#             "sem": sem
#         }).eq("id", note_id).execute()
#         return {"message": "Updated successfully"}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

# # ==========================================
# # 🟢 NEW ADMIN LOGIN LOGIC START
# # ==========================================
# class LoginRequest(BaseModel):
#     username: str
#     password: str

# @app.post("/admin/login")
# def admin_login(creds: LoginRequest):
#     admin_user = os.getenv("ADMIN_USERNAME")
#     admin_pass = os.getenv("ADMIN_PASSWORD")
    
#     # Verify both aren't None in .env and match the request
#     if admin_user and admin_pass and creds.username == admin_user and creds.password == admin_pass:
#         return {"success": True}
        
#     raise HTTPException(status_code=401, detail="Invalid credentials")