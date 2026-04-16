// Live theme provider — thin wrappers around services/api/themeApi.

import service from '../../../api/index'
import {
  listGlobalThemes as apiListGlobalThemes,
  getThemeHubView as apiGetThemeHubView,
  getThemePanorama as apiGetThemePanorama,
  getOrphans as apiGetOrphans,
} from '../../../services/api/themeApi'

export function listGlobalThemes() {
  return apiListGlobalThemes()
}

export function getThemeHubView(themeId) {
  return apiGetThemeHubView(themeId)
}

export function getThemePanorama(themeId) {
  return apiGetThemePanorama(themeId)
}

export function getOrphans(limit = 200) {
  return apiGetOrphans(limit)
}

// ThemeTab (inside RegistryPage) previously called raw service() — we
// route it through the same endpoint so live behaviour is unchanged.
export function listThemesViaRegistryTab() {
  return service({ url: '/api/registry/themes', method: 'get' })
}
