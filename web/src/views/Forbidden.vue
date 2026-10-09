<template>
  <div class="forbidden-wrap">
    <el-result icon="warning" title="403" sub-title="需要会战管理员权限（超级管理员或已任命的管理员）">
      <template #extra>
        <el-button type="primary" @click="$router.push('/home')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.forbidden-wrap {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
