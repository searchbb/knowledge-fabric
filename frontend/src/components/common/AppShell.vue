<template>
  <div class="app-shell">
    <AppSidebar
      :current-project-id="currentProjectId"
      :current-project-section="currentProjectSection"
    />
    <div class="app-main">
      <AppTopBar :crumbs="crumbs" :show-copy="showCopy" :show-new-tab="showNewTab">
        <template #actions>
          <slot name="topbar-actions" />
        </template>
      </AppTopBar>
      <main class="app-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import AppTopBar from './AppTopBar.vue'

const props = defineProps({
  crumbs: {
    type: Array,
    required: true,
  },
  // Optional explicit override. When absent we derive from route.
  projectId: { type: String, default: '' },
  projectSection: { type: String, default: '' },
  showCopy: { type: Boolean, default: true },
  showNewTab: { type: Boolean, default: true },
})

const route = useRoute()

const currentProjectId = computed(() => {
  if (props.projectId) return props.projectId
  return route.params?.projectId || ''
})
const currentProjectSection = computed(() => {
  if (props.projectSection) return props.projectSection
  return route.params?.section || ''
})
</script>

<style scoped>
/* Full viewport-tall flex column so pages that want to fill remaining
   vertical space (e.g. article graph) can propagate `flex:1; min-height:0`
   all the way down. `height: 100vh` (not min-height) gives descendants a
   concrete height to resolve against; pages that overflow scroll via the
   page's own content area. `min-height: 0` on flex children lets them
   shrink past intrinsic size so `flex:1` actually works. */
.app-shell {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: var(--bg-app-gradient);
  color: var(--text-primary);
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.app-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.app-content {
  flex: 1;
  min-height: 0;
  padding: 20px 28px 32px;
  display: flex;
  flex-direction: column;
  overflow-x: auto;
  overflow-y: auto;
}

@media (max-width: 960px) {
  .app-shell { flex-direction: column; }
  .app-content { padding: 16px 18px 24px; }
}
</style>
