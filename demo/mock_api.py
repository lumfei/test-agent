"""
Mock API 服务器 — 一个有 bug 的演示 API，用于展示 Agent 的缺陷发现能力。

启动: python demo/mock_api.py

包含的故意设计的 bug：
1. GET /api/users — 当 limit=0 时返回 500 而非 400
2. POST /api/users — 不验证 email 格式，接受空 name
3. GET /api/users/{id} — id=999 时返回 HTML 而非 JSON
4. DELETE /api/users/{id} — 不验证认证
5. POST /api/users — SQL 注入字符串原样返回在响应中
"""
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

HOST = "0.0.0.0"
PORT = 8003

# 模拟数据
USERS = {
    1: {"id": 1, "name": "张三", "email": "zhangsan@example.com", "role": "admin"},
    2: {"id": 2, "name": "李四", "email": "lisi@example.com", "role": "user"},
    3: {"id": 3, "name": "王五", "email": "wangwu@example.com", "role": "user"},
}
NEXT_ID = 4


class MockAPIHandler(BaseHTTPRequestHandler):
    """模拟的 REST API 处理器"""

    def do_GET(self):
        path = self.path.split("?")[0]

        # OpenAPI Spec
        if path == "/openapi.json":
            spec = self._generate_openapi_spec()
            self._json_response(200, spec)
            return

        # GET /api/users
        if path == "/api/users":
            params = self._parse_params()
            limit = int(params.get("limit", [10])[0])

            # BUG 1: limit=0 返回 500
            if limit == 0:
                self._error_response(500, "Internal Server Error: division by zero in pagination")
                return

            users = list(USERS.values())
            if limit > 0:
                users = users[:limit]
            self._json_response(200, {"users": users, "total": len(USERS)})
            return

        # GET /api/users/{id}
        if path.startswith("/api/users/"):
            try:
                user_id = int(path.split("/")[-1])

                # BUG 3: id=999 返回 HTML 而非 JSON
                if user_id == 999:
                    self._html_response(500, "<html><body><h1>Internal Error</h1><p>Stack trace...</p></body></html>")
                    return

                user = USERS.get(user_id)
                if user:
                    self._json_response(200, user)
                else:
                    self._json_response(404, {"error": "User not found"})
            except ValueError:
                self._json_response(400, {"error": "Invalid user ID"})
            return

        self._json_response(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0]

        # POST /api/users
        if path == "/api/users":
            try:
                body = self._read_body()
                data = json.loads(body) if body else {}

                # BUG 2: 不验证 email 格式，接受空 name
                global NEXT_ID
                new_user = {
                    "id": NEXT_ID,
                    "name": data.get("name", ""),       # BUG: 不拒绝空 name
                    "email": data.get("email", ""),      # BUG: 不验证 email 格式
                    "role": data.get("role", "user"),
                    # BUG 5: 不转义 SQL 注入字符串
                    "note": data.get("note", ""),
                }
                USERS[NEXT_ID] = new_user
                NEXT_ID += 1
                self._json_response(201, new_user)

            except json.JSONDecodeError:
                self._json_response(400, {"error": "Invalid JSON"})
            return

        self._json_response(404, {"error": "Not found"})

    def do_PUT(self):
        path = self.path.split("?")[0]

        if path.startswith("/api/users/"):
            try:
                user_id = int(path.split("/")[-1])
                if user_id not in USERS:
                    self._json_response(404, {"error": "User not found"})
                    return

                body = self._read_body()
                data = json.loads(body) if body else {}

                USERS[user_id].update({
                    "name": data.get("name", USERS[user_id]["name"]),
                    "email": data.get("email", USERS[user_id]["email"]),
                    "role": data.get("role", USERS[user_id]["role"]),
                })
                self._json_response(200, USERS[user_id])
            except (ValueError, json.JSONDecodeError):
                self._json_response(400, {"error": "Bad request"})
            return

        self._json_response(404, {"error": "Not found"})

    def do_DELETE(self):
        path = self.path.split("?")[0]

        if path.startswith("/api/users/"):
            try:
                user_id = int(path.split("/")[-1])

                # BUG 4: 不验证认证
                if user_id not in USERS:
                    self._json_response(404, {"error": "User not found"})
                    return

                del USERS[user_id]
                self._json_response(204, {"message": "Deleted"})
            except ValueError:
                self._json_response(400, {"error": "Invalid user ID"})
            return

        self._json_response(404, {"error": "Not found"})

    # ===== Helpers =====

    def _json_response(self, status: int, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html_response(self, status: int, html: str):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _error_response(self, status: int, message: str):
        self._json_response(status, {"error": message})

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode()
        return ""

    def _parse_params(self) -> dict:
        from urllib.parse import parse_qs, urlparse
        query = urlparse(self.path).query
        return parse_qs(query)

    def _generate_openapi_spec(self) -> dict:
        """动态生成 OpenAPI 3.0 规范"""
        server_url = f"http://localhost:{PORT}"
        return {
            "openapi": "3.0.3",
            "info": {
                "title": "用户管理 API (含Bug的演示版)",
                "version": "1.0.0",
                "description": "⚠️ 这是一个故意包含 Bug 的 Mock API，用于展示自动化测试 Agent 的缺陷发现能力。"
            },
            "servers": [{"url": server_url, "description": "本地 Mock 服务器"}],
            "paths": {
                "/api/users": {
                    "get": {
                        "summary": "获取用户列表",
                        "parameters": [
                            {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 10}}
                        ],
                        "responses": {
                            "200": {
                                "description": "成功",
                                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserList"}}}
                            }
                        }
                    },
                    "post": {
                        "summary": "创建用户",
                        "requestBody": {
                            "required": True,
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CreateUser"}}}
                        },
                        "responses": {
                            "201": {"description": "创建成功"},
                            "400": {"description": "参数错误"}
                        }
                    }
                },
                "/api/users/{id}": {
                    "get": {
                        "summary": "获取单个用户",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "成功"},
                            "404": {"description": "未找到"}
                        }
                    },
                    "put": {
                        "summary": "更新用户",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "200": {"description": "更新成功"},
                            "404": {"description": "未找到"}
                        }
                    },
                    "delete": {
                        "summary": "删除用户",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                        ],
                        "responses": {
                            "204": {"description": "删除成功"},
                            "404": {"description": "未找到"}
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string", "minLength": 1},
                            "email": {"type": "string", "format": "email"},
                            "role": {"type": "string", "enum": ["admin", "user"]}
                        },
                        "required": ["id", "name", "email"]
                    },
                    "CreateUser": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "email": {"type": "string", "format": "email"},
                            "role": {"type": "string", "enum": ["admin", "user"]}
                        },
                        "required": ["name", "email"]
                    },
                    "UserList": {
                        "type": "object",
                        "properties": {
                            "users": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
                            "total": {"type": "integer"}
                        }
                    }
                }
            }
        }

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    server = HTTPServer((HOST, PORT), MockAPIHandler)
    print(f"Mock Buggy API Server running at http://{HOST}:{PORT}")
    print(f"OpenAPI Spec: http://{HOST}:{PORT}/openapi.json")
    print(f"\n[BUGS] 5 deliberate bugs:")
    print(f"  1. GET /api/users?limit=0 -> 500 (should be 400)")
    print(f"  2. POST /api/users -> no email validation, accepts empty name")
    print(f"  3. GET /api/users/999 -> returns HTML instead of JSON")
    print(f"  4. DELETE /api/users/{{id}} -> no auth check")
    print(f"  5. POST /api/users -> SQL injection strings not escaped")
    print(f"\nPress Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.shutdown()
