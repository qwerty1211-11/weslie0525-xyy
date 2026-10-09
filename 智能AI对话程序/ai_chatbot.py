"""
AI 语音对话 Agent · AGENT_VOICE11
=================================
启动：pip install flask && python AI语音对话Agent.py
访问：http://127.0.0.1:5011

真 AI + 真语音 + 真 Agent 工具：
  - 真调 LLM API（智谱GLM-4-Flash 永久免费，支持 DeepSeek/硅基流动等多平台）
  - 浏览器原生语音识别（Web Speech API，Chrome/Edge 可用，无需装库）
  - 浏览器原生语音合成（SpeechSynthesis 朗读 AI 回复）
  - Agent 工作流：LLM 自己决定调用哪个工具，工具真执行真返回
  - 6 个真实工具：
      get_time      真系统时间
      get_weather   真调 Open-Meteo + Geocoding API
      calc          真计算表达式
      save_note     真存到 SQLite
      query_notes   真查 SQLite
      search_wiki   真调维基百科 REST API

工作流：
  用户说话/输入 → 调 LLM → LLM 决定直接回复还是调工具
  → 如果调工具：后端真执行 → 结果作为新的 Observation 喂回 LLM
  → LLM 基于结果给最终回复 → 前端流式渲染 + 语音朗读

使用前：
  1. 选一个免费 LLM 平台注册（推荐智谱，永久免费）：
     - 智谱 GLM    https://open.bigmodel.cn        GLM-4-Flash 永久免费
     - 硅基流动     https://cloud.siliconflow.cn     9B 以下永久免费
     - DeepSeek    https://platform.deepseek.com   新用户送额度
  2. 修改下方 CURRENT_PROVIDER（默认 "智谱GLM"）+ 填入 LLM_API_KEY
  3. 启动后用 Chrome/Edge 浏览器访问，点麦克风说话或输入文字，AI 真实回复并朗读
"""
import os
import re
import json
import time
import sqlite3
import datetime
import urllib.request
import urllib.parse
from flask import Flask, request, jsonify, Response, stream_with_context, g

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_agent11.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool TEXT DEFAULT '',
            created_at TEXT DEFAULT(datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            tag TEXT DEFAULT '',
            created_at TEXT DEFAULT(datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()


init_db()

# ============ 支持的 LLM 平台 ============
PROVIDERS = {
    "智谱GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model":    "glm-4-flash",
        "register": "https://open.bigmodel.cn",
        "note":     "永久免费，无 token 上限，国内直连"
    },
    "硅基流动": {
        "base_url": "https://api.siliconflow.cn/v1/chat/completions",
        "model":    "Qwen/Qwen2.5-7B-Instruct",
        "register": "https://cloud.siliconflow.cn",
        "note":     "9B 以下永久免费，注册送 2000 万 token"
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "model":    "deepseek-chat",
        "register": "https://platform.deepseek.com",
        "note":     "推理强，新用户送额度"
    },
    "阿里百炼": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model":    "qwen-plus",
        "register": "https://dashscope.aliyun.com",
        "note":     "每模型 100 万 token/3 月"
    },
    "Kimi": {
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "model":    "moonshot-v1-8k",
        "register": "https://platform.moonshot.cn",
        "note":     "新用户送 500 万 token"
    },
}
CURRENT_PROVIDER = "智谱GLM"
LLM_API_KEY = "ec813646f4dc48ad901c45bb2c861cc7.MdNKt2mWxVKDHpo3"  # 在双引号内粘贴你的 API Key


# ============ LLM 调用（带 Function Calling） ============
TOOL_SCHEMAS = [
    {
        "name": "get_time",
        "description": "获取当前系统时间，包含日期、星期、时分秒。当用户问『现在几点』『今天几号』『星期几』时调用。",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "get_weather",
        "description": "查询指定城市的当前天气（温度、天气状况、湿度、风速）。当用户问『XX天气』『XX几度』时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市中文名，如 北京/上海/广州"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "calc",
        "description": "计算数学表达式。当用户问『3+5等于多少』『计算 12*8』时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式，如 3+5、12*8、100/4"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "save_note",
        "description": "把用户提到要记下来的内容保存到笔记本。当用户说『记一下』『帮我记住』时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要保存的笔记内容"},
                "tag":     {"type": "string", "description": "标签，可选，如 待办/想法/购物"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "query_notes",
        "description": "搜索之前保存的笔记。当用户说『我之前记的XX』『查一下笔记』时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "search_wiki",
        "description": "搜索维基百科获取知识。当用户问『XX是什么』『XX是谁』『介绍一下XX』时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要查询的概念/人物/事物名"}
            },
            "required": ["query"]
        }
    }
]

SYSTEM_PROMPT = """你是一个语音对话 Agent。用户用中文跟你对话（语音输入或文字输入）。

你可以通过调用工具来获取信息或执行操作：
- get_time：查当前时间
- get_weather：查城市天气
- calc：算数学题
- save_note：帮用户记笔记
- query_notes：搜索之前的笔记
- search_wiki：查维基百科

规则：
1. 简短口语化回答，像真人对话，不要长篇大论
2. 调用工具后，用工具返回的结果用自然语言回答用户
3. 不需要调工具时直接回复
4. 用户记笔记时，调用 save_note，然后告诉用户『已记下』
5. 用中文回答
"""


def _build_request(messages, tools=None, stream=False):
    if CURRENT_PROVIDER not in PROVIDERS:
        return None, "未识别的平台：" + CURRENT_PROVIDER
    p = PROVIDERS[CURRENT_PROVIDER]
    if not LLM_API_KEY:
        return None, "未配置 LLM_API_KEY"
    body = {
        "model": p["model"],
        "messages": messages,
        "temperature": 0.6,
        "tools": [{"type": "function", "function": t} for t in tools] if tools else None
    }
    if stream:
        body["stream"] = True
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        p["base_url"], data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + LLM_API_KEY,
            "User-Agent": "VoiceAgent/1.0"
        }
    )
    return req, None


def safe_json(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r'^```(?:json)?\s*', '', t)
        t = re.sub(r'\s*```$', '', t)
    try:
        return json.loads(t), None
    except Exception as e:
        m = re.search(r'\{[\s\S]*\}', t)
        if m:
            try:
                return json.loads(m.group(0)), None
            except Exception:
                pass
        return None, "JSON 解析失败：" + str(e)


def call_llm(messages, tools=None):
    """非流式调用，返回完整 response JSON"""
    req, err = _build_request(messages, tools=tools, stream=False)
    if err:
        return None, err
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        return None, CURRENT_PROVIDER + " HTTP " + str(e.code) + "：" + body[:300]
    except Exception as e:
        return None, CURRENT_PROVIDER + " 调用失败：" + str(e)


def call_llm_stream(messages):
    """流式调用，yield delta"""
    req, err = _build_request(messages, stream=True)
    if err:
        yield None, err
        return
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            buf = b""
            while True:
                chunk = r.read(1024)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line or not line.startswith(b"data:"):
                        continue
                    data_str = line[5:].strip().decode("utf-8", errors="ignore")
                    if data_str == "[DONE]":
                        return
                    try:
                        obj = json.loads(data_str)
                        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            yield delta, None
                    except Exception:
                        continue
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        yield None, CURRENT_PROVIDER + " HTTP " + str(e.code) + "：" + body[:300]
    except Exception as e:
        yield None, CURRENT_PROVIDER + " 流式失败：" + str(e)


# ============ 真实工具实现 ============
def tool_get_time(args):
    now = datetime.datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return "现在是 " + now.strftime("%Y年%m月%d日 ") + weekdays[now.weekday()] + " " + now.strftime("%H点%M分%S秒")


def tool_get_weather(args):
    city = (args or {}).get("city", "").strip()
    if not city:
        return "需要城市名"
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search?name=" + urllib.parse.quote(city) + "&count=1&language=zh"
        with urllib.request.urlopen(url, timeout=10) as r:
            geo = json.loads(r.read().decode("utf-8"))
        if not geo.get("results"):
            return "找不到城市：" + city
        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]
        url2 = "https://api.open-meteo.com/v1/forecast?latitude=" + str(lat) + "&longitude=" + str(lon) + "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        with urllib.request.urlopen(url2, timeout=10) as r:
            w = json.loads(r.read().decode("utf-8"))
        cur = w.get("current", {})
        code_map = {0: "晴", 1: "晴", 2: "多云", 3: "阴", 45: "雾", 51: "小雨", 53: "中雨", 55: "大雨", 61: "小雨", 63: "中雨", 65: "大雨", 71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 95: "雷雨"}
        code = cur.get("weather_code", 0)
        return "城市：" + city + " | 天气：" + code_map.get(code, "未知") + " | 温度：" + str(cur.get("temperature_2m", "?")) + "°C | 湿度：" + str(cur.get("relative_humidity_2m", "?")) + "% | 风速：" + str(cur.get("wind_speed_10m", "?")) + "km/h"
    except Exception as e:
        return "天气查询失败：" + str(e)


def tool_calc(args):
    expr = (args or {}).get("expression", "").strip()
    if not expr:
        return "需要计算表达式"
    if not re.match(r'^[0-9+\-*/().%\s]+$', expr):
        return "表达式含非法字符"
    try:
        return "计算结果：" + str(eval(expr, {"__builtins__": {}}, {}))
    except Exception as e:
        return "计算失败：" + str(e)


def tool_save_note(args):
    content = (args or {}).get("content", "").strip()
    tag = (args or {}).get("tag", "").strip()
    if not content:
        return "笔记内容为空"
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO notes(content,tag) VALUES(?,?)", (content, tag))
    conn.commit()
    conn.close()
    return "已保存笔记：" + content + (["（标签：" + tag + "）"] if tag else [])


def tool_query_notes(args):
    keyword = (args or {}).get("keyword", "").strip()
    conn = sqlite3.connect(DB_PATH)
    if keyword:
        rows = conn.execute("SELECT * FROM notes WHERE content LIKE ? OR tag LIKE ? ORDER BY id DESC LIMIT 10",
                            ("%" + keyword + "%", "%" + keyword + "%")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    if not rows:
        return "没找到相关笔记"
    return "找到 " + str(len(rows)) + " 条笔记：" + " | ".join([r[1] + ("[" + r[2] + "]" if r[2] else "") for r in rows])


def tool_search_wiki(args):
    query = (args or {}).get("query", "").strip()
    if not query:
        return "查询内容为空"
    try:
        url = "https://zh.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"User-Agent": "VoiceAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        extract = data.get("extract", "")
        if not extract:
            return "没找到「" + query + "」的相关信息"
        return extract[:500]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "维基没有「" + query + "」的词条"
        return "维基查询失败：HTTP " + str(e.code)
    except Exception as e:
        return "维基查询失败：" + str(e)


TOOL_FUNCS = {
    "get_time": tool_get_time,
    "get_weather": tool_get_weather,
    "calc": tool_calc,
    "save_note": tool_save_note,
    "query_notes": tool_query_notes,
    "search_wiki": tool_search_wiki,
}


# ============ Agent 主循环 ============
def run_agent(history, user_input):
    """Agent 主循环。SSE 流式输出事件。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    max_iter = 4
    for i in range(max_iter):
        resp, err = call_llm(messages, tools=TOOL_SCHEMAS)
        if err:
            yield {"type": "error", "msg": err}
            return
        msg = resp.get("choices", [{}])[0].get("message", {})

        # 1. 如果 LLM 决定调工具
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            # 把 assistant 这条带 tool_calls 的消息原样塞回 messages
            messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls
            })
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name")
                args_raw = fn.get("arguments", "{}")
                args, _ = safe_json(args_raw)
                if name in TOOL_FUNCS:
                    yield {"type": "tool_call", "name": name, "args": args or {}}
                    result = TOOL_FUNCS[name](args or {})
                    yield {"type": "tool_result", "name": name, "result": result}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "name": name,
                        "content": result
                    })
            # 继续下一轮让 LLM 综合结果
            continue

        # 2. LLM 直接给最终回复 → 流式再补一次让前端有打字机效果
        # 用 stream 重发一次 messages 让回复有打字机感
        stream_req_msgs = messages + []
        yield {"type": "stream_start"}
        for delta, ferr in call_llm_stream(stream_req_msgs):
            if ferr:
                yield {"type": "error", "msg": "流式输出失败：" + str(ferr)}
                return
            if delta:
                yield {"type": "delta", "chunk": delta}
        yield {"type": "final"}
        return

    yield {"type": "error", "msg": "Agent 超过最大循环次数"}


def sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


# ============ 路由 ============
@app.route("/api/status")
def api_status():
    p = PROVIDERS.get(CURRENT_PROVIDER, {})
    return jsonify({
        "configured": bool(LLM_API_KEY),
        "provider": CURRENT_PROVIDER,
        "model": p.get("model", "?"),
        "register": p.get("register", ""),
        "note": p.get("note", "")
    })


@app.route("/api/chats")
def list_chats():
    db = get_db()
    rows = db.execute("SELECT * FROM chats ORDER BY id ASC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/chat", methods=["POST"])
def add_chat():
    d = request.get_json()
    db = get_db()
    cur = db.execute("INSERT INTO chats(role,content,tool) VALUES(?,?,?)",
                     (d["role"], d["content"], d.get("tool", "")))
    db.commit()
    row = db.execute("SELECT * FROM chats WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row))


@app.route("/api/chats", methods=["DELETE"])
def clear_chats():
    db = get_db()
    db.execute("DELETE FROM chats")
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/notes")
def list_notes():
    db = get_db()
    rows = db.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/notes", methods=["DELETE"])
def clear_notes():
    db = get_db()
    db.execute("DELETE FROM notes")
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/note/<int:nid>", methods=["DELETE"])
def del_note(nid):
    db = get_db()
    db.execute("DELETE FROM notes WHERE id=?", (nid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    d = request.get_json()
    user_input = (d.get("text") or "").strip()
    history = d.get("history", [])
    if not user_input:
        return jsonify({"error": "请输入内容"}), 400
    if not LLM_API_KEY:
        return jsonify({"error": "未配置 LLM_API_KEY，请在 AI语音对话Agent.py 顶部填入 " + CURRENT_PROVIDER + " key"}), 500

    # 历史压缩：只保留最近 8 条消息
    history = history[-8:] if len(history) > 8 else history

    def stream():
        try:
            for event in run_agent(history, user_input):
                yield sse(event)
        except Exception as e:
            yield sse({"type": "error", "msg": "Agent 异常：" + str(e)})

    return Response(stream_with_context(stream()), mimetype="text/event-stream")


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI 语音对话 Agent · AGENT_VOICE11</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e1a;color:#e0e6ed;font-family:"Microsoft YaHei",sans-serif;min-height:100vh}
.hero{background:linear-gradient(135deg,#4a148c,#6a1b9a,#8e24aa);padding:20px;text-align:center}
.hero h1{font-size:21px;margin-bottom:4px;color:#fff}
.hero .code{display:inline-block;padding:3px 12px;background:rgba(255,255,255,.18);border-radius:12px;font-size:11px;color:#e1bee7}
.hero .desc{color:#e1bee7;font-size:12px;margin-top:6px}
.main{max-width:1100px;margin:14px auto;padding:0 14px;display:grid;grid-template-columns:1fr 300px;gap:14px}
@media(max-width:850px){.main{grid-template-columns:1fr}}
.card{background:#111827;border-radius:10px;padding:14px;margin-bottom:14px;border:1px solid #1e293b}
.card h2{color:#ab47bc;font-size:14px;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.chat-box{height:380px;overflow-y:auto;background:#050a18;border-radius:8px;padding:12px;margin-bottom:10px;border:1px solid #1a2942}
.chat-box::-webkit-scrollbar{width:6px}
.chat-box::-webkit-scrollbar-thumb{background:#1e3a5f}
.msg{margin:8px 0;display:flex;gap:10px}
.msg.user{flex-direction:row-reverse}
.msg .avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.msg.user .avatar{background:#0288d1}
.msg.ai .avatar{background:#8e24aa}
.msg .body{max-width:75%}
.msg .bubble{padding:9px 14px;border-radius:12px;font-size:13px;line-height:1.6;word-break:break-word}
.msg.user .bubble{background:#0d47a1;color:#fff;border-top-right-radius:4px}
.msg.ai .bubble{background:#1e293b;color:#e0e6ed;border-top-left-radius:4px}
.msg .meta{font-size:10px;color:#4b5563;margin-top:3px;text-align:right}
.msg.user .meta{text-align:left}
.msg .tool-box{margin-top:4px;font-size:11px;color:#7b8794;background:#050a18;padding:4px 8px;border-radius:4px;border-left:2px solid #ab47bc}
.thinking{margin:8px 0;display:flex;gap:10px}
.thinking .avatar{background:#8e24aa;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px}
.thinking .body{padding:9px 14px;background:#1e293b;border-radius:12px;font-size:13px;color:#7b8794;border-top-left-radius:4px}
.thinking .dot{display:inline-block;width:6px;height:6px;background:#ab47bc;border-radius:50%;margin:0 2px;animation:bounce 1s infinite}
.thinking .dot:nth-child(2){animation-delay:.2s}
.thinking .dot:nth-child(3){animation-delay:.4s}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
.input-row{display:flex;gap:10px;align-items:center}
.input-row input{flex:1;padding:11px;background:#0a0e1a;border:1px solid #1e3a5f;color:#e0e6ed;border-radius:8px;font-size:14px;font-family:inherit}
.input-row input:focus{border-color:#ab47bc;outline:none}
.mic-btn{width:48px;height:48px;border-radius:50%;border:none;cursor:pointer;font-size:22px;background:linear-gradient(135deg,#8e24aa,#6a1b9a);color:#fff;transition:.2s;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.mic-btn:hover{transform:scale(1.08)}
.mic-btn.rec{background:linear-gradient(135deg,#e74c3c,#c0392b);animation:pulseMic 1s infinite}
@keyframes pulseMic{0%,100%{box-shadow:0 0 0 0 rgba(231,76,60,.7)}50%{box-shadow:0 0 0 10px rgba(231,76,60,0)}}
.send-btn{padding:11px 18px;background:linear-gradient(90deg,#0288d1,#03a9f4);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:bold}
.wave{display:none;height:30px;align-items:center;justify-content:center;gap:3px;margin:6px 0}
.wave.show{display:flex}
.wave span{width:3px;background:#ab47bc;border-radius:2px;animation:waveAnim .6s infinite alternate}
.wave span:nth-child(1){height:8px;animation-delay:0s}
.wave span:nth-child(2){height:20px;animation-delay:.1s}
.wave span:nth-child(3){height:30px;animation-delay:.2s}
.wave span:nth-child(4){height:20px;animation-delay:.3s}
.wave span:nth-child(5){height:10px;animation-delay:.4s}
@keyframes waveAnim{from{height:5px}to{height:30px}}
.note-item{background:#050a18;padding:8px 10px;border-radius:6px;margin:5px 0;font-size:12px;line-height:1.5;border-left:3px solid #ab47bc;color:#e0e6ed}
.note-item .meta{display:flex;justify-content:space-between;align-items:center;margin-top:4px;font-size:10px;color:#7b8794}
.note-item .tag{padding:1px 6px;border-radius:8px;background:#4a148c;color:#e1bee7}
.note-item .del{background:none;border:none;cursor:pointer;color:#f87171;font-size:11px;padding:0}
.note-item .del:hover{color:#fff}
.warn{padding:8px 10px;border-radius:5px;font-size:11px;line-height:1.6;margin-bottom:8px}
.warn.ok{background:#0e2a1e;border:1px solid #1b5e20;color:#81c784}
.warn.err{background:#2a1a0a;border:1px solid #b1351d;color:#ffcc80}
.field{margin-bottom:8px}
.field label{display:block;color:#7b8794;font-size:11px;margin-bottom:4px}
.field input,.field select{width:100%;padding:7px;background:#0a0e1a;border:1px solid #1e3a5f;color:#e0e6ed;border-radius:5px;font-size:12px}
.btn{padding:6px 12px;border:none;border-radius:5px;cursor:pointer;font-size:12px;font-weight:bold;font-family:inherit}
.btn-purple{background:linear-gradient(90deg,#8e24aa,#6a1b9a);color:#fff}
.btn-sm{padding:4px 10px;font-size:11px}
.btn-yellow{background:#374151;color:#fbbf24}
.btn-red{background:#3e2723;color:#f87171}
.tab-bar{display:flex;gap:5px;margin-bottom:8px}
.btn-tab{padding:5px 12px;background:#1e293b;color:#7b8794;border:1px solid #1e3a5f;border-radius:15px;font-size:11px;cursor:pointer;font-family:inherit}
.btn-tab.active{background:#8e24aa;color:#fff;border:none}
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
.status-saved{background:#2ecc71}
.status-unsaved{background:#f39c12}
.empty{text-align:center;padding:20px;color:#4b5563;font-size:12px}
.hint{font-size:11px;color:#7b8794;margin-top:6px;line-height:1.5}
.hint b{color:#e1bee7}
</style>
</head>
<body>
<div class="hero">
  <h1>🎤 AI 语音对话 Agent</h1>
  <div class="code">AGENT_VOICE11</div>
  <div class="desc">真 AI · 真语音识别合成 · 真 Agent 工具调用（天气/时间/计算/笔记/维基）</div>
</div>
<div class="main">
  <div>
    <div class="card">
      <div class="warn" id="keyStatus">检测中...</div>
      <h2>💬 对话窗口</h2>
      <div class="chat-box" id="chatBox"></div>
      <div class="wave" id="wave"><span></span><span></span><span></span><span></span><span></span></div>
      <div class="input-row">
        <button class="mic-btn" id="micBtn" onclick="toggleMic()" title="点击说话">🎤</button>
        <input id="textInput" placeholder="输入文字，或点麦克风说话..." onkeydown="if(event.key==='Enter')sendText()">
        <button class="send-btn" onclick="sendText()" id="sendBtn">发送</button>
      </div>
      <div class="hint">💡 试试问：<b>现在几点</b> · <b>北京今天天气</b> · <b>3.14乘以8</b> · <b>记一下明天买牛奶</b> · <b>我之前记了什么</b> · <b>介绍一下量子计算</b></div>
    </div>
  </div>

  <div>
    <div class="card">
      <div class="tab-bar">
        <button class="btn-tab active" onclick="switchSide('notes',this)">📝 笔记</button>
        <button class="btn-tab" onclick="switchSide('voice',this)">🔊 语音</button>
      </div>
      <div id="side-notes">
        <div class="hint" id="noteCount" style="margin-bottom:6px">笔记数：0</div>
        <div id="noteList"></div>
        <div style="margin-top:10px">
          <button class="btn btn-sm btn-yellow" style="width:100%;margin-bottom:5px" onclick="exportNotes()">📋 导出笔记</button>
          <button class="btn btn-sm btn-red" style="width:100%" onclick="clearNotes()">🗑 清空笔记</button>
        </div>
      </div>
      <div id="side-voice" style="display:none">
        <div class="field"><label>语速 (0.5-2.0)</label><input id="setRate" type="range" min="0.5" max="2" step="0.1" value="1" oninput="saveVoiceSettings()"></div>
        <div class="field"><label>音调 (0-2)</label><input id="setPitch" type="range" min="0" max="2" step="0.1" value="1" oninput="saveVoiceSettings()"></div>
        <div class="field"><label>语音合成音色</label><select id="setVoice"></select></div>
        <div class="field"><label><input type="checkbox" id="setAuto" checked onchange="saveVoiceSettings()"> 自动朗读 AI 回复</label></div>
        <button class="btn btn-purple" style="width:100%" onclick="testVoice()">🔊 测试语音</button>
        <div class="hint" style="margin-top:10px">
          <b>说明：</b><br>
          · 语音识别：Chrome/Edge 浏览器 + localhost 访问<br>
          · 语音合成：所有现代浏览器可用<br>
          · 需要授权麦克风权限
        </div>
      </div>
    </div>

    <div class="card">
      <h2>🤖 Agent 工具</h2>
      <div class="hint">
        <b>真调 LLM API 决定调用哪个工具，真执行真返回：</b><br>
        ⏰ get_time — 真系统时间<br>
        🌤 get_weather — 真调 Open-Meteo API<br>
        🧮 calc — 真计算表达式<br>
        📝 save_note — 真存到 SQLite<br>
        🔍 query_notes — 真查 SQLite<br>
        📚 search_wiki — 真调维基百科 API
      </div>
    </div>

    <div class="card">
      <h2>⚙ 对话管理</h2>
      <button class="btn btn-sm btn-yellow" style="width:100%;margin-bottom:6px" onclick="exportChat()">📋 导出对话</button>
      <button class="btn btn-sm btn-red" style="width:100%" onclick="clearChat()">🗑 清空对话</button>
    </div>
  </div>
</div>

<script>
var recognition=null,recognizing=false;
var rate=1,pitch=1,voices=[],autoSpeak=true;
var isResponding=false;

function checkKey(){
  fetch("/api/status").then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById("keyStatus");
    if (d.configured){
      el.className="warn ok";
      el.innerHTML="✅ <b>"+esc(d.provider)+"</b> 已配置 ｜ 模型：<b>"+esc(d.model)+"</b> ｜ "+esc(d.note);
    } else {
      el.className="warn err";
      el.innerHTML="⚠️ 未配置 API Key ｜ 平台：<b>"+esc(d.provider)+"</b> ｜ "+esc(d.note)+
        "<br><br><b>配置：</b>1. 访问 <b>"+esc(d.register)+"</b> 注册创建 key"+
        "<br>2. 打开 <b>AI语音对话Agent.py</b>，顶部 <code>LLM_API_KEY = &quot;&quot;</code> 填入"+
        "<br>3. （可选）改 <code>CURRENT_PROVIDER</code> 切换平台"+
        "<br>4. 重启：Ctrl+C 后重跑";
    }
  });
}

function initVoices(){
  function load(){
    voices=speechSynthesis.getVoices();
    var sel=document.getElementById("setVoice");
    sel.innerHTML="";
    var zhVoices=voices.filter(function(v){return v.lang.indexOf("zh")>=0||v.lang.indexOf("cmn")>=0;});
    var list=zhVoices.length?zhVoices:voices;
    list.forEach(function(v){
      var o=document.createElement("option");
      o.value=voices.indexOf(v);
      o.text=v.name+" ("+v.lang+")";
      sel.add(o);
    });
  }
  load();
  if (speechSynthesis.onvoiceschanged!==undefined) speechSynthesis.onvoiceschanged=load;
}

function initRecog(){
  var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if (!SR){
    alert("您的浏览器不支持语音识别，请用 Chrome 或 Edge");
    return null;
  }
  var r=new SR();
  r.lang="zh-CN";r.continuous=false;r.interimResults=false;
  r.onresult=function(e){
    var txt=e.results[0][0].transcript;
    document.getElementById("textInput").value=txt;
    sendText();
  };
  r.onend=function(){recognizing=false;updateMic(false);wave(false);};
  r.onerror=function(e){
    recognizing=false;updateMic(false);wave(false);
    if (e.error!=="no-speech" && e.error!=="aborted") alert("语音识别错误："+e.error);
  };
  r.onstart=function(){recognizing=true;updateMic(true);wave(true);};
  return r;
}

function toggleMic(){
  if (!recognition) recognition=initRecog();
  if (!recognition) return;
  if (isResponding){ alert("AI 正在回复，请稍候"); return; }
  if (recognizing){ recognition.stop(); return; }
  try { recognition.start(); } catch(e){}
}

function updateMic(rec){
  var btn=document.getElementById("micBtn");
  btn.classList.toggle("rec",rec);
  btn.textContent=rec?"⏹":"🎤";
}

function wave(show){ document.getElementById("wave").classList.toggle("show",show); }

function sendText(){
  if (isResponding) return;
  var input=document.getElementById("textInput");
  var txt=input.value.trim();
  if (!txt) return;
  input.value="";
  saveChat("user",txt,"");
  addChatUI(0,"user",txt,"");
  streamAgent(txt);
}

function streamAgent(text){
  isResponding=true;
  document.getElementById("sendBtn").disabled=true;
  document.getElementById("sendBtn").textContent="...";

  // 历史聊天作为上下文
  var history=[];
  document.querySelectorAll("#chatBox .msg").forEach(function(m){
    var role=m.classList.contains("user")?"user":"assistant";
    var bubble=m.querySelector(".bubble");
    if (bubble && bubble.dataset.full) history.push({role:role,content:bubble.dataset.full});
  });
  history=history.slice(-8);

  // 占位 AI 消息
  var aiMsg=addThinkingUI();
  var collected="";
  var toolsCalled=[];

  fetch("/chat/stream",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({text:text,history:history})
  }).then(function(res){
    if (!res.ok){
      return res.json().then(function(e){throw new Error(e.error||"请求失败");});
    }
    var reader=res.body.getReader();
    var decoder=new TextDecoder("utf-8");
    var buffer="";

    function pump(){
      reader.read().then(function(res){
        if (res.done){ finish(aiMsg,collected,toolsCalled); return; }
        buffer+=decoder.decode(res.value,{stream:true});
        var parts=buffer.split("\\n\\n");
        buffer=parts.pop();
        parts.forEach(function(p){
          if (p.startsWith("data: ")){
            var json;
            try { json=JSON.parse(p.slice(6)); } catch(e){ return; }
            handleEvent(json,aiMsg);
            if (json.type==="delta") collected+=json.chunk;
            if (json.type==="tool_call") toolsCalled.push({name:json.name,args:json.args});
            if (json.type==="final" || json.type==="error") { finish(aiMsg,collected,toolsCalled); }
          }
        });
        if (buffer.indexOf("data: ")<0 || buffer.endsWith("\\n\\n")) pump();
        else pump();
      }).catch(function(e){
        appendToBubble(aiMsg,"\\n[错误] "+e.message);
        finish(aiMsg,collected,toolsCalled);
      });
    }
    pump();
  }).catch(function(e){
    appendToBubble(aiMsg,"[错误] "+e.message);
    finish(aiMsg,collected,toolsCalled);
  });
}

function handleEvent(ev,aiMsg){
  if (ev.type==="stream_start"){
    // 把 thinking 占位换成空 bubble
    var body=aiMsg.querySelector(".body");
    body.innerHTML='<div class="bubble" data-full=""></div>';
  } else if (ev.type==="delta"){
    var bubble=aiMsg.querySelector(".bubble");
    if (!bubble){
      var body=aiMsg.querySelector(".body");
      body.innerHTML='<div class="bubble" data-full=""></div>';
      bubble=aiMsg.querySelector(".bubble");
    }
    bubble.innerHTML+=ev.chunk.replace(/\\n/g,"<br>");
    bubble.dataset.full=(bubble.dataset.full||"")+ev.chunk;
    scrollChat();
  } else if (ev.type==="tool_call"){
    var tBox=document.createElement("div");
    tBox.className="tool-box";
    tBox.innerHTML="🔧 调用工具：<b>"+esc(ev.name)+"</b> 参数："+esc(JSON.stringify(ev.args));
    aiMsg.querySelector(".body").appendChild(tBox);
    scrollChat();
  } else if (ev.type==="tool_result"){
    var tBox=document.createElement("div");
    tBox.className="tool-box";
    tBox.style.borderLeftColor="#43a047";
    tBox.innerHTML="✅ 工具返回："+esc(ev.result);
    aiMsg.querySelector(".body").appendChild(tBox);
    scrollChat();
  } else if (ev.type==="error"){
    var body=aiMsg.querySelector(".body")||aiMsg;
    body.innerHTML+='<div class="bubble" style="background:#7f1d1d;color:#fca5a5">[错误] '+esc(ev.msg)+'</div>';
  }
}

function finish(aiMsg,collected,toolsCalled){
  isResponding=false;
  document.getElementById("sendBtn").disabled=false;
  document.getElementById("sendBtn").textContent="发送";
  // 移除 thinking 占位（如果还残留）
  var thinking=aiMsg.querySelector(".thinking")||aiMsg.querySelector(".dot");
  // 把数据保存到后端
  var toolName=toolsCalled.map(function(t){return t.name;}).join(",");
  if (collected){
    saveChat("ai",collected,toolName);
    // 更新 UI 元数据
    var bubble=aiMsg.querySelector(".bubble");
    if (bubble){
      bubble.dataset.full=collected;
      // 加 meta
      if (!aiMsg.querySelector(".meta")){
        var meta=document.createElement("div");
        meta.className="meta";
        meta.textContent=toolName?("工具："+toolName):"AI";
        aiMsg.querySelector(".body").appendChild(meta);
      }
    }
    if (autoSpeak) speak(collected);
  }
  scrollChat();
}

function addThinkingUI(){
  var box=document.getElementById("chatBox");
  var div=document.createElement("div");
  div.className="msg ai";
  div.innerHTML='<div class="avatar">🤖</div>'+
    '<div class="body"><div class="bubble" style="color:#7b8794">思考中 <span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>';
  box.appendChild(div);
  scrollChat();
  return div;
}

function appendToBubble(aiMsg,text){
  var bubble=aiMsg.querySelector(".bubble");
  if (!bubble){
    var body=aiMsg.querySelector(".body");
    body.innerHTML='<div class="bubble"></div>';
    bubble=aiMsg.querySelector(".bubble");
  }
  bubble.innerHTML+=text.replace(/\\n/g,"<br>");
  scrollChat();
}

function scrollChat(){
  var box=document.getElementById("chatBox");
  box.scrollTop=box.scrollHeight;
}

function speak(text){
  if (!speechSynthesis) return;
  speechSynthesis.cancel();
  var u=new SpeechSynthesisUtterance(text);
  u.lang="zh-CN";u.rate=rate;u.pitch=pitch;
  var sel=document.getElementById("setVoice");
  if (sel.value && voices[sel.value]) u.voice=voices[sel.value];
  speechSynthesis.speak(u);
}

function saveChat(role,content,tool){
  fetch("/api/chat",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({role:role,content:content,tool:tool||""})
  });
}

function addChatUI(id,role,content,time,tool){
  var box=document.getElementById("chatBox");
  var div=document.createElement("div");
  div.className="msg "+role;
  div.innerHTML='<div class="avatar">'+(role==="user"?"🧑":"🤖")+'</div>'+
    '<div class="body">'+
      '<div class="bubble" data-full="'+esc(content)+'">'+esc(content).replace(/\\n/g,"<br>")+'</div>'+
      (tool?'<div class="meta">工具：'+esc(tool)+'</div>':'<div class="meta">'+(time||"")+'</div>')+
    '</div>';
  box.appendChild(div);
  scrollChat();
}

function loadChat(){
  fetch("/api/chats").then(function(r){return r.json();}).then(function(data){
    data.forEach(function(c){
      addChatUI(c.id,c.role,c.content,c.created_at,c.tool);
    });
  });
}

function loadNotes(){
  fetch("/api/notes").then(function(r){return r.json();}).then(function(data){
    var box=document.getElementById("noteList");
    document.getElementById("noteCount").textContent="笔记数："+data.length;
    if (!data.length){
      box.innerHTML='<div class="empty">暂无笔记<br><span style="font-size:10px">对 AI 说"记一下..."即可自动保存</span></div>';
      return;
    }
    box.innerHTML=data.map(function(n){
      return '<div class="note-item">'+esc(n.content)+
        '<div class="meta">'+
          '<span class="tag">'+esc(n.tag||"无标签")+'</span>'+
          '<span>'+esc(n.created_at)+'</span>'+
          '<button class="del" onclick="delNote('+n.id+')">删除</button>'+
        '</div></div>';
    }).join("");
  });
}

function delNote(id){
  fetch("/api/note/"+id,{method:"DELETE"}).then(loadNotes);
}

function clearNotes(){
  if (!confirm("清空所有笔记？")) return;
  fetch("/api/notes",{method:"DELETE"}).then(loadNotes);
}

function saveVoiceSettings(){
  rate=parseFloat(document.getElementById("setRate").value);
  pitch=parseFloat(document.getElementById("setPitch").value);
  autoSpeak=document.getElementById("setAuto").checked;
}

function testVoice(){
  speak("你好，这是语音测试。当前语速"+rate+"，音调"+pitch+"。");
}

function switchSide(tab,btn){
  document.querySelectorAll(".tab-bar .btn-tab").forEach(function(b){b.classList.remove("active");});
  btn.classList.add("active");
  document.getElementById("side-notes").style.display=tab==="notes"?"block":"none";
  document.getElementById("side-voice").style.display=tab==="voice"?"block":"none";
}

function exportChat(){
  fetch("/api/chats").then(function(r){return r.json();}).then(function(data){
    if (!data.length){ alert("暂无对话"); return; }
    var txt="══════ AI 对话记录 ══════\\n\\n";
    data.forEach(function(c){
      txt+=(c.role==="user"?"我":"AI")+"："+c.content+"\\n";
      if (c.tool) txt+="  (调用了工具："+c.tool+")\\n";
      txt+="  ("+c.created_at+")\\n\\n";
    });
    download(txt,"AI对话");
  });
}

function exportNotes(){
  fetch("/api/notes").then(function(r){return r.json();}).then(function(data){
    if (!data.length){ alert("暂无笔记"); return; }
    var txt="══════ 语音笔记 ══════\\n\\n";
    data.forEach(function(n,i){
      txt+=(i+1)+". "+n.content+" ["+(n.tag||"无标签")+"]\\n   ("+n.created_at+")\\n\\n";
    });
    download(txt,"语音笔记");
  });
}

function download(txt,name){
  var blob=new Blob([txt],{type:"text/plain;charset=utf-8"});
  var a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  a.download=name+"_"+Date.now()+".txt";
  a.click();
}

function clearChat(){
  if (!confirm("清空所有对话？")) return;
  fetch("/api/chats",{method:"DELETE"}).then(function(){
    document.getElementById("chatBox").innerHTML="";
  });
}

function esc(s){
  return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

checkKey();
initVoices();
loadChat();
loadNotes();
</script>
</body>
</html>"""


@app.route("/")
def index():
    # 注意：直接返回字符串，不走 Jinja2 渲染
    # PAGE 里没有需要 Flask 替换的变量
    return Response(PAGE, mimetype="text/html; charset=utf-8")


if __name__ == "__main__":
    print("=" * 60)
    p = PROVIDERS.get(CURRENT_PROVIDER, {})
    print("当前 LLM 平台：", CURRENT_PROVIDER, "｜模型：", p.get("model", "?"))
    print("注册地址：", p.get("register", ""))
    if LLM_API_KEY:
        print("✅ LLM_API_KEY 已配置")
    else:
        print("⚠️  未配置 LLM_API_KEY")
        print("   1. 访问上面注册地址创建 key")
        print("   2. 在本文件顶部 LLM_API_KEY = \"\" 中粘贴")
        print("   3. 重新运行本文件")
    print("🚀 用 Chrome/Edge 访问 http://127.0.0.1:5011")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5011, debug=True)
#part2 语音识别功能