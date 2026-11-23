"""
PyCharm / 命令行一键启动入口
用法：直接运行本文件（右键 Run 'server'），或 python server.py
"""
import os
import sys

# 关键：把工作目录切到 backend（.env 和 app 包都在这里）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("运营管理系统启动中...")
    print("访问地址: http://127.0.0.1:8001/")
    print("登录账号: yjr / 123")
    print("=" * 50)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,  # 代码修改后自动重启，开发友好
    )
