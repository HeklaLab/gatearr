"""Demo-only Emby contract simulator. Never run this service in production."""
import os
import sqlite3
import json
import uuid
from copy import deepcopy
from fastapi import FastAPI, Request, HTTPException
from .security import hasher, verify

app = FastAPI()
DB = os.getenv("MOCK_DB", "/data/mock.db")
COPY_OPTIONS = [{"Id": "Policy", "Name": "Library access and permissions"}, {"Id": "Configuration", "Name": "User configuration"}, {"Id": "DisplayPreferences", "Name": "Home screen and display preferences"}]
LIBRARIES = [{"ItemId":"1001","Guid":"11111111111111111111111111111111","Name":"Movies"}, {"ItemId":"1002","Guid":"22222222222222222222222222222222","Name":"Films"}, {"ItemId":"1003","Guid":"33333333333333333333333333333333","Name":"TV Shows"}]
DEFAULT_PROFILE = {"Policy": {"IsAdministrator": False, "EnableAllFolders": False, "EnabledFolders": ["11111111111111111111111111111111","22222222222222222222222222222222"]}, "Configuration": {"OrderedViews": ["films", "movies"], "HidePlayedInLatest": True}, "DisplayPreferences": {"homeSections": ["myMedia", "continueWatching", "latestMedia"]}}
API_KEY = os.getenv("MOCK_API_KEY", "demo-emby-key")
def connection():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT UNIQUE, password TEXT, disabled INTEGER DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, body TEXT)")
    if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        db.execute("INSERT INTO users VALUES (?, ?, ?, 0)", ("demo-user-1", "demo", hasher.hash("DemoPassword123!")))
        db.execute("INSERT INTO users VALUES (?, ?, ?, 1)", ("demo-user-disabled", "disabled", hasher.hash("DemoPassword123!")))
        db.commit()
    if not db.execute("SELECT 1 FROM users WHERE id=?",("demo-admin-1",)).fetchone():
        db.execute("INSERT INTO users VALUES (?, ?, ?, 0)",("demo-admin-1","portal-admin",hasher.hash("AdminPassword123!")))
        db.commit()
    return db

def profile(user_id):
    with connection() as db:
        row = db.execute("SELECT body FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    data=json.loads(row[0]) if row else deepcopy(DEFAULT_PROFILE)
    aliases={'movies':'11111111111111111111111111111111','films':'22222222222222222222222222222222','series':'33333333333333333333333333333333'}
    data['Policy']['EnabledFolders']=[aliases.get(value,value) for value in data['Policy'].get('EnabledFolders',[])]
    return data

def save_profile(user_id, data):
    with connection() as db:
        db.execute("INSERT OR REPLACE INTO profiles VALUES (?, ?)", (user_id, json.dumps(data)))
        db.commit()

def dto(row):
    data = profile(row["id"])
    data["Policy"]["IsDisabled"] = bool(row["disabled"])
    return {"Id": row["id"], "Name": row["name"], **data}

def authorize(request, user_id=None):
    token = request.headers.get("X-Emby-Token")
    if token != API_KEY and (not user_id or token != "demo-session-" + user_id):
        raise HTTPException(403)

@app.get("/healthz")
def health():
    with connection() as db:
        db.execute("SELECT 1")
    return {"status": "ok"}

@app.get('/emby/System/Info')
def system_info(request:Request):
    authorize(request)
    return {'Id':'demo-server','ServerName':'Emby demo','ProductName':'Emby Server','Version':'demo'}

@app.post("/emby/Users/AuthenticateByName")
async def login(request: Request):
    data = await request.json()
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE name=?", (data.get("Username"),)).fetchone()
    if not row or row["disabled"] or not verify(row["password"], data.get("Pw", "")):
        raise HTTPException(401)
    return {"User": dto(row), "AccessToken": "demo-session-" + row["id"]}

@app.get("/emby/Users/Query")
def users(request: Request, StartIndex: int = 0, Limit: int = 200):
    authorize(request)
    with connection() as db:
        rows = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return {"Items": [dto(row) for row in rows[StartIndex:StartIndex+Limit]], "TotalRecordCount": len(rows)}

@app.get("/emby/Users/CopyDataOptions")
def copy_options(request: Request):
    authorize(request)
    return {"DataOptions": COPY_OPTIONS}

@app.get("/emby/Library/VirtualFolders/Query")
def libraries(request: Request, StartIndex: int = 0, Limit: int = 200):
    authorize(request)
    return {"Items": LIBRARIES[StartIndex:StartIndex+Limit], "TotalRecordCount": len(LIBRARIES)}

@app.post("/emby/Users/New")
async def create_user(request: Request):
    authorize(request)
    data = await request.json()
    user_id = uuid.uuid4().hex
    source = profile(data["CopyFromUserId"])
    result = deepcopy(DEFAULT_PROFILE)
    for key in data.get("UserCopyOptions", []):
        if key in source:
            result[key] = deepcopy(source[key])
    with connection() as db:
        db.execute("INSERT INTO users VALUES (?, ?, ?, 0)", (user_id, data["Name"], hasher.hash(uuid.uuid4().hex)))
        db.commit()
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    save_profile(user_id, result)
    return dto(row)

@app.post("/emby/Users/{user_id}/Policy", status_code=204)
async def policy(request: Request, user_id: str):
    authorize(request)
    data = await request.json()
    result = profile(user_id)
    result["Policy"] = data
    save_profile(user_id, result)
    with connection() as db:
        db.execute("UPDATE users SET disabled=? WHERE id=?", (int(data.get("IsDisabled", False)), user_id))
        db.commit()

@app.post("/emby/Users/{user_id}", status_code=204)
async def rename(request: Request, user_id: str):
    authorize(request)
    data = await request.json()
    with connection() as db:
        try:
            db.execute("UPDATE users SET name=? WHERE id=?", (data["Name"], user_id))
            db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409)

@app.delete("/emby/Users/{user_id}", status_code=204)
def delete_user(request: Request, user_id: str):
    authorize(request)
    with connection() as db:
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
        db.commit()

@app.post("/emby/Users/{user_id}/CopyData", status_code=204)
async def copy_data(request: Request, user_id: str):
    authorize(request)
    body = await request.json()
    source = profile(user_id)
    for target in body.get("ToUserIds", []):
        data = profile(target)
        for key in body.get("CopyOptions", []):
            if key in source:
                data[key] = deepcopy(source[key])
        save_profile(target, data)

@app.get("/emby/Users/{user_id}")
def user(request: Request, user_id: str):
    authorize(request)
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    return dto(row)

@app.post("/emby/Users/{user_id}/Password", status_code=204)
async def password(request: Request, user_id: str):
    authorize(request, user_id)
    data = await request.json()
    if "NewPw" not in data or data.get("ResetPassword") is not False:
        raise HTTPException(400)
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or (row["disabled"] and request.headers.get("X-Emby-Token") != API_KEY):
            raise HTTPException(403)
        db.execute("UPDATE users SET password=? WHERE id=?", (hasher.hash(data["NewPw"]), user_id))
        db.commit()
