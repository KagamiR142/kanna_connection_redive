<template>
  <div class="page-wrap">
    <el-alert
      v-if="!userStore.isGlobalAdmin"
      type="error"
      title="无权访问管理运维页"
      show-icon
      class="mb-16"
    />

    <template v-else>
      <el-tabs>
        <el-tab-pane label="监控状态">
          <el-table :data="monitors" v-loading="loadingMonitor" stripe>
            <el-table-column prop="group_id" label="群号" width="120" />
            <el-table-column prop="clan_name" label="公会" />
            <el-table-column prop="active" label="运行中" width="80">
              <template #default="{ row }">{{ row.active ? '是' : '否' }}</template>
            </el-table-column>
            <el-table-column prop="monitor_user_id" label="监控 QQ" width="120" />
            <el-table-column prop="rank" label="排名" width="80" />
          </el-table>
          <el-button class="mt-12" @click="loadMonitor">刷新</el-button>
        </el-tab-pane>

        <el-tab-pane label="QQ↔UID 绑定">
          <div class="kanna-card form-inline mb-12">
            <span>运维群</span>
            <el-select
              v-model="opsGroupId"
              placeholder="选择群"
              filterable
              style="width: 280px"
              @change="onOpsGroupChange"
            >
              <el-option
                v-for="g in bindingGroups"
                :key="g.group_id"
                :label="`${g.group_name} (${g.group_id})`"
                :value="String(g.group_id)"
              />
            </el-select>
            <el-button @click="reloadBindingWorkbench">刷新列表</el-button>
          </div>

          <div class="section-label">已绑定（按 QQ）</div>
          <el-table
            :data="bindingsGrouped"
            v-loading="loadingBind"
            stripe
            max-height="280"
            row-key="user_id"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <el-table :data="row.bindings" size="small">
                  <el-table-column prop="viewer_id" label="UID" width="120" />
                  <el-table-column prop="name" label="角色" />
                  <el-table-column prop="slot" label="槽位" width="70" />
                  <el-table-column prop="sort_order" label="排序" width="70" />
                  <el-table-column label="操作" width="90">
                    <template #default="{ row: b }">
                      <el-button link type="danger" size="small" @click="unbindOne(b.id)">
                        解绑
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </template>
            </el-table-column>
            <el-table-column prop="user_id" label="QQ" width="120" />
            <el-table-column prop="qq_display_name" label="群昵称" />
            <el-table-column label="账号数" width="80">
              <template #default="{ row }">{{ row.bindings?.length || 0 }}</template>
            </el-table-column>
          </el-table>

          <div class="section-label mt-16">批量绑定</div>
          <div class="dual-panels">
            <div class="panel">
              <el-input v-model="qqSearch" placeholder="搜索 QQ 昵称/号码" clearable class="mb-8" />
              <el-table
                ref="qqTableRef"
                :data="filteredQqMembers"
                v-loading="loadingQq"
                max-height="320"
                :row-class-name="qqRowClass"
                @selection-change="onQqSelection"
              >
                <el-table-column type="selection" width="45" />
                <el-table-column prop="display_name" label="昵称" />
                <el-table-column prop="user_id" label="QQ" width="120" />
                <el-table-column label="" width="72">
                  <template #default="{ row }">
                    <el-button link type="info" size="small" @click="hideQq(row.user_id)">
                      隐藏
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div class="panel">
              <el-input v-model="uidSearch" placeholder="搜索角色名/UID" clearable class="mb-8" />
              <el-table
                ref="uidTableRef"
                :data="filteredClanAccounts"
                v-loading="loadingClan"
                max-height="320"
                :row-class-name="uidRowClass"
                @selection-change="onUidSelection"
              >
                <el-table-column type="selection" width="45" />
                <el-table-column prop="name" label="角色" />
                <el-table-column prop="viewer_id" label="UID" width="120" />
              </el-table>
            </div>
          </div>
          <el-button type="primary" class="mt-12" :loading="batchLoading" @click="submitBatch">
            绑定选中
          </el-button>
        </el-tab-pane>

        <el-tab-pane label="出刀修正">
          <div class="kanna-card form-inline">
            <el-input v-model="correct.dao_id" placeholder="出刀编号" style="width: 140px" />
            <el-select v-model="correct.type" style="width: 120px">
              <el-option label="完整刀" value="完整刀" />
              <el-option label="尾刀" value="尾刀" />
              <el-option label="补偿刀" value="补偿刀" />
            </el-select>
            <el-input v-model="correct.group_id" placeholder="群号" style="width: 140px" />
            <el-button type="primary" @click="submitCorrect">提交</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="操作日志">
          <el-table :data="logs" stripe max-height="520">
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ formatTime(row.time) }}</template>
            </el-table-column>
            <el-table-column prop="kind" label="类型" width="100" />
            <el-table-column prop="group_id" label="群" width="100" />
            <el-table-column prop="message" label="内容" />
          </el-table>
          <el-button class="mt-12" @click="loadLogs">刷新</el-button>
        </el-tab-pane>

        <el-tab-pane v-if="userStore.isSuperAdmin" label="任命管理员">
          <el-alert type="info" show-icon :closable="false" class="mb-12">
            超级管理员仅配置项 admin_qq；委派管理员最多 5 人。
          </el-alert>
          <el-table :data="delegatedAdmins" stripe>
            <el-table-column prop="qq_id" label="QQ" width="140" />
            <el-table-column prop="appointed_at" label="任命时间戳" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="revoke(row.qq_id)">
                  撤销
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="form-inline mt-12">
            <el-input v-model="appointQq" placeholder="新管理员 QQ" style="width: 180px" />
            <el-button type="primary" @click="submitAppoint">任命</el-button>
            <el-button @click="loadDelegated">刷新</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  appointDelegatedAdmin,
  correctDao,
  deleteAdminBinding,
  getAdminBindings,
  getAdminBindingsIndex,
  getAdminBindingGroups,
  getAdminClanAccounts,
  getAdminDelegatedAdmins,
  getAdminLogs,
  getAdminMonitor,
  getAdminQqMembers,
  postAdminBatchBindings,
  revokeDelegatedAdmin,
} from '@/api'
import { useUserStore } from '@/store/user'
import type { DaoFlagType } from '@/types'

const userStore = useUserStore()
const monitors = ref<any[]>([])
const bindingsGrouped = ref<any[]>([])
const logs = ref<any[]>([])
const delegatedAdmins = ref<any[]>([])
const loadingMonitor = ref(false)
const loadingBind = ref(false)
const loadingQq = ref(false)
const loadingClan = ref(false)
const batchLoading = ref(false)
const appointQq = ref('')
const opsGroupId = ref('')
const bindingGroups = ref<{ group_id: number; group_name: string }[]>([])
const qqMembers = ref<any[]>([])
const clanAccounts = ref<any[]>([])
const qqSearch = ref('')
const uidSearch = ref('')
const selectedQq = ref<any[]>([])
const selectedUid = ref<any[]>([])
const boundUserIds = ref<Set<number>>(new Set())
const boundViewerIds = ref<Set<number>>(new Set())
const hiddenQqIds = ref<Set<number>>(new Set())

function zhCompare(a: string, b: string) {
  return a.localeCompare(b, 'zh-CN')
}

function qqRowClass({ row }: { row: { user_id: number } }) {
  return boundUserIds.value.has(Number(row.user_id)) ? 'row-bound' : ''
}

function uidRowClass({ row }: { row: { viewer_id: number } }) {
  return boundViewerIds.value.has(Number(row.viewer_id)) ? 'row-bound' : ''
}

function hideQq(userId: number) {
  hiddenQqIds.value = new Set([...hiddenQqIds.value, Number(userId)])
}

const correct = reactive<{
  dao_id: string
  type: DaoFlagType
  group_id: string
}>({ dao_id: '', type: '完整刀', group_id: '' })

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleString()
}

const filteredQqMembers = computed(() => {
  const q = qqSearch.value.trim().toLowerCase()
  let list = qqMembers.value.filter((m) => !hiddenQqIds.value.has(Number(m.user_id)))
  if (q) {
    list = list.filter(
      (m) =>
        String(m.user_id).includes(q) ||
        (m.display_name || '').toLowerCase().includes(q)
    )
  }
  return [...list].sort((a, b) =>
    zhCompare(String(a.display_name || ''), String(b.display_name || ''))
  )
})

const filteredClanAccounts = computed(() => {
  const q = uidSearch.value.trim().toLowerCase()
  let list = clanAccounts.value
  if (q) {
    list = list.filter(
      (m) =>
        String(m.viewer_id).includes(q) ||
        (m.name || '').toLowerCase().includes(q)
    )
  }
  return [...list].sort((a, b) =>
    zhCompare(String(a.name || ''), String(b.name || ''))
  )
})

function opsGidNum(): number | undefined {
  const n = Number(opsGroupId.value)
  return n > 0 ? n : undefined
}

async function loadBindingGroups() {
  try {
    bindingGroups.value = await getAdminBindingGroups()
  } catch {
    bindingGroups.value = []
  }
}

function pickDefaultOpsGroup() {
  if (opsGroupId.value) return
  const fromClan = userStore.currentClanId
  if (fromClan) {
    opsGroupId.value = String(fromClan)
    return
  }
  const mon = monitors.value.find((m) => m.active)
  if (mon?.group_id) {
    opsGroupId.value = String(mon.group_id)
    return
  }
  if (bindingGroups.value.length) {
    opsGroupId.value = String(bindingGroups.value[0].group_id)
  }
}

async function loadMonitor() {
  loadingMonitor.value = true
  try {
    monitors.value = await getAdminMonitor()
  } finally {
    loadingMonitor.value = false
  }
  pickDefaultOpsGroup()
}

async function loadBindings() {
  loadingBind.value = true
  try {
    bindingsGrouped.value = await getAdminBindings(opsGidNum())
  } finally {
    loadingBind.value = false
  }
}

async function loadQqMembers() {
  const gid = opsGidNum()
  if (!gid) {
    qqMembers.value = []
    return
  }
  loadingQq.value = true
  try {
    qqMembers.value = await getAdminQqMembers(gid)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '拉取 QQ 成员失败')
    qqMembers.value = []
  } finally {
    loadingQq.value = false
  }
}

async function loadClanAccounts() {
  const gid = opsGidNum()
  if (!gid) {
    clanAccounts.value = []
    return
  }
  loadingClan.value = true
  try {
    clanAccounts.value = await getAdminClanAccounts(gid)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '拉取公会角色失败（请先开启监控）')
    clanAccounts.value = []
  } finally {
    loadingClan.value = false
  }
}

async function loadBindingIndex() {
  try {
    const idx = await getAdminBindingsIndex()
    boundUserIds.value = new Set((idx.bound_user_ids || []).map(Number))
    boundViewerIds.value = new Set((idx.bound_viewer_ids || []).map(Number))
  } catch {
    boundUserIds.value = new Set()
    boundViewerIds.value = new Set()
  }
}

async function reloadBindingWorkbench() {
  hiddenQqIds.value = new Set()
  await Promise.all([
    loadBindings(),
    loadQqMembers(),
    loadClanAccounts(),
    loadBindingIndex(),
  ])
}

function onOpsGroupChange() {
  reloadBindingWorkbench()
}

function onQqSelection(rows: any[]) {
  selectedQq.value = rows
}

function onUidSelection(rows: any[]) {
  selectedUid.value = rows
}

async function submitBatch() {
  const gid = opsGidNum()
  if (!gid) {
    ElMessage.warning('请先选择运维群')
    return
  }
  const user_ids = selectedQq.value.map((r) => Number(r.user_id))
  const viewer_ids = selectedUid.value.map((r) => Number(r.viewer_id))
  if (!user_ids.length || !viewer_ids.length) {
    ElMessage.warning('请两侧各至少选择一项')
    return
  }
  batchLoading.value = true
  try {
    const res = await postAdminBatchBindings({ user_ids, viewer_ids, group_id: gid })
    const fail = res.failed?.length || 0
    const skip = res.skipped || 0
    let msg = `新增 ${res.ok} 条`
    if (skip) msg += `，跳过 ${skip} 条（已有绑定）`
    if (fail) msg += `，失败 ${fail} 条`
    ElMessage.success(msg)
    await reloadBindingWorkbench()
  } finally {
    batchLoading.value = false
  }
}

async function unbindOne(bindingId: number) {
  await deleteAdminBinding(bindingId)
  ElMessage.success('已解绑')
  await loadBindings()
}

async function loadLogs() {
  logs.value = await getAdminLogs(opsGidNum())
}

async function loadDelegated() {
  if (!userStore.isSuperAdmin) return
  delegatedAdmins.value = await getAdminDelegatedAdmins()
}

async function submitCorrect() {
  const gid = Number(correct.group_id)
  const did = Number(correct.dao_id)
  if (!gid || !did) {
    ElMessage.warning('请填写群号与出刀编号')
    return
  }
  await correctDao({ dao_id: did, type: correct.type, group_id: gid })
  ElMessage.success('已修正')
}

async function submitAppoint() {
  const qq = Number(appointQq.value)
  if (!qq) {
    ElMessage.warning('请输入 QQ')
    return
  }
  await appointDelegatedAdmin(qq)
  ElMessage.success('已任命')
  appointQq.value = ''
  await loadDelegated()
}

async function revoke(qqId: number) {
  await revokeDelegatedAdmin(qqId)
  ElMessage.success('已撤销')
  await loadDelegated()
}

onMounted(async () => {
  if (userStore.isGlobalAdmin) {
    await loadBindingGroups()
    await loadMonitor()
    loadLogs()
    loadDelegated()
    pickDefaultOpsGroup()
    if (opsGroupId.value) {
      await reloadBindingWorkbench()
    }
  }
})
</script>

<style scoped>
.page-wrap {
  padding: 8px;
}
.form-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px;
  align-items: center;
}
.mt-12 {
  margin-top: 12px;
}
.mb-12 {
  margin-bottom: 12px;
}
.mb-16 {
  margin-bottom: 16px;
}
.mt-16 {
  margin-top: 16px;
}
.section-label {
  font-weight: 600;
  margin-bottom: 8px;
}
.dual-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.panel {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
}
.mb-8 {
  margin-bottom: 8px;
}
@media (max-width: 900px) {
  .dual-panels {
    grid-template-columns: 1fr;
  }
}
:deep(.row-bound) {
  background-color: var(--el-fill-color-light) !important;
}
</style>
