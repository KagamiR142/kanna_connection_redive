<template>
  <div class="page-wrap">
    <el-empty v-if="!groupId" description="请先在顶栏选择公会" />

    <template v-else>
      <div class="toolbar kanna-card">
        <span>会战日</span>
        <el-select v-model="selectedDate" placeholder="选择日期" style="width: 160px" @change="loadStats">
          <el-option v-for="d in battleDays" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button :loading="loading" @click="loadStats">刷新</el-button>
      </div>

      <el-table :data="rows" stripe v-loading="loading" class="mt-16">
        <el-table-column label="SL" width="60">
          <template #default="{ row }">{{ row.sl ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="qq_nickname" label="QQ 昵称" min-width="100" sortable />
        <el-table-column prop="game_name" label="游戏名" min-width="100" sortable />
        <el-table-column prop="knife_count" label="已出刀" width="90" sortable />
        <el-table-column prop="knife1" label="第一刀" min-width="120" />
        <el-table-column prop="knife2" label="第二刀" min-width="120" />
        <el-table-column prop="knife3" label="第三刀" min-width="120" />
        <el-table-column prop="qq_id" label="QQ" width="120" sortable />
        <el-table-column prop="viewer_id" label="UID" width="120" sortable />
      </el-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getBattleDays, getDailyStats } from '@/api'

const route = useRoute()
const groupId = computed(() => Number(route.params.groupId) || 0)

const battleDays = ref<string[]>([])
const selectedDate = ref('')
const rows = ref<any[]>([])
const loading = ref(false)

async function loadDays() {
  if (!groupId.value) return
  battleDays.value = await getBattleDays(groupId.value)
  if (battleDays.value.length && !selectedDate.value) {
    selectedDate.value = battleDays.value[battleDays.value.length - 1]
  }
}

async function loadStats() {
  if (!groupId.value || !selectedDate.value) return
  loading.value = true
  try {
    rows.value = await getDailyStats(groupId.value, selectedDate.value)
  } finally {
    loading.value = false
  }
}

watch(groupId, async () => {
  selectedDate.value = ''
  await loadDays()
  await loadStats()
})

onMounted(async () => {
  await loadDays()
  await loadStats()
})
</script>

<style scoped>
.page-wrap {
  padding: 8px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
}
.mt-16 {
  margin-top: 16px;
}
</style>
