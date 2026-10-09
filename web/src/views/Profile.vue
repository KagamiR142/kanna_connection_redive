<template>
  <div class="page-wrap">
    <el-empty v-if="!groupId" description="请先在顶栏选择公会" />

    <template v-else>
      <div class="section-title">游戏账号绑定（多槽位）</div>
      <div class="kanna-card bind-card">
        <p class="hint">
          从公会成员列表选择角色；「添加槽位」保留已有绑定。排序影响 QQ 默认账号与账号N 指令。凭证请 QQ 私聊【绑定账号】。
        </p>
        <el-table :data="bindingList" stripe empty-text="尚未绑定会战身份">
          <el-table-column label="槽位" width="70" prop="slot" />
          <el-table-column prop="name" label="角色" />
          <el-table-column prop="viewer_id" label="UID" width="120" />
          <el-table-column label="操作" width="160">
            <template #default="{ row, $index }">
              <el-button link size="small" :disabled="$index === 0" @click="moveUp($index)">
                上移
              </el-button>
              <el-button
                link
                size="small"
                :disabled="$index >= bindingList.length - 1"
                @click="moveDown($index)"
              >
                下移
              </el-button>
              <el-button link type="danger" size="small" @click="removeSlot(row.viewer_id)">
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="mt-12 add-row">
          <el-select
            v-model="selectedViewer"
            placeholder="选择角色添加/覆盖"
            filterable
            style="width: 100%; max-width: 420px"
            :loading="loadingMembers"
          >
            <el-option
              v-for="m in members"
              :key="m.viewer_id"
              :label="`${m.name} (${m.viewer_id}) Lv.${m.level}`"
              :value="m.viewer_id"
              :class="{ 'option-bound': isViewerBound(m.viewer_id) }"
            />
          </el-select>
          <el-button type="primary" :loading="saving" @click="saveBinding(false)">
            设为唯一绑定
          </el-button>
          <el-button :loading="saving" @click="saveBinding(true)">添加槽位</el-button>
        </div>
      </div>

      <div v-for="sec in sections" :key="sec.day" class="day-block mt-24">
        <div class="section-title">{{ sec.day_label || sec.day }}</div>
        <template v-for="acct in sec.accounts || []" :key="acct.viewer_id">
          <div class="account-subtitle">
            {{ acct.slot }}-{{ acct.name }}
          </div>
          <el-table :data="acct.records" stripe empty-text="暂无" class="mb-12">
            <el-table-column label="时间" width="160">
              <template #default="{ row }">{{ formatTime(row.time) }}</template>
            </el-table-column>
            <el-table-column label="Boss" width="100">
              <template #default="{ row }">{{ row.lap }}-{{ row.boss }}</template>
            </el-table-column>
            <el-table-column prop="damage" label="伤害" />
            <el-table-column label="角色" width="120">
              <template #default>{{ acct.name }}</template>
            </el-table-column>
            <el-table-column prop="knife_type" label="刀型" width="80" />
            <el-table-column label="击杀" width="70">
              <template #default="{ row }">{{ row.is_kill ? '是' : '' }}</template>
            </el-table-column>
          </el-table>
        </template>
      </div>
      <el-empty v-if="!loadingRecords && !sections.length" description="暂无当期出刀" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  deleteMyBindingSlot,
  getClanAccounts,
  getMyBinding,
  getSeasonRecords,
  putMyBinding,
  sortMyBindings,
} from '@/api'

const route = useRoute()
const groupId = computed(() => Number(route.params.groupId) || 0)

const sections = ref<any[]>([])
const members = ref<any[]>([])
const binding = ref<any>(null)
const bindingList = ref<any[]>([])
const selectedViewer = ref<number | undefined>()
const loadingRecords = ref(false)
const loadingMembers = ref(false)
const saving = ref(false)

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleString()
}

function isViewerBound(viewerId: number) {
  return bindingList.value.some((b) => Number(b.viewer_id) === Number(viewerId))
}

function enrichBindingNamesFromMembers() {
  const byVid = new Map<number, string>()
  for (const m of members.value) {
    const n = String(m.name || '').trim()
    if (n) byVid.set(Number(m.viewer_id), n)
  }
  if (!byVid.size) return
  bindingList.value = bindingList.value.map((b) => {
    const uidPat = /^UID\d+$/
    if (!uidPat.test(String(b.name || ''))) return b
    const n = byVid.get(Number(b.viewer_id))
    return n ? { ...b, name: n } : b
  })
  if (binding.value?.bindings?.length) {
    binding.value = {
      ...binding.value,
      bindings: bindingList.value,
      name: bindingList.value[0]?.name ?? binding.value.name
    }
  }
}

async function refreshBindingView() {
  if (!groupId.value) return
  binding.value = await getMyBinding(groupId.value)
  bindingList.value = binding.value?.bindings || []
  enrichBindingNamesFromMembers()
}

async function loadAll() {
  if (!groupId.value) return
  loadingRecords.value = true
  try {
    const raw = await getSeasonRecords(groupId.value)
    if (
      Array.isArray(raw) &&
      raw.length &&
      (raw[0].accounts?.length || raw[0].records?.length)
    ) {
      sections.value = raw
    } else if (Array.isArray(raw)) {
      sections.value = [{ day: '', day_label: '当期', records: raw }]
    } else {
      sections.value = []
    }
  } finally {
    loadingRecords.value = false
  }
  loadingMembers.value = true
  try {
    members.value = await getClanAccounts(groupId.value)
    await refreshBindingView()
    selectedViewer.value = binding.value?.viewer_id
  } finally {
    loadingMembers.value = false
  }
}

async function saveBinding(multi: boolean) {
  if (!selectedViewer.value || !groupId.value) {
    ElMessage.warning('请选择角色')
    return
  }
  saving.value = true
  try {
    await putMyBinding({
      viewer_id: selectedViewer.value,
      group_id: groupId.value,
      multi,
    })
    ElMessage.success(multi ? '已添加/更新槽位' : '已设为唯一绑定')
    await refreshBindingView()
  } finally {
    saving.value = false
  }
}

async function persistOrder() {
  const ids = bindingList.value.map((b) => b.viewer_id)
  if (ids.length < 2) return
  await sortMyBindings(ids, groupId.value)
  await refreshBindingView()
}

async function moveUp(index: number) {
  if (index <= 0) return
  const list = [...bindingList.value]
  ;[list[index - 1], list[index]] = [list[index], list[index - 1]]
  bindingList.value = list
  await persistOrder()
}

async function moveDown(index: number) {
  if (index >= bindingList.value.length - 1) return
  const list = [...bindingList.value]
  ;[list[index], list[index + 1]] = [list[index + 1], list[index]]
  bindingList.value = list
  await persistOrder()
}

async function removeSlot(viewerId: number) {
  await deleteMyBindingSlot(viewerId, groupId.value)
  ElMessage.success('已移除')
  await refreshBindingView()
}

watch(groupId, loadAll)
onMounted(loadAll)
</script>

<style scoped>
.page-wrap {
  padding: 8px;
}
.section-title {
  font-weight: 600;
  margin: 12px 0 8px;
}
.day-block {
  margin-bottom: 20px;
}
.bind-card {
  padding: 16px;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-bottom: 12px;
}
.add-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.mt-12 {
  margin-top: 12px;
}
.mt-24 {
  margin-top: 24px;
}
.account-subtitle {
  font-weight: 600;
  margin: 8px 0 4px;
  color: var(--el-text-color-regular);
}
.mb-12 {
  margin-bottom: 12px;
}
:deep(.option-bound) {
  background-color: var(--el-fill-color-light);
}
</style>
