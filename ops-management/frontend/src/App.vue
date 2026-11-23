<template>
  <el-config-provider :locale="elLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'

const { locale } = useI18n()
// Element Plus 组件（分页器、空数据、日期选择器等）文案跟随语言切换
const elLocale = computed(() => (locale.value === 'enUS' ? en : zhCn))
</script>

<style>
</style>
