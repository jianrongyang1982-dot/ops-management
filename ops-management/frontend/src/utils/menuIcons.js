import {
  Box, DataBoard, TrendCharts, Setting, User, Connection, OfficeBuilding,
  Grid, Shop, ShoppingCart, Bell, Document, Tools, Lock, House, Star,
} from '@element-plus/icons-vue'

// 数据库 menu.icon -> Element Plus 图标组件
export const MENU_ICONS = {
  Box, DataBoard, TrendCharts, Setting, User, Connection, OfficeBuilding,
  Grid, Shop, ShoppingCart, Bell, Document, Tools, Lock, House, Star,
}

export function menuIcon(name) {
  return MENU_ICONS[name] || Document
}
