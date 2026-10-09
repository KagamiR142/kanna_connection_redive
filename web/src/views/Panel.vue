<template>
  <div class="panel-page">
    <el-empty v-if="!groupId" description="请先在顶栏选择公会" />

    <template v-else>
      <div class="toolbar kanna-card">
        <el-tag :type="stateTag">{{ data.state || '未开启' }}</el-tag>
        <span class="clan-name">{{ data.clan_name || '未知公会' }}</span>
        <span>{{ data.stage }}</span>
        <span>第 {{ data.day_num ?? 0 }} 天</span>
        <span v-if="data.rank">排名 {{ data.rank }}</span>

        <el-button size="small" :loading="statusImageLoading" @click="openStatusImage">
          会战状态图
        </el-button>
        <template v-if="isOpsAdmin">
          <el-button
            v-if="monitorOn"
            size="small"
            type="danger"
            :loading="monitorLoading"
            @click="switchMonitorOff"
          >
            关闭监控
          </el-button>
          <el-button
            v-else
            size="small"
            type="success"
            :loading="monitorLoading"
            @click="openMonitorDialog"
          >
            开启监控
          </el-button>
        </template>
      </div>

      <el-row :gutter="16" class="boss-row">
        <el-col v-for="boss in data.bosses" :key="boss.order" :xs="24" :sm="12" :md="8">
          <div class="boss-card kanna-card">
            <div class="boss-head">
              <img
                v-if="boss.id && !imgFail[boss.order]"
                class="boss-avatar"
                :src="avatarSrc(boss)"
                alt=""
                @error="onImgError(boss)"
              />
              <div v-else class="boss-avatar fallback">{{ boss.order }}</div>
              <div>
                <div class="boss-title">{{ boss.order }}王 · {{ boss.name }}</div>
                <div v-if="boss.lap">{{ boss.lap }} 周目</div>
              </div>
              <el-tag v-if="boss.is_behind" type="warning" size="small">落后</el-tag>
            </div>
            <el-progress
              v-if="boss.max_hp"
              :percentage="hpPercent(boss)"
              :stroke-width="12"
              :show-text="false"
            />
            <div class="boss-meta">
              <span>战斗 {{ boss.fighter ?? 0 }}</span>
              <span>预约 {{ boss.subscribe ?? 0 }}</span>
              <span>申请 {{ boss.apply ?? 0 }}</span>
              <span>挂树 {{ boss.tree ?? 0 }}</span>
            </div>
            <div v-if="boss.challenge?.length" class="challenge-list">
              <div v-for="(c, i) in boss.challenge" :key="'c' + i">{{ c }}</div>
            </div>
            <div v-if="boss.unknown?.length" class="unknown-list">
              <div v-for="(u, i) in boss.unknown" :key="'u' + i">{{ u }}</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <div class="member-bar kanna-card mt-16">
        <el-button size="small" type="primary" @click="noticeDialog = true">添加通知</el-button>
        <span class="hint">Web 操作不会向 QQ 群发送消息</span>
      </div>

      <el-tabs v-model="queueTab" class="mt-16">
        <el-tab-pane label="预约" name="subscribe">
          <el-table :data="queueRows('subscribe')" stripe empty-text="暂无">
            <el-table-column prop="display_label" label="成员" min-width="140" />
            <el-table-column prop="boss" label="Boss" width="70" />
            <el-table-column prop="lap" label="周目" width="70" />
            <el-table-column prop="text" label="留言" />
            <el-table-column v-if="isOpsAdmin" label="操作" width="90">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="delRow(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="申请" name="apply">
          <el-table :data="queueRows('apply')" stripe empty-text="暂无">
            <el-table-column prop="display_label" label="成员" min-width="140" />
            <el-table-column prop="boss" label="Boss" width="70" />
            <el-table-column prop="text" label="留言" />
            <el-table-column v-if="isOpsAdmin" label="操作" width="90">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="delRow(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="挂树" name="tree">
          <el-table :data="queueRows('tree')" stripe empty-text="暂无">
            <el-table-column prop="display_label" label="成员" min-width="140" />
            <el-table-column prop="boss" label="Boss" width="70" />
            <el-table-column label="挂树时长" width="100">
              <template #default="{ row }">
                {{ row.hang_seconds != null ? `${row.hang_seconds}s` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="text" label="留言" />
            <el-table-column v-if="isOpsAdmin" label="操作" width="90">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="delRow(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-dialog v-model="noticeDialog" title="添加通知" width="420px">
      <el-form label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="noticeForm.notice_type" style="width: 100%">
            <el-option label="预约" :value="0" />
            <el-option label="挂树" :value="1" />
            <el-option label="申请出刀" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="Boss">
          <el-input-number v-model="noticeForm.boss" :min="1" :max="5" />
        </el-form-item>
        <el-form-item v-if="noticeForm.notice_type === 0" label="周目">
          <el-input-number v-model="noticeForm.lap" :min="0" />
        </el-form-item>
        <el-form-item label="留言">
          <el-input v-model="noticeForm.text" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="noticeDialog = false">取消</el-button>
        <el-button type="primary" @click="submitNotice">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="statusImageDialog"
      title="会战状态图"
      width="min(860px, 96vw)"
      destroy-on-close
      @closed="revokeStatusImageUrl"
    >
      <div v-loading="statusImageLoading" class="status-image-wrap">
        <img v-if="statusImageUrl" :src="statusImageUrl" alt="会战状态" class="status-image" />
      </div>
    </el-dialog>

    <el-dialog v-model="monitorDialog" title="选择监控账号" width="400px">
      <el-select v-model="monitorAccountId" placeholder="账号" style="width: 100%">
        <el-option
          v-for="a in monitorAccounts"
          :key="a.account_id"
          :label="`${a.name} (${a.viewer_id})`"
          :value="a.account_id"
        />
      </el-select>
      <template #footer>
        <el-button @click="monitorDialog = false">取消</el-button>
        <el-button type="primary" :loading="monitorLoading" @click="confirmMonitor">开启</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { bossAvatarFallback, bossAvatarPrimary } from '@/utils/bossAvatar'
import {
  deleteNoticeById,
  getMonitorAccounts,
  fetchStatusImageBlob,
  getPanel,
  setNotice,
  toggleMonitor,
} from '@/api'
import { useUserStore } from '@/store/user'

const route = useRoute()
const userStore = useUserStore()
const groupId = computed(() => Number(route.params.groupId) || 0)

const data = ref<any>({ bosses: [], queues: {}, state: '关闭' })
const queueTab = ref('apply')
const monitorLoading = ref(false)
const monitorDialog = ref(false)
const monitorAccountId = ref<number>()
const monitorAccounts = ref<any[]>([])
const statusImageDialog = ref(false)
const statusImageLoading = ref(false)
const statusImageUrl = ref('')
const noticeDialog = ref(false)
const noticeForm = ref({
  notice_type: 2,
  boss: 1,
  lap: 0,
  text: '',
})
const imgFail = ref<Record<number, boolean>>({})
const imgFallback = ref<Record<number, boolean>>({})
let panelEs: EventSource | undefined
const API_BASE = import.meta.env.VITE_API_BASE || '/kanna_dependency'

const isOpsAdmin = computed(() => userStore.isGlobalAdmin)
const monitorOn = computed(() => String(data.value.state || '').includes('开启'))
const stateTag = computed(() => (monitorOn.value ? 'success' : 'info'))

function queueRows(field: string) {
  const q = data.value.queues || {}
  const out: any[] = []
  for (let b = 1; b <= 5; b++) {
    out.push(...(q[String(b)]?.[field] || []))
  }
  return out
}

function hpPercent(boss: any) {
  if (!boss.max_hp) return 0
  return Math.min(100, Math.round((boss.current_hp / boss.max_hp) * 100))
}

function avatarSrc(boss: any) {
  if (imgFallback.value[boss.order]) return bossAvatarFallback(boss.id)
  return bossAvatarPrimary(boss.id)
}

function onImgError(boss: any) {
  if (!imgFallback.value[boss.order]) {
    imgFallback.value[boss.order] = true
  } else {
    imgFail.value[boss.order] = true
  }
}

async function loadPanel() {
  if (!groupId.value) return
  data.value = await getPanel(groupId.value)
}

function revokeStatusImageUrl() {
  if (statusImageUrl.value) {
    URL.revokeObjectURL(statusImageUrl.value)
    statusImageUrl.value = ''
  }
}

async function openStatusImage() {
  if (!groupId.value) return
  revokeStatusImageUrl()
  statusImageDialog.value = true
  statusImageLoading.value = true
  try {
    const blob = await fetchStatusImageBlob(groupId.value)
    statusImageUrl.value = URL.createObjectURL(blob)
  } catch {
    statusImageDialog.value = false
  } finally {
    statusImageLoading.value = false
  }
}

async function openMonitorDialog() {
  monitorAccounts.value = await getMonitorAccounts(groupId.value)
  if (!monitorAccounts.value.length) {
    ElMessage.warning('请先在 QQ 私聊绑定用于监控的游戏账号')
    return
  }
  monitorAccountId.value = monitorAccounts.value[0].account_id
  monitorDialog.value = true
}

async function confirmMonitor() {
  if (!monitorAccountId.value) return
  monitorLoading.value = true
  try {
    await toggleMonitor(groupId.value, { action: 'on', account_id: monitorAccountId.value })
    monitorDialog.value = false
    ElMessage.success('监控已开启')
    await loadPanel()
  } finally {
    monitorLoading.value = false
  }
}

async function switchMonitorOff() {
  monitorLoading.value = true
  try {
    await toggleMonitor(groupId.value, { action: 'off' })
    ElMessage.success('监控已关闭')
    await loadPanel()
  } finally {
    monitorLoading.value = false
  }
}

async function submitNotice() {
  await setNotice({
    group_id: groupId.value,
    user_id: userStore.userId,
    notice_type: noticeForm.value.notice_type,
    boss: noticeForm.value.boss,
    lap: noticeForm.value.lap || 0,
    text: noticeForm.value.text || '',
  } as any)
  noticeDialog.value = false
  ElMessage.success('已添加（静默，不群发）')
  await loadPanel()
}

async function delRow(row: any) {
  if (!row.id) return
  await deleteNoticeById(groupId.value, row.id)
  ElMessage.success('已删除')
  await loadPanel()
}

function connectPanelStream() {
  panelEs?.close()
  if (!groupId.value) return
  const url = `${API_BASE}/${groupId.value}/panel/stream`
  panelEs = new EventSource(url, { withCredentials: true })
  panelEs.onmessage = (ev) => {
    try {
      data.value = JSON.parse(ev.data)
    } catch {
      /* ignore malformed chunk */
    }
  }
  panelEs.onerror = () => {
    panelEs?.close()
    window.setTimeout(connectPanelStream, 5000)
  }
}

watch(groupId, () => {
  loadPanel()
  connectPanelStream()
})

onMounted(() => {
  loadPanel()
  connectPanelStream()
})

onUnmounted(() => {
  panelEs?.close()
  revokeStatusImageUrl()
})
</script>

<style scoped>
.panel-page {
  padding: 8px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.clan-name {
  font-weight: 600;
}
.boss-card {
  padding: 14px;
  margin-bottom: 16px;
}
.boss-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.boss-avatar {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
}
.boss-avatar.fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fce7f3;
  font-weight: 700;
}
.boss-title {
  font-weight: 600;
}
.boss-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
  margin-top: 8px;
}
.challenge-list,
.unknown-list {
  font-size: 12px;
  margin-top: 6px;
  color: #374151;
}
.unknown-list {
  color: #b45309;
}
.mt-16 {
  margin-top: 16px;
}
.status-image-wrap {
  min-height: 120px;
  text-align: center;
}
.status-image {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
.member-bar {
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.member-bar .hint {
  font-size: 12px;
  color: #6b7280;
}
</style>
