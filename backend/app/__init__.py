"""
Knowledge Fabric Center Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Knowledge Fabric Center Backend 启动中...")
        logger.info("=" * 50)
    
    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
    # 请求日志中间件
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, review_bp, concept_bp, theme_bp, evolution_bp, registry_bp
    from .api.routes.auto_pipeline import auto_pipeline_bp
    from .api.routes.discover_jobs import discover_jobs_bp
    from .api.routes.llm_mode_config import llm_mode_config_bp
    from .api.routes.vault import vault_bp
    from .api.routes.article_raw import article_raw_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(review_bp, url_prefix='/api/review')
    app.register_blueprint(concept_bp, url_prefix='/api/concept')
    app.register_blueprint(theme_bp, url_prefix='/api/theme')
    app.register_blueprint(evolution_bp, url_prefix='/api/evolution')
    app.register_blueprint(registry_bp, url_prefix='/api/registry')
    # auto_pipeline_bp / discover_jobs_bp / llm_mode_config_bp / vault_bp / article_raw_bp 都自带 /api/* prefix
    app.register_blueprint(auto_pipeline_bp)
    app.register_blueprint(discover_jobs_bp)
    app.register_blueprint(llm_mode_config_bp)
    app.register_blueprint(vault_bp)
    app.register_blueprint(article_raw_bp)
    
    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'Knowledge Fabric Center Backend'}
    
    # Discover V2 worker (P1.2): opt-in background daemon that drains the
    # cross-concept discover job queue. Off by default so operators can
    # deploy the scheduling change first and observe main-pipeline latency
    # before flipping background execution on.
    if os.environ.get("AUTO_START_DISCOVER_WORKER", "0") == "1":
        try:
            from .services.auto.discover_worker import start_global_worker

            idle = float(os.environ.get("DISCOVER_WORKER_IDLE_SECONDS", "5"))
            start_global_worker(idle_sleep_seconds=idle, recover_stale_on_start=True)
            if should_log_startup:
                logger.info(f"discover worker started (idle_sleep={idle}s)")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"failed to start discover worker: {exc}")

    if should_log_startup:
        logger.info("Knowledge Fabric Center Backend 启动完成")

    return app
