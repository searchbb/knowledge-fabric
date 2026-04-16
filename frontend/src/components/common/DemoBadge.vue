<template>
  <span v-if="isDemo" class="demo-badge" title="当前显示的是本地示例数据，而非真实后端">
    <span class="dot" aria-hidden="true"></span>
    <span class="text">Demo mode</span>
    <span class="sub">Sample data only</span>
  </span>
</template>

<script setup>
import { isDemo } from '../../runtime/appMode'
</script>

<style scoped>
.demo-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #fff4e5;
  border: 1px solid #f0c68a;
  color: #8a5a00;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d9820a;
  box-shadow: 0 0 0 2px rgba(217, 130, 10, 0.15);
}
.text {
  letter-spacing: 0.02em;
}
.sub {
  color: #b5811c;
  font-weight: 500;
  font-size: 10px;
  opacity: 0.85;
}

@media (max-width: 720px) {
  /* On narrow widths, drop the sub-line to stay out of the way. */
  .sub { display: none; }
}
</style>
