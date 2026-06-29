<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { basePath, bootstrap, runtime, type Feature } from './api/runtime'
import LookingGlassView from './features/looking-glass/LookingGlassView.vue'
import SchedulerView from './features/scheduler/SchedulerView.vue'

const loading = ref(true)
const error = ref('')
const activeFeatureId = ref('')

const features = computed(() => runtime.boot?.features || [])
const activeFeature = computed(() => features.value.find((feature) => feature.id === activeFeatureId.value) || features.value[0])

onMounted(async () => {
  try {
    await bootstrap()
    activeFeatureId.value = matchFeature(features.value)?.id || features.value[0]?.id || ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})

function selectFeature(feature: Feature) {
  activeFeatureId.value = feature.id
  window.history.replaceState(null, '', `${featureURL(feature)}${window.location.search}${window.location.hash}`)
}

function matchFeature(items: Feature[]) {
  const current = window.location.pathname
  return items.find((feature) => current.startsWith(featureURL(feature)))
}

function featureURL(feature: Feature) {
  const base = basePath()
  return base === '/' ? feature.path : `${base}${feature.path}`
}
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div>
        <div class="brand">sub2api tools</div>
        <div class="muted">{{ runtime.boot?.user.username || runtime.boot?.user.id || '-' }} · {{ runtime.boot?.user.role || '-' }}</div>
      </div>
      <nav class="nav" v-if="features.length">
        <button
          v-for="feature in features"
          :key="feature.id"
          type="button"
          :class="{ active: activeFeature?.id === feature.id }"
          @click="selectFeature(feature)"
        >
          {{ feature.name }}
        </button>
      </nav>
    </header>
    <main class="content">
      <div v-if="loading" class="panel muted">加载中...</div>
      <div v-else-if="error" class="panel error">{{ error }}</div>
      <div v-else-if="!activeFeature" class="panel muted">当前用户没有可见功能</div>
      <LookingGlassView v-else-if="activeFeature.id === 'looking-glass'" />
      <SchedulerView v-else-if="activeFeature.id === 'account-scheduler'" />
      <div v-else class="panel muted">未知功能：{{ activeFeature.id }}</div>
    </main>
  </div>
</template>
