"""Obsidian vault 相关 REST 接口。

提供:
- GET /api/vault/themes — 列出 vault 下可用的主题目录,供前端上传页下拉
- GET /api/vault/status — 报告 vault 是否启用及是否健康(启用时用,启动校验的运行时补充)

错误语义遵循 MiroFish 零 fallback:vault 未启用时返回明确的状态而非假装有数据。
"""

from flask import Blueprint, jsonify

from ...services.vault_service import VaultService, VaultError


vault_bp = Blueprint('vault', __name__, url_prefix='/api/vault')


@vault_bp.route('/status', methods=['GET'])
def vault_status():
    """返回 vault 启用状态。前端上传页用它决定是否渲染主题下拉。"""
    enabled = VaultService.is_enabled()
    if not enabled:
        return jsonify({
            "success": True,
            "enabled": False,
            "reason": "OBSIDIAN_VAULT_PATH 未配置",
        })

    try:
        root = VaultService.vault_root()
    except VaultError as e:
        return jsonify({
            "success": False,
            "enabled": True,
            "error_code": e.code,
            "error": e.message,
        }), 500

    return jsonify({
        "success": True,
        "enabled": True,
        "vault_root": root,
    })


@vault_bp.route('/themes', methods=['GET'])
def list_themes():
    """列出 vault 下可作为 md 落地目标的主题目录。

    返回示例:
    {
        "success": true,
        "enabled": true,
        "themes": [
            {"label": "AI", "relative_path": "AI", "has_notes_subdir": true},
            {"label": "AI / 笔记库", "relative_path": "AI/笔记库", "has_notes_subdir": false},
            ...
        ]
    }
    """
    if not VaultService.is_enabled():
        return jsonify({
            "success": True,
            "enabled": False,
            "themes": [],
            "reason": "OBSIDIAN_VAULT_PATH 未配置",
        })

    try:
        themes = VaultService.list_themes()
    except VaultError as e:
        return jsonify({
            "success": False,
            "enabled": True,
            "error_code": e.code,
            "error": e.message,
        }), 500

    return jsonify({
        "success": True,
        "enabled": True,
        "themes": [t.to_dict() for t in themes],
    })
