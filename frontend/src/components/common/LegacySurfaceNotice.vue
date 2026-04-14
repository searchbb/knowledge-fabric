<template>
  <section class="legacy-notice">
    <div class="notice-topline">LEGACY SURFACE</div>
    <div class="notice-main">
      <div class="notice-copy">
        <h2 class="notice-title">{{ title }}</h2>
        <p class="notice-text">
          当前页面仍走 <code>legacy_zep</code> 兼容链路，仅用于保留旧能力。
          Phase 2 的默认知识工作台主线已经迁到本地化的 workspace 视图。
        </p>
      </div>
      <a
        v-if="workspacePath"
        class="notice-link"
        :href="workspacePath"
      >
        打开 Phase 2 工作台
      </a>
    </div>
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '兼容模式页面',
  },
  workspacePath: {
    type: String,
    default: '',
  },
})
</script>

<style scoped>
.legacy-notice {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 24px 16px;
  border-bottom: 1px solid rgba(189, 136, 56, 0.18);
  background:
    linear-gradient(90deg, rgba(248, 232, 203, 0.82), rgba(255, 251, 242, 0.95)),
    #fffaf0;
}

.notice-topline {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.22em;
  font-weight: 700;
  color: #9a5c12;
}

.notice-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.notice-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.notice-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #3b2a18;
}

.notice-text {
  margin: 0;
  max-width: 880px;
  font-size: 13px;
  line-height: 1.65;
  color: #6f5a45;
}

.notice-text code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #7a3f00;
}

.notice-link {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 14px;
  border: 1px solid rgba(145, 92, 19, 0.24);
  border-radius: 999px;
  text-decoration: none;
  font-size: 12px;
  font-weight: 700;
  color: #6e4716;
  background: rgba(255, 255, 255, 0.86);
}

.notice-link:hover {
  border-color: rgba(145, 92, 19, 0.4);
  background: #ffffff;
}

@media (max-width: 960px) {
  .legacy-notice {
    padding: 14px 16px 16px;
  }

  .notice-main {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
