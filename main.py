#
# Copyright (C) 2026 @dabeecao
#
# This file is part of TeleCloud project, lead developer: @dabeecao
# For support, please visit the TTJB support group: https://t.me/thuthuatjb_sp
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

import os
import hmac
import hashlib
import uuid
import tempfile
import mimetypes
import subprocess
from urllib.parse import quote
from contextlib import asynccontextmanager
from typing import Optional, List
from PIL import Image

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form, status, Query
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyCookie
from fastapi.staticfiles import StaticFiles
from fastapi import BackgroundTasks
from pydantic import BaseModel
import aiosqlite
from hydrogram import Client
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", 2048))
SECRET_KEY = os.getenv("ADMIN_PASSWORD", "telecloud_secret").encode()

log_group_env = os.getenv("LOG_GROUP_ID")
try:
    LOG_GROUP_ID = int(log_group_env)
except ValueError:
    LOG_GROUP_ID = log_group_env

if SESSION_STRING:
    tg_app = Client("my_cloud_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
    startup_msg = "🚀 Khởi động với User Session (Userbot Mode)"
elif BOT_TOKEN:
    tg_app = Client("my_cloud_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    startup_msg = "🤖 Khởi động với Bot Token (Bot Mode)"
else:
    raise ValueError("Bạn phải cấu hình SESSION_STRING hoặc BOT_TOKEN trong file .env")
    
def generate_direct_token(share_token: str) -> str:
    signature = hmac.new(SECRET_KEY, share_token.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{share_token}_{signature}"

def verify_direct_token(direct_token: str) -> str | None:
    try:
        share_token, signature = direct_token.split("_")
        expected_sig = hmac.new(SECRET_KEY, share_token.encode(), hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(signature, expected_sig):
            return share_token
    except Exception:
        pass
    return None
    
async def process_complete_upload(file_path: str, filename: str, path: str, mime_type: str, task_id: str):
    try:
        upload_tasks[task_id] = {"status": "telegram", "percent": 0}
        file_size = os.path.getsize(file_path)
        
        local_thumb = create_local_thumbnail(file_path, mime_type)
        
        msg = await tg_app.send_document(
            LOG_GROUP_ID, 
            document=file_path, 
            file_name=filename, 
            thumb=local_thumb,
            caption=f"Path: {path}\nFilename: {filename}",
            progress=upload_progress_tracker,
            progress_args=(task_id,)
        )
        
        async with aiosqlite.connect("database.db") as db:
            await db.execute(
                "INSERT INTO files (message_id, filename, path, size, mime_type, is_folder, thumb_path) VALUES (?, ?, ?, ?, ?, 0, ?)",
                (msg.id, filename, path, file_size, mime_type, local_thumb)
            )
            await db.commit()
            
    except Exception as e:
        print(f"Lỗi upload Telegram: {e}")
        upload_tasks[task_id] = {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            
        if task_id in upload_tasks and upload_tasks[task_id].get("status") != "error":
            upload_tasks[task_id]["status"] = "done"
            upload_tasks[task_id]["percent"] = 100


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(startup_msg)
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files (
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                filename TEXT NOT NULL,
                path TEXT DEFAULT '/',
                size INTEGER DEFAULT 0,
                mime_type TEXT,
                share_token TEXT UNIQUE,
                is_folder BOOLEAN DEFAULT 0
            )
        """)
        try:
            await db.execute("ALTER TABLE files ADD COLUMN thumb_path TEXT")
        except Exception:
            pass
            
        await db.commit()
    
    await tg_app.start()
    yield
    await tg_app.stop()

app = FastAPI(lifespan=lifespan)

THUMBS_DIR = "static/thumbs"
os.makedirs(THUMBS_DIR, exist_ok=True)

def create_local_thumbnail(source_path: str, mime_type: str) -> str | None:
    """Tạo thumbnail local cho ảnh, video và nhạc, trả về đường dẫn file thumb"""
    
    actual_mime = mime_type
    if not actual_mime or actual_mime == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(source_path)
        actual_mime = guessed or ""

    thumb_name = f"{uuid.uuid4().hex}.jpg"
    thumb_path = os.path.join(THUMBS_DIR, thumb_name)
    
    try:
        if actual_mime.startswith('image/'):
            with Image.open(source_path) as img:
                img.thumbnail((320, 320))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(thumb_path, "JPEG", quality=85)
            return thumb_path
            
        elif actual_mime.startswith('video/'):
            cmd = [
                'ffmpeg', '-y', '-i', source_path,
                '-ss', '00:00:00.000', '-vframes', '1',
                '-vf', 'scale=320:-1', thumb_path
            ]
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                print(f"\n[!] LỖI FFMPEG KHI TẠO THUMB VIDEO: {process.stderr}\n")
                return None
                
            if os.path.exists(thumb_path):
                return thumb_path
                
        elif actual_mime.startswith('audio/'):
            cmd = [
                'ffmpeg', '-y', '-i', source_path,
                '-an',
                '-vframes', '1',
                '-vf', 'scale=320:-1',
                thumb_path
            ]
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode == 0 and os.path.exists(thumb_path):
                return thumb_path
            else:
                return None
                
    except Exception as e:
        print(f"\n[!] LỖI EXCEPTION TẠO THUMB: {e}\n")
        
    return None

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
cookie_scheme = APIKeyCookie(name="session_token", auto_error=False)

async def get_db():
    async with aiosqlite.connect("database.db") as db:
        db.row_factory = aiosqlite.Row
        yield db

def check_auth(token: Optional[str] = Depends(cookie_scheme)):
    if token != ADMIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return token

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, token: Optional[str] = Depends(cookie_scheme)):
    return templates.TemplateResponse(request=request, name="index.html", context={
        "logged_in": token == ADMIN_PASSWORD,
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB
    })

@app.post("/login")
async def login(response: Response, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response.set_cookie(key="session_token", value=password, httponly=True)
        return {"status": "success"}
    raise HTTPException(status_code=401)

@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session_token")
    return {"status": "success"}

upload_tasks = {}

async def upload_progress_tracker(current, total, task_id):
    percent = int((current / total) * 100)
    upload_tasks[task_id] = {"status": "telegram", "percent": percent}

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str, _=Depends(check_auth)):
    return upload_tasks.get(task_id, {"status": "pending", "percent": 0})

@app.get("/api/files")
async def list_files(path: str = "/", _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM files WHERE path = ? ORDER BY is_folder DESC, id DESC", (path,)) as cursor:
        files = await cursor.fetchall()
        
    result = []
    for row in files:
        file_dict = dict(row)
        if file_dict.get("share_token"):
            file_dict["direct_token"] = generate_direct_token(file_dict["share_token"])
        
        file_dict["has_thumb"] = True if file_dict.get("thumb_path") and os.path.exists(file_dict["thumb_path"]) else False
        result.append(file_dict)
        
    return {"files": result}

@app.post("/api/folders")
async def create_folder(name: str = Form(...), path: str = Form("/"), _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("INSERT INTO files (filename, path, is_folder) VALUES (?, ?, 1)", (name, path))
    await db.commit()
    return {"status": "success"}

@app.post("/api/upload")
async def upload_file_chunk(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    filename: str = Form(...),
    path: str = Form("/"), 
    task_id: str = Form(...), 
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    _=Depends(check_auth)
):
    temp_dir = os.path.join(tempfile.gettempdir(), "telecloud_chunks")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file_path = os.path.join(temp_dir, f"{task_id}_{filename}")

    with open(temp_file_path, "ab") as f:
        f.write(await file.read())

    server_percent = int(((chunk_index + 1) / total_chunks) * 100)
    upload_tasks[task_id] = {"status": "uploading_to_server", "percent": server_percent}

    if chunk_index == total_chunks - 1:
        background_tasks.add_task(
            process_complete_upload,
            file_path=temp_file_path,
            filename=filename,
            path=path,
            mime_type=file.content_type or "application/octet-stream",
            task_id=task_id
        )
        return {"status": "processing_telegram", "message": "Đã nhận đủ, đang đẩy lên Telegram"}

    return {"status": "chunk_received", "chunk": chunk_index}

class PasteRequest(BaseModel):
    action: str 
    item_ids: List[int]
    destination: str

@app.post("/api/actions/paste")
async def paste_items(req: PasteRequest, _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    for item_id in req.item_ids:
        async with db.execute("SELECT * FROM files WHERE id = ?", (item_id,)) as cursor:
            item = await cursor.fetchone()
        if not item: continue

        if item["is_folder"]:
            old_prefix = f"{item['path']}/{item['filename']}" if item['path'] != "/" else f"/{item['filename']}"
            
            if req.destination == old_prefix or req.destination.startswith(old_prefix + "/"):
                continue 

        if req.action == "move":
            await db.execute("UPDATE files SET path = ? WHERE id = ?", (req.destination, item_id))
            
            if item["is_folder"]:
                new_prefix = f"{req.destination}/{item['filename']}" if req.destination != "/" else f"/{item['filename']}"
                await db.execute(
                    "UPDATE files SET path = ? || SUBSTR(path, ?) WHERE path = ? OR path LIKE ?",
                    (new_prefix, len(old_prefix) + 1, old_prefix, old_prefix + "/%")
                )

        elif req.action == "copy":
            if item["is_folder"]:
                await db.execute(
                    "INSERT INTO files (filename, path, is_folder) VALUES (?, ?, 1)",
                    (item["filename"], req.destination)
                )
                
                new_prefix = f"{req.destination}/{item['filename']}" if req.destination != "/" else f"/{item['filename']}"
                
                await db.execute(
                    """
                    INSERT INTO files (message_id, filename, path, size, mime_type, is_folder, share_token)
                    SELECT message_id, filename, ? || SUBSTR(path, ?), size, mime_type, is_folder, NULL
                    FROM files 
                    WHERE path = ? OR path LIKE ?
                    """,
                    (new_prefix, len(old_prefix) + 1, old_prefix, old_prefix + "/%")
                )
            else:
                await db.execute(
                    "INSERT INTO files (message_id, filename, path, size, mime_type, is_folder) VALUES (?, ?, ?, ?, ?, 0)",
                    (item["message_id"], item["filename"], req.destination, item["size"], item["mime_type"])
                )
    
    await db.commit()
    return {"status": "success"}

@app.delete("/api/files/{file_id}")
async def delete_file(file_id: int, _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM files WHERE id = ?", (file_id,)) as cursor:
        row = await cursor.fetchone()
        if not row: raise HTTPException(status_code=404)
    
    row_dict = dict(row)
    
    if row_dict["is_folder"]:
        folder_full_path = f"{row_dict['path']}/{row_dict['filename']}" if row_dict['path'] != "/" else f"/{row_dict['filename']}"
        
        async with db.execute(
            "SELECT message_id, thumb_path FROM files WHERE (path = ? OR path LIKE ?) AND message_id IS NOT NULL", 
            (folder_full_path, folder_full_path + "/%")
        ) as cursor:
            children = await cursor.fetchall()
        
        target_msg_ids = list(set([child["message_id"] for child in children if child["message_id"]]))
        
        await db.execute("DELETE FROM files WHERE path = ? OR path LIKE ?", (folder_full_path, folder_full_path + "/%"))
        await db.execute("DELETE FROM files WHERE id = ?", (file_id,))
        
        for child in children:
            child_dict = dict(child)
            if child_dict.get("thumb_path") and os.path.exists(child_dict["thumb_path"]):
                try: os.remove(child_dict["thumb_path"])
                except Exception: pass
        
        msg_ids_to_delete_tele = []
        for msg_id in target_msg_ids:
            async with db.execute("SELECT COUNT(*) FROM files WHERE message_id = ?", (msg_id,)) as cursor:
                c = await cursor.fetchone()
                if c[0] == 0:
                    msg_ids_to_delete_tele.append(msg_id)
        
        if msg_ids_to_delete_tele:
            try:
                await tg_app.delete_messages(LOG_GROUP_ID, msg_ids_to_delete_tele)
            except Exception as e:
                print(f"Lỗi khi xóa file folder trên Telegram: {e}")
                
    else:
        if row_dict.get("thumb_path") and os.path.exists(row_dict["thumb_path"]):
            try: os.remove(row_dict["thumb_path"])
            except Exception: pass

        if row_dict.get("message_id"):
            async with db.execute("SELECT COUNT(*) FROM files WHERE message_id = ?", (row_dict["message_id"],)) as cursor:
                count = await cursor.fetchone()
            
            if count[0] <= 1:
                try:
                    await tg_app.delete_messages(LOG_GROUP_ID, row_dict["message_id"])
                except Exception as e:
                    print(f"Lỗi khi xóa file đơn trên Telegram: {e}")
        
        await db.execute("DELETE FROM files WHERE id = ?", (file_id,))

    await db.commit()
    return {"status": "deleted"}

@app.put("/api/files/{file_id}/rename")
async def rename_file(file_id: int, new_name: str = Form(...), _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT filename, path, is_folder FROM files WHERE id = ?", (file_id,)) as cursor:
        row = await cursor.fetchone()
        if not row: raise HTTPException(status_code=404)
        
        old_name = row["filename"]
        base_path = row["path"]
        
        if not row["is_folder"]:
            old_ext = os.path.splitext(old_name)[1]
            new_ext = os.path.splitext(new_name)[1]
            if old_ext and not new_ext:
                new_name = new_name + old_ext
        else:
            old_folder_path = f"{base_path}/{old_name}" if base_path != "/" else f"/{old_name}"
            new_folder_path = f"{base_path}/{new_name}" if base_path != "/" else f"/{new_name}"
            
            await db.execute(
                "UPDATE files SET path = ? || SUBSTR(path, ?) WHERE path = ? OR path LIKE ?",
                (new_folder_path, len(old_folder_path) + 1, old_folder_path, old_folder_path + "/%")
            )

    await db.execute("UPDATE files SET filename = ? WHERE id = ?", (new_name, file_id))
    await db.commit()
    return {"status": "renamed"}

@app.post("/api/files/{file_id}/share")
async def generate_share_link(file_id: int, _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    token = str(uuid.uuid4())
    await db.execute("UPDATE files SET share_token = ? WHERE id = ?", (token, file_id))
    await db.commit()
    return {
        "share_token": token, 
        "direct_token": generate_direct_token(token)
    }

@app.delete("/api/files/{file_id}/share")
async def revoke_share_link(file_id: int, _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("UPDATE files SET share_token = NULL WHERE id = ?", (file_id,))
    await db.commit()
    return {"status": "revoked"}

async def stream_telegram_file(message_id: int):
    msg = await tg_app.get_messages(LOG_GROUP_ID, message_id)
    async for chunk in tg_app.stream_media(msg):
        yield chunk

@app.get("/download/{file_id}")
async def download_file(file_id: int, _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT message_id, filename, mime_type FROM files WHERE id = ?", (file_id,)) as cursor:
        row = await cursor.fetchone()
        if not row or not row["message_id"]: raise HTTPException(status_code=404)
        
    encoded_name = quote(row["filename"])
    headers = { "Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}" }
    
    response = StreamingResponse(
        stream_telegram_file(row["message_id"]), 
        media_type=row["mime_type"], 
        headers=headers
    )
    
    response.set_cookie(key="dl_started", value="1", max_age=15, path="/")
    
    return response
    
@app.get("/dl/{direct_token}")
async def secure_direct_download(direct_token: str, db: aiosqlite.Connection = Depends(get_db)):
    share_token = verify_direct_token(direct_token)
    if not share_token:
        raise HTTPException(status_code=403, detail="Link tải trực tiếp không hợp lệ hoặc đã bị giả mạo.")
        
    async with db.execute("SELECT message_id, filename, mime_type FROM files WHERE share_token = ?", (share_token,)) as cursor:
        row = await cursor.fetchone()
        if not row or not row["message_id"]: 
            raise HTTPException(status_code=404, detail="File không tồn tại hoặc link đã bị thu hồi.")
            
    encoded_name = quote(row["filename"])
    headers = { "Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}" }
    
    return StreamingResponse(
        stream_telegram_file(row["message_id"]), 
        media_type=row["mime_type"], 
        headers=headers
    )

@app.get("/s/{token}")
async def public_download(request: Request, token: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT message_id, filename, mime_type, size, created_at, thumb_path FROM files WHERE share_token = ?", (token,)) as cursor:
        row = await cursor.fetchone()
        if not row: 
            return templates.TemplateResponse(
                request=request, name="error.html", 
                context={"error_message": "File không tồn tại hoặc link đã bị thu hồi."},
                status_code=404
            )
            
    has_thumb = True if row["thumb_path"] and os.path.exists(row["thumb_path"]) else False
    
    return templates.TemplateResponse(
        request=request, 
        name="share.html", 
        context={
            "filename": row["filename"],
            "size": row["size"],
            "mime_type": row["mime_type"],
            "created_at": row["created_at"],
            "token": token,
            "has_thumb": has_thumb
        }
    )
    
@app.get("/s/{token}/stream")
async def stream_public_media(request: Request, token: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT message_id, filename, mime_type, size FROM files WHERE share_token = ?", (token,)) as cursor:
        row = await cursor.fetchone()
        if not row or not row["message_id"]: 
            raise HTTPException(status_code=404)
            
    file_size = row["size"]
    message_id = row["message_id"]
    encoded_name = quote(row["filename"])
    
    actual_mime_type = row["mime_type"]
    if not actual_mime_type or actual_mime_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(row["filename"])
        actual_mime_type = guessed_type or "application/octet-stream"

    range_header = request.headers.get("Range")
    
    if range_header:
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
        
        if end >= file_size:
            end = file_size - 1
            
        chunk_size = (end - start) + 1

        async def ranged_stream_generator():
            msg = await tg_app.get_messages(LOG_GROUP_ID, message_id)
            async for chunk in tg_app.stream_media(msg, offset=start, limit=chunk_size):
                yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Disposition": f"inline; filename*=utf-8''{encoded_name}",
        }
        return StreamingResponse(
            ranged_stream_generator(), 
            status_code=206, 
            media_type=actual_mime_type, 
            headers=headers
        )
    else:
        async def full_stream_generator():
            msg = await tg_app.get_messages(LOG_GROUP_ID, message_id)
            async for chunk in tg_app.stream_media(msg):
                yield chunk

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f"inline; filename*=utf-8''{encoded_name}",
        }
        return StreamingResponse(
            full_stream_generator(), 
            status_code=200, 
            media_type=actual_mime_type, 
            headers=headers
        )
    
@app.get("/api/files/{file_id}/thumb")
async def get_internal_thumb(file_id: int, _=Depends(check_auth), db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT thumb_path FROM files WHERE id = ?", (file_id,)) as cursor:
        row = await cursor.fetchone()
        if row and row["thumb_path"] and os.path.exists(row["thumb_path"]):
            return FileResponse(row["thumb_path"])
    raise HTTPException(status_code=404)

@app.get("/s/{token}/thumb")
async def stream_public_thumbnail(token: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT thumb_path FROM files WHERE share_token = ?", (token,)) as cursor:
        row = await cursor.fetchone()
        if row and row["thumb_path"] and os.path.exists(row["thumb_path"]):
            return FileResponse(row["thumb_path"])
            
    raise HTTPException(status_code=404, detail="Không có thumbnail")
    
@app.post("/s/{token}/dl")
async def process_public_download(token: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT message_id, filename, mime_type FROM files WHERE share_token = ?", (token,)) as cursor:
        row = await cursor.fetchone()
        if not row or not row["message_id"]: 
            raise HTTPException(status_code=404, detail="File không tồn tại hoặc link đã bị thu hồi.")
            
    encoded_name = quote(row["filename"])
    headers = { "Content-Disposition": f"attachment; filename*=utf-8''{encoded_name}" }
    
    response = StreamingResponse(
        stream_telegram_file(row["message_id"]), 
        media_type=row["mime_type"], 
        headers=headers
    )
    
    response.set_cookie(key="dl_started", value="1", max_age=15, path="/")
    
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8091)) 
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
