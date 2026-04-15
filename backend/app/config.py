"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    LLM_TIMEOUT_SECONDS = int(os.environ.get('LLM_TIMEOUT_SECONDS', '180'))
    LLM_RESPONSE_FORMAT_MODE = os.environ.get('LLM_RESPONSE_FORMAT_MODE', 'auto').lower()
    GRAPHITI_LLM_API_KEY = os.environ.get('GRAPHITI_LLM_API_KEY') or LLM_API_KEY
    GRAPHITI_LLM_BASE_URL = os.environ.get('GRAPHITI_LLM_BASE_URL') or LLM_BASE_URL
    GRAPHITI_LLM_MODEL_NAME = os.environ.get('GRAPHITI_LLM_MODEL_NAME') or LLM_MODEL_NAME
    
    # Zep配置（保留兼容性，已迁移到 Graphiti 本地）
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    ENABLE_LEGACY_ZEP_SIMULATION = os.environ.get('ENABLE_LEGACY_ZEP_SIMULATION', 'true').lower() == 'true'
    ENABLE_LEGACY_ZEP_REPORTING = os.environ.get('ENABLE_LEGACY_ZEP_REPORTING', 'true').lower() == 'true'

    # Neo4j 本地图数据库配置（Graphiti 后端）
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'graphiti123')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Obsidian vault 集成:若配置了 OBSIDIAN_VAULT_PATH,上传 md 时支持写入 vault。
    # 读取原文(article/raw API)优先从 project.json.source_md_path 指向的位置读。
    # 零 fallback:若 vault 配置了但不可用,启动时报错,不偷偷回退 uploads。
    OBSIDIAN_VAULT_PATH = os.environ.get('OBSIDIAN_VAULT_PATH', '').strip() or None
    
    # Graphiti bulk processing concurrency limit
    GRAPHITI_SEMAPHORE_LIMIT = int(os.environ.get('GRAPHITI_SEMAPHORE_LIMIT', '3'))
    GRAPHITI_BATCH_SIZE = int(os.environ.get('GRAPHITI_BATCH_SIZE', '3'))

    # ===== 抽取模式开关 (local vs online DeepSeek) =====
    # 默认启动模式；运行时通过 backend/data/llm_mode.json 可覆盖。
    LLM_MODE_DEFAULT = os.environ.get('LLM_MODE_DEFAULT', 'local').strip().lower()

    # DeepSeek 在线 API（GPT consult 2026-04-11: semaphore 6 起步、不要超过 8；
    # deepseek-chat 非思考模式，比 deepseek-reasoner 更适合大量结构化抽取）。
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
    DEEPSEEK_MODEL_NAME = os.environ.get('DEEPSEEK_MODEL_NAME', 'deepseek-chat')
    DEEPSEEK_SEMAPHORE_LIMIT = int(os.environ.get('DEEPSEEK_SEMAPHORE_LIMIT', '6'))
    DEEPSEEK_BATCH_SIZE = int(os.environ.get('DEEPSEEK_BATCH_SIZE', '1'))

    # Bailian (Alibaba DashScope, OpenAI-compatible). qwen3.5-plus is the
    # current recommended main model for Graphiti bulk extraction: the
    # long-output tail is ~4-5x shorter than DeepSeek's on the same
    # edge-extraction prompts (2026-04-15 A/B: 40+ min → 11 min for a 14KB
    # Chinese article). Note: qwen3 models default to thinking=on on
    # DashScope; graph_builder.py turns it off via extra_body when
    # provider=='bailian', which matters for structured extraction latency.
    BAILIAN_API_KEY = os.environ.get('BAILIAN_API_KEY')
    BAILIAN_BASE_URL = os.environ.get(
        'BAILIAN_BASE_URL',
        'https://dashscope.aliyuncs.com/compatible-mode/v1',
    )
    BAILIAN_MODEL_NAME = os.environ.get('BAILIAN_MODEL_NAME', 'qwen3.5-plus')
    BAILIAN_SEMAPHORE_LIMIT = int(os.environ.get('BAILIAN_SEMAPHORE_LIMIT', '6'))
    BAILIAN_BATCH_SIZE = int(os.environ.get('BAILIAN_BATCH_SIZE', '1'))

    # 文本处理配置
    DEFAULT_CHUNK_SIZE = int(os.environ.get('DEFAULT_CHUNK_SIZE', '3000'))
    DEFAULT_CHUNK_OVERLAP = int(os.environ.get('DEFAULT_CHUNK_OVERLAP', '200'))
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.GRAPHITI_LLM_API_KEY:
            errors.append("GRAPHITI_LLM_API_KEY 未配置")
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD 未配置")
        # 若配置了 OBSIDIAN_VAULT_PATH,强校验(零 fallback:不可用就报错,不回退)
        if cls.OBSIDIAN_VAULT_PATH:
            vault = cls.OBSIDIAN_VAULT_PATH
            if not os.path.isdir(vault):
                errors.append(f"OBSIDIAN_VAULT_PATH 不存在或非目录: {vault}")
            elif not os.path.isdir(os.path.join(vault, '.obsidian')):
                errors.append(f"OBSIDIAN_VAULT_PATH 不是有效 Obsidian vault(缺少 .obsidian 目录): {vault}")
            elif not os.access(vault, os.W_OK):
                errors.append(f"OBSIDIAN_VAULT_PATH 不可写: {vault}")
        return errors
