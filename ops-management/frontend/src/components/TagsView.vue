<template>
  <div class="tags-view">
    <div class="tags-scroll">
      <div
        v-for="tag in items"
        :key="tag.path"
        class="tag-item"
        :class="{ active: tag.path === active, fixed: tag.fixed }"
        @click="$emit('change', tag.path)"
      >
        <span class="dot"></span>
        <span class="label">{{ tag.title }}</span>
        <el-icon v-if="!tag.fixed" class="close" @click.stop="$emit('close', tag.path)">
          <Close />
        </el-icon>
      </div>
    </div>
    <div class="tags-tools">
      <el-tooltip :content="isFavorited ? t('home.unfavorite') : t('home.favorite')" placement="bottom">
        <el-button link class="tool-star" :class="{ 'is-fav': isFavorited }" @click="$emit('toggle-favorite')">
          <el-icon><Star /></el-icon>
        </el-button>
      </el-tooltip>
      <el-dropdown trigger="click" @command="onCommand">
        <el-button type="primary" size="small" class="opt-btn">
          {{ t('home.tabOptions') }} <el-icon><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="close-all">{{ t('home.closeAllTabs') }}</el-dropdown-item>
            <el-dropdown-item command="close-other">{{ t('home.closeOtherTabs') }}</el-dropdown-item>
            <el-dropdown-item command="favorite" divided>{{ t('home.favoriteConfig') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { Close, Star, ArrowDown } from '@element-plus/icons-vue'

defineProps({
  items: { type: Array, default: () => [] },
  active: { type: String, default: '' },
  isFavorited: { type: Boolean, default: false },
})
const emit = defineEmits(['change', 'close', 'close-all', 'close-other', 'favorite', 'toggle-favorite'])
const { t } = useI18n()

function onCommand(cmd) { emit(cmd) }
</script>

<style scoped>
.tags-view {
  height: 38px;
  flex: none;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 10px;
}
.tags-scroll {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  overflow-y: hidden;
  flex: 1;
  scrollbar-width: none;
}
.tags-scroll::-webkit-scrollbar { display: none; }
.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 9px;
  border-radius: 4px;
  background: #f1f3f5;
  color: #5c6570;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  flex: none;
  transition: background .15s, color .15s;
  user-select: none;
}
.tag-item:hover { background: #e8eaed; }
.tag-item.active { background: #e8f3ff; color: #2563eb; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #b9c0c8; flex: none; }
.tag-item.active .dot { background: #2563eb; }
.close { font-size: 12px; color: #9aa2ab; border-radius: 50%; }
.close:hover { color: #f56c6c; background: rgba(0, 0, 0, .06); }
.tags-tools { display: flex; align-items: center; gap: 8px; flex: none; }
.tool-star { font-size: 17px; color: #c0c4cc; }
.tool-star.is-fav { color: #f7b500; }
.opt-btn { height: 26px; padding: 0 10px; font-size: 12px; }
</style>
