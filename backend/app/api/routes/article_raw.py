"""项目原文(md)读取接口。

GET /api/workspace/projects/<pid>/article/raw
返回项目 source md 的原始字节(UTF-8 解码)+ 元信息。

读取策略(零 fallback):
1. 从 project.files[] 取第一个文件的 source_md_path
2. 若 project.files[].source_md_path 缺失(旧项目),fallback 到扫描 backend/uploads/projects/<pid>/files/
   (这不是 vault fallback,而是对旧格式 project.json 的兼容读取)
3. 若路径不存在或读取失败,返回明确错误码,前端会原样展示给用户

错误码:
- PROJECT_NOT_FOUND: project_id 不存在
- NO_SOURCE_FILE: 项目没有任何源 md 文件
- SOURCE_MD_MISSING: source_md_path 记录的文件已被删/移动
- SOURCE_MD_UNREADABLE: 文件存在但 IO 错误
"""

import os

from flask import Blueprint, jsonify

from ...models.project import ProjectManager


article_raw_bp = Blueprint('article_raw', __name__, url_prefix='/api/workspace')


@article_raw_bp.route('/projects/<project_id>/article/raw', methods=['GET'])
def get_article_raw(project_id: str):
    project = ProjectManager.get_project(project_id)
    if not project:
        return jsonify({
            "success": False,
            "error_code": "PROJECT_NOT_FOUND",
            "error": f"项目不存在: {project_id}",
        }), 404

    files = project.files or []
    if not files:
        return jsonify({
            "success": False,
            "error_code": "NO_SOURCE_FILE",
            "error": "该项目没有源文件记录",
        }), 404

    # 取第一个文件作为"文章原文"(MiroFish 当前单文件项目为主)
    entry = files[0]
    md_path = entry.get("source_md_path")
    source_backend = entry.get("source_backend") or "uploads"
    vault_relative_dir = entry.get("vault_relative_dir")

    if not md_path:
        # 旧项目 project.json 没有 source_md_path,扫 files_dir 找第一个 md
        files_dir = ProjectManager._get_project_files_dir(project_id)
        if os.path.isdir(files_dir):
            candidates = [
                os.path.join(files_dir, f)
                for f in sorted(os.listdir(files_dir))
                if f.lower().endswith(('.md', '.markdown'))
            ]
            if candidates:
                md_path = candidates[0]
                source_backend = "uploads"

    if not md_path:
        return jsonify({
            "success": False,
            "error_code": "NO_SOURCE_FILE",
            "error": "未能定位源 md 文件路径",
        }), 404

    if not os.path.exists(md_path):
        return jsonify({
            "success": False,
            "error_code": "SOURCE_MD_MISSING",
            "error": f"源 md 文件不存在:{md_path}",
            "source_md_path": md_path,
            "source_backend": source_backend,
        }), 404

    try:
        size = os.path.getsize(md_path)
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError as e:
        return jsonify({
            "success": False,
            "error_code": "SOURCE_MD_UNREADABLE",
            "error": f"读取源 md 失败:{e}",
            "source_md_path": md_path,
        }), 500

    # 外部图床(微信图床等)可能存在防盗链,前端应提前提示用户
    has_wechat_img = 'mmbiz.qpic.cn' in content or 'mmbiz.qlogo.cn' in content

    return jsonify({
        "success": True,
        "project_id": project_id,
        "filename": entry.get("filename") or os.path.basename(md_path),
        "size": size,
        "content": content,
        "source_backend": source_backend,
        "source_md_path": md_path,
        "vault_relative_dir": vault_relative_dir,
        "image_policy": {
            "mode": "external" if has_wechat_img else "none",
            "may_fail": has_wechat_img,
            "message": "原文包含微信外链图片,可能因防盗链无法加载(不影响文字)"
            if has_wechat_img
            else "",
        },
    })
