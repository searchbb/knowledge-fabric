import service from './index'

/**
 * 查询 Obsidian vault 集成状态
 * 返回 {success, enabled, vault_root?} 或 {success:false, enabled, error_code, error}
 */
export function getVaultStatus() {
  return service({
    url: '/api/vault/status',
    method: 'get'
  })
}

/**
 * 列出 vault 下可作为 md 落地目标的主题目录(供上传页下拉)
 * 返回 {success, enabled, themes: [{label, relative_path, has_notes_subdir}, ...]}
 */
export function listVaultThemes() {
  return service({
    url: '/api/vault/themes',
    method: 'get'
  })
}

/**
 * 获取项目原文 md 内容(含图片策略)
 * 错误场景用 error_code 区分:
 * - PROJECT_NOT_FOUND / NO_SOURCE_FILE / SOURCE_MD_MISSING / SOURCE_MD_UNREADABLE
 */
export function getArticleRaw(projectId) {
  return service({
    url: `/api/workspace/projects/${projectId}/article/raw`,
    method: 'get'
  })
}
