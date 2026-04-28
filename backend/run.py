"""
Knowledge Fabric Center Backend 启动入口
"""

import os
import sys

# 解决 Windows 控制台中文乱码问题：在所有导入之前设置 UTF-8 编码
if sys.platform == 'win32':
    # 设置环境变量确保 Python 使用 UTF-8
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # 重新配置标准输出流为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 撕掉 HTTP(S)_PROXY 环境变量：本地 VPN/代理（如 Clash/Veee）在长流式 LLM
# 响应中容易中途断流，导致 httpx.RemoteProtocolError 让 ontology/graph build
# 以 500 挂掉。Backend 直连上游 LLM 更稳。如果就是需要走代理（比如 LLM
# endpoint 被墙），设 KFC_KEEP_PROXY=1 保留。
if not os.environ.get('KFC_KEEP_PROXY'):
    _stripped = [k for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy')
                 if os.environ.pop(k, None) is not None]
    if _stripped:
        print(f"[run.py] stripped proxy env for LLM stability: {_stripped} "
              "(set KFC_KEEP_PROXY=1 to keep)")

# 抬高文件描述符软上限：macOS 默认 256，长跑服务 + 并发 LLM/proxy socket 很容易打满，
# 一旦打满后续 socket 全部 ConnectError。Windows 没有 resource 模块，跳过。
if sys.platform != 'win32':
    import resource
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        target_hard = hard if hard != resource.RLIM_INFINITY else 65535
        target_soft = min(65535, target_hard)
        if target_soft > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target_soft, target_hard))
            print(f"[run.py] RLIMIT_NOFILE raised: {soft} -> {target_soft} (hard={target_hard})")
    except (ValueError, OSError) as _e:
        print(f"[run.py] WARN: failed to raise RLIMIT_NOFILE: {_e}")

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """主函数"""
    # 验证配置
    errors = Config.validate()
    if errors:
        print("配置错误:")
        for err in errors:
            print(f"  - {err}")
        print("\n请检查 .env 文件中的配置")
        sys.exit(1)
    
    # 创建应用
    app = create_app()
    
    # 获取运行配置
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG
    
    # 启动服务
    # Long-running graph builds run in daemon threads and keep task state in
    # memory, so Werkzeug's stat reloader would orphan them on every reload.
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
