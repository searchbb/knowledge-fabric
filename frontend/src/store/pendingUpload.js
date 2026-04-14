/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  vaultRelativeDir: '',  // 用户选择的 Obsidian vault 子目录,空字符串表示不走 vault
  isPending: false
})

export function setPendingUpload(files, requirement, vaultRelativeDir = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.vaultRelativeDir = vaultRelativeDir || ''
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    vaultRelativeDir: state.vaultRelativeDir,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.vaultRelativeDir = ''
  state.isPending = false
}

export default state
