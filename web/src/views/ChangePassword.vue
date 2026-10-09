<template>
  <div class="page-wrap">
    <div class="kanna-card form-card">
      <h2>修改密码</h2>
      <p class="hint">8–20 位，仅大小写字母与数字</p>
      <el-form :model="form" label-position="top" @submit.prevent="submit">
        <el-form-item label="旧密码">
          <el-input v-model="form.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="submit">保存</el-button>
          <el-button @click="$router.back()">返回</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePassword } from '@/api'
import { useUserStore } from '@/store/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const form = reactive({ old_password: '', new_password: '' })

async function submit() {
  if (!/^[A-Za-z0-9]{8,20}$/.test(form.new_password)) {
    ElMessage.warning('新密码须为 8–20 位字母或数字')
    return
  }
  loading.value = true
  try {
    await changePassword(form)
    ElMessage.success('密码已修改')
    userStore.isInitialPassword = false
    await router.push('/home')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page-wrap {
  max-width: 480px;
  margin: 0 auto;
}
.form-card {
  padding: 24px;
}
.hint {
  color: #6b7280;
  margin-bottom: 16px;
}
</style>
