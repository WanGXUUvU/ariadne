<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import type { ApprovalInfo } from '../../types';

interface GroupedToolExecution {
  id: string;
  tool_name: string;
  status: 'running' | 'success' | 'error' | 'awaiting_approval';
  args: any;
  result?: any;
  error?: string;
  duration: string;
  groupCount?: number;
}

const props = defineProps<{
  exec: GroupedToolExecution;
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  isProcessingApproval?: boolean;
}>();

const emit = defineEmits<{
  (e: 'approve'): void;
  (e: 'reject'): void;
  (e: 'approve-all'): void;
}>();

const isExpanded = ref(false);

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value;
};

const formatJson = (val: any): string => {
  if (typeof val === 'string') {
    try {
      return JSON.stringify(JSON.parse(val), null, 2);
    } catch {
      return val;
    }
  }
  if (val && typeof val === 'object') {
    return JSON.stringify(val, null, 2);
  }
  return String(val);
};

// Check if this specific tool card is currently waiting for approval
const isThisWaitingApproval = computed(() => {
  if (props.exec.status === 'awaiting_approval') return true;
  if (props.isAwaitingApproval && props.pendingApprovalInfo) {
    const pInfo = props.pendingApprovalInfo;
    const cid = pInfo.tool_call_id;
    if (cid && cid === props.exec.id) return true;
    if (!cid && pInfo.tool_name === props.exec.tool_name) return true;
  }
  return false;
});

// Code block copy handling
const copyState = ref<Record<string, boolean>>({});
const handleCopy = (key: string, text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    copyState.value = { ...copyState.value, [key]: true };
    setTimeout(() => {
      copyState.value = { ...copyState.value, [key]: false };
    }, 2000);
  }).catch(err => {
    console.error('Copy failed:', err);
  });
};

/* ==================== 🦊 CUTE ANIMAL & WITTY TOOL AESTHETICS ==================== */
interface ToolAesthetic {
  icon: string;
  emoji: string;
  successText: string;
  errorText: string;
  pendingText: string;
  runningCycles: string[];
}

const toolAestheticMap: Record<string, ToolAesthetic> = {
  // Writing files
  write_file: {
    icon: '✍️',
    emoji: '🐹',
    successText: '仓鼠小工写完啦！签字画押完成！',
    errorText: '仓鼠小工笔头折断了... 写入失败！',
    pendingText: '仓鼠小工正叼着铅笔，等您画押授权...',
    runningCycles: [
      '🐹 仓鼠小工正在铺平白纸...',
      '✍️ 仓鼠小工正在奋笔疾书...',
      '💨 墨汁未干，仓鼠在努力吹气烘干...',
      '📦 正在封档，盖上红色小手掌印...'
    ]
  },
  replace_file_content: {
    icon: '✂️',
    emoji: '🦫',
    successText: '海狸工程师修剪完毕！滴水不漏！',
    errorText: '海狸工程师啃错木头了... 修改失败！',
    pendingText: '海狸工程师咬着图纸，等您批准动工...',
    runningCycles: [
      '🦫 海狸工程师正在校准新旧蓝图...',
      '🛠️ 海狸工程师正在精准啃食木头...',
      '🧱 叮叮当当... 精密拼图咬合中...',
      '✨ 海狸正在用尾巴给代码抛光打蜡...'
    ]
  },
  multi_replace_file_content: {
    icon: '✂️',
    emoji: '🦫',
    successText: '海狸施工队多点修改完成！大坝完美咬合！',
    errorText: '大坝遭遇洪峰... 批量修改失败！',
    pendingText: '海狸施工队已经安放好路障，等您下达总攻令...',
    runningCycles: [
      '🦫 几只小海狸正在商讨施工队形...',
      '🪵 叮叮哐哐！分头啃食旧代码木料...',
      '🧱 水坝多点加固中，严丝合缝...',
      '🌟 施工队收工整理工具，向您敬礼...'
    ]
  },
  // Reading files
  view_file: {
    icon: '🔍',
    emoji: '🐱',
    successText: '橘猫警长看完啦！脑补吸收完成！',
    errorText: '橘猫警长眼睛看花了... 读取失败！',
    pendingText: '橘猫警长正咬着放大镜，等您翻开机密卷宗...',
    runningCycles: [
      '🐱 橘猫警长揉了揉惺忪的睡眼...',
      '🔍 戴上单片金丝眼镜，拿好放大镜...',
      '📄 刷刷刷... 聚精会神翻阅文件...',
      '💡 脑电波高度震荡，正在提取记忆...'
    ]
  },
  list_dir: {
    icon: '📁',
    emoji: '🐿️',
    successText: '松鼠特工把树洞里的家当数了一遍！',
    errorText: '树洞坍塌了... 盘点储粮点失败！',
    pendingText: '松鼠特工正站在树梢上，等您下达搜山指令...',
    runningCycles: [
      '🐿️ 松鼠特工背上小背包，开始爬树...',
      '🥜 扒拉树洞，清点藏匿的松果松子...',
      '🗺️ 正在连线绘制仓储藏宝地图...',
      '✨ 盘点完毕！松果码放得整整齐齐...'
    ]
  },
  // Searching
  grep_search: {
    icon: '🔎',
    emoji: '🐶',
    successText: '汪汪队立大功！关键词全部揪出来了！',
    errorText: '汪汪队刨了半天打了个喷嚏... 搜寻失败！',
    pendingText: '汪汪队正急切地摇尾巴，等您核准搜索范围...',
    runningCycles: [
      '🐶 汪汪队紧急集合！大家闻一闻气味...',
      '🐾 在草丛和代码堆里仔细刨土搜寻...',
      '🔎 发现一处可疑的脚印，汪汪低吼...',
      '🎉 找到了！正在兴奋打滚摇尾巴...'
    ]
  },
  web_search: {
    icon: '🌐',
    emoji: '🦅',
    successText: '信鸽掠过千山万水，衔回了全网军情！',
    errorText: '信鸽撞上海防电磁波... 联网搜索失败！',
    pendingText: '信鸽已经梳理好羽毛，等您系上搜寻信笺...',
    runningCycles: [
      '🦅 信鸽扑棱着翅膀腾空而起...',
      '🌐 掠过宽带网线与光纤，飞入路由器云端...',
      '📑 正在全网情报堆里疯狂叼取有用的树枝...',
      '🌟 凯旋返航！带回最新的云端快报...'
    ]
  },
  // Terminal commands
  run_command: {
    icon: '⚙️',
    emoji: '🐒',
    successText: '猴子工程师运行结束，稳如老狗！',
    errorText: '指令炸了！猴子工程师被静电电了一下...',
    pendingText: '猴子工程师蹲在红按钮旁，等您点头授权启动...',
    runningCycles: [
      '🐒 猴子工程师戴好安全帽，手握大扳手...',
      '⚙️ 机械仓鼠进入跑轮，疯狂奔跑发电...',
      '⚡ 引擎点火！高压指令在主板电线上狂飙...',
      '🔥 火花带闪电，终端终端指令突突突狂奔...'
    ]
  },
  // Summons
  invoke_subagent: {
    icon: '🔮',
    emoji: '🐝',
    successText: '分身小蜜蜂回报！子任务圆满解决！',
    errorText: '分身小蜜蜂失联在远方... 任务失败！',
    pendingText: '小蜜蜂队长正整队，等您盖章发放出征特赦令...',
    runningCycles: [
      '🔮 魔法阵亮起，正在念动嗡嗡召唤咒语...',
      '🐝 呼叫小蜜蜂特别行动队前来集结...',
      '🤝 小蜜蜂带上微缩工具箱，飞往远方子节点...',
      '📈 分工完毕，协同蜂群网络全速开动...'
    ]
  },
  define_subagent: {
    icon: '🤖',
    emoji: '🐝',
    successText: '分身小蜜蜂特工设计完成！蓄势待发！',
    errorText: '孵化舱断电... 分身特工定义失败！',
    pendingText: '蜜蜂基因孵化器就绪，等您录入特工专属性格...',
    runningCycles: [
      '🤖 正在绘制蜜蜂分身的精密集成图纸...',
      '🧬 组装微型传感器，拼装钛合金翅膀...',
      '🔋 能量池灌注，蜜蜂触角滋滋放电...',
      '🎉 叮！新一代小蜜蜂特工破茧而出...'
    ]
  }
};

const defaultAesthetic: ToolAesthetic = {
  icon: '🛠️',
  emoji: '🤖',
  successText: '小助手运行成功！',
  errorText: '小助手出错了... 执行失败！',
  pendingText: '小助手在原地踏步，等您的金手指授权...',
  runningCycles: [
    '🤖 正在装配零件...',
    '⚙️ 齿轮咬合，滋滋滋...',
    '⚡ 指令狂飙中...',
    '✨ 正在收工整理...'
  ]
};

// 动画文本轮播控制
const currentCycleIndex = ref(0);
let cycleInterval: any = null;

const startCycling = (cycles: string[]) => {
  stopCycling();
  currentCycleIndex.value = 0;
  cycleInterval = setInterval(() => {
    currentCycleIndex.value = (currentCycleIndex.value + 1) % cycles.length;
  }, 2200); // 每 2.2 秒翻页一次，保证舒适的阅读节奏
};

const stopCycling = () => {
  if (cycleInterval) {
    clearInterval(cycleInterval);
    cycleInterval = null;
  }
};

// 监听状态，只有在 running 时开启消息轮播，其余时间清空
watch(() => props.exec.status, (status) => {
  const aest = toolAestheticMap[props.exec.tool_name] || defaultAesthetic;
  if (status === 'running') {
    startCycling(aest.runningCycles);
  } else {
    stopCycling();
  }
}, { immediate: true });

onBeforeUnmount(() => {
  stopCycling();
});

const displayedAesthetic = computed(() => {
  const aest = toolAestheticMap[props.exec.tool_name] || defaultAesthetic;
  const status = props.exec.status;
  
  if (isThisWaitingApproval.value) {
    return {
      icon: aest.icon,
      emoji: aest.emoji,
      text: aest.pendingText
    };
  }
  
  if (status === 'running') {
    return {
      icon: aest.icon,
      emoji: aest.emoji,
      text: aest.runningCycles[currentCycleIndex.value]
    };
  }
  
  if (status === 'success') {
    return {
      icon: aest.icon,
      emoji: aest.emoji,
      text: aest.successText
    };
  }
  
  if (status === 'error') {
    return {
      icon: aest.icon,
      emoji: aest.emoji,
      text: aest.errorText
    };
  }
  
  return {
    icon: aest.icon,
    emoji: aest.emoji,
    text: aest.successText
  };
});
</script>

<template>
  <!-- 连续重复调用：紧凑摘要行 -->
  <div
    v-if="exec.groupCount && exec.groupCount > 1"
    class="tool-exec-card tool-exec-group-summary"
  >
    <!-- 左侧发光状态条 -->
    <div class="tool-status-bar status-success"></div>
    <div class="tool-exec-header">
      <span class="tool-exec-icon-box status-success">
        <span class="cute-emoji-icon">{{ toolAestheticMap[exec.tool_name]?.emoji || '🤖' }}</span>
      </span>
      <span class="tool-exec-name cute-status-text">
        {{ toolAestheticMap[exec.tool_name]?.emoji || '🤖' }} 连续执行了 {{ exec.groupCount }} 次 {{ exec.tool_name }} 操作
      </span>
    </div>
  </div>

  <!-- 单次工具调用或待审批工具调用 -->
  <div
    v-else
    class="tool-exec-card stagger-anim"
    :class="{ 
      'is-expanded': isExpanded || isThisWaitingApproval, 
      'has-error': exec.status === 'error',
      'is-awaiting-approval': isThisWaitingApproval 
    }"
  >
    <!-- 左侧发光状态条 -->
    <div class="tool-status-bar" :class="`status-${isThisWaitingApproval ? 'running' : exec.status}`"></div>

    <!-- 工具头部 -->
    <div class="tool-exec-header" @click="toggleExpand">
      <!-- 动画可爱的 Emoji 盒子 -->
      <span class="tool-exec-icon-box" :class="`status-${isThisWaitingApproval ? 'running' : exec.status}`">
        <span class="cute-emoji-icon">{{ displayedAesthetic.emoji }}</span>
      </span>
      
      <!-- 风趣幽默的执行状态文字（代替冰冷的 write_file 等字样） -->
      <span class="tool-exec-name cute-status-text" :class="`status-${exec.status}`">
        {{ displayedAesthetic.text }}
      </span>
      
      <!-- 运行中状态指示器 -->
      <span v-if="exec.status === 'running'" class="running-indicator">
        <span class="pulse-dot"></span>
      </span>

      <!-- 审批挂起微章 -->
      <span v-else-if="isThisWaitingApproval" class="approval-pulse-badge">
        <span class="pulse-dot-amber"></span>
        PENDING APPROVAL
      </span>

      <div class="tool-exec-meta" @click.stop>
        <span v-if="exec.status === 'error'" class="status-error-label">failed</span>
        <span v-else-if="!isThisWaitingApproval" class="duration-label">{{ exec.duration }}</span>
        
        <button class="header-chevron-btn" @click="toggleExpand">
          <svg class="toggle-chevron" :class="{ open: isExpanded || isThisWaitingApproval }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 工具折叠体内容 -->
    <div class="tool-exec-body" v-if="isExpanded || isThisWaitingApproval">
      <!-- 参数 -->
      <div class="tool-exec-section" v-if="exec.args && Object.keys(exec.args).length > 0">
        <div class="ide-code-container">
          <div class="ide-code-header">
            <div class="mac-control-dots">
              <span class="dot close"></span>
              <span class="dot minimize"></span>
              <span class="dot expand"></span>
            </div>
            <span class="ide-tab-title">parameters.json</span>
            <button class="ide-copy-btn" :class="{ copied: copyState['args'] }" @click="handleCopy('args', formatJson(exec.args))">
              <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" stroke-width="2.5" fill="none">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              <span class="copy-label">{{ copyState['args'] ? 'Copied' : 'Copy' }}</span>
            </button>
          </div>
          <pre class="json-code"><code>{{ formatJson(exec.args) }}</code></pre>
        </div>
      </div>

      <!-- 错误状态 -->
      <div class="tool-exec-section is-error" v-if="exec.status === 'error' && exec.error">
        <div class="section-label">Error Output</div>
        <div class="error-text">{{ exec.error }}</div>
      </div>

      <!-- 正常返回结果 -->
      <div class="tool-exec-section" v-if="exec.status === 'success' && exec.result">
        <div class="ide-code-container">
          <div class="ide-code-header">
            <div class="mac-control-dots">
              <span class="dot close"></span>
              <span class="dot minimize"></span>
              <span class="dot expand"></span>
            </div>
            <span class="ide-tab-title">response.log</span>
            <button class="ide-copy-btn" :class="{ copied: copyState['result'] }" @click="handleCopy('result', formatJson(exec.result))">
              <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" stroke-width="2.5" fill="none">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              <span class="copy-label">{{ copyState['result'] ? 'Copied' : 'Copy' }}</span>
            </button>
          </div>
          <pre class="json-code"><code>{{ formatJson(exec.result) }}</code></pre>
        </div>
      </div>

      <!-- 💡 顶奢级审批交互面板：磨砂拟态、渐变霓虹呼吸边框与对称排版 -->
      <div class="approval-action-block" v-if="isThisWaitingApproval" @click.stop>
        <div class="approval-message">
          <svg class="warning-icon animate-pulse" viewBox="0 0 24 24" width="14" height="14" stroke="var(--warning-amber)" stroke-width="2" fill="none">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          <span class="warning-text">安全拦截：该工具操作包含副作用，需要您的授权。</span>
        </div>

        <div class="approval-buttons-row">
          <!-- 拒绝按钮 -->
          <button 
            class="approval-btn reject-btn" 
            :disabled="isProcessingApproval"
            @click="emit('reject')"
          >
            <span class="btn-hover-glow"></span>
            <span class="btn-text">拒绝 (Reject)</span>
          </button>

          <!-- 全部授权自动运行 -->
          <button 
            class="approval-btn approve-all-btn" 
            :disabled="isProcessingApproval"
            @click="emit('approve-all')"
            title="将权限配置切换为 Full-Auto，本次运行不再拦截任何工具"
          >
            <span class="btn-hover-glow"></span>
            <span class="btn-text">全部授权 (Full Auto)</span>
          </button>

          <!-- 授权单次运行 -->
          <button 
            class="approval-btn approve-btn" 
            :disabled="isProcessingApproval"
            @click="emit('approve')"
          >
            <span class="btn-hover-glow"></span>
            <span class="btn-text">批准 (Approve)</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── 工具调用卡片样式 ── */
.tool-exec-card {
  border-radius: 8px;
  background: color-mix(in srgb, var(--bg-panel) 95%, var(--text-primary));
  border: 1px solid var(--border-dim);
  overflow: hidden;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  margin-bottom: 8px;
  position: relative;
  width: 100%;
}

body.theme-default .tool-exec-card,
body.theme-cyberpunk .tool-exec-card,
body.theme-emerald .tool-exec-card,
body.theme-amber .tool-exec-card {
  background: rgba(255, 255, 255, 0.015);
  border-color: rgba(255, 255, 255, 0.05);
}

.tool-exec-card:hover {
  background: color-mix(in srgb, var(--bg-panel) 92%, var(--text-primary));
  border-color: var(--border-strong);
}

body.theme-default .tool-exec-card:hover,
body.theme-cyberpunk .tool-exec-card:hover,
body.theme-emerald .tool-exec-card:hover,
body.theme-amber .tool-exec-card:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.1);
}

.tool-exec-card.is-expanded {
  background: color-mix(in srgb, var(--bg-panel) 90%, var(--text-primary));
  border-color: var(--border-strong);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
}

body.theme-default .tool-exec-card.is-expanded,
body.theme-cyberpunk .tool-exec-card.is-expanded,
body.theme-emerald .tool-exec-card.is-expanded,
body.theme-amber .tool-exec-card.is-expanded {
  background: rgba(255, 255, 255, 0.025);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.tool-exec-card.has-error {
  background: rgba(255, 69, 58, 0.02);
  border-color: rgba(255, 69, 58, 0.18);
}

.tool-exec-card.has-error:hover {
  border-color: rgba(255, 69, 58, 0.35);
  background: rgba(255, 69, 58, 0.04);
}

.tool-exec-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  position: relative;
}

/* 左侧发光指示线 */
.tool-status-bar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: transparent;
  transition: all 0.2s ease;
}

.tool-status-bar.status-success {
  background: var(--accent-emerald, #34c759);
  box-shadow: 0 0 6px var(--accent-emerald, #34c759);
}

.tool-status-bar.status-running {
  background: var(--warning-amber, #FBBF24);
  box-shadow: 0 0 6px var(--warning-amber, #FBBF24);
}

.tool-status-bar.status-error {
  background: var(--danger, #ff453a);
  box-shadow: 0 0 6px var(--danger, #ff453a);
}

.tool-exec-icon-box {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid var(--border-dim);
  position: relative;
  transition: all 0.2s ease;
}

body.theme-default .tool-exec-icon-box,
body.theme-cyberpunk .tool-exec-icon-box,
body.theme-emerald .tool-exec-icon-box,
body.theme-amber .tool-exec-icon-box {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.06);
}

.tool-exec-icon-box.status-success {
  background: rgba(52, 199, 89, 0.06);
  border-color: rgba(52, 199, 89, 0.15);
}

.tool-exec-icon-box.status-running {
  background: rgba(251, 191, 36, 0.06);
  border-color: rgba(251, 191, 36, 0.15);
}

.tool-exec-icon-box.status-error {
  background: rgba(255, 69, 58, 0.06);
  border-color: rgba(255, 69, 58, 0.15);
}

.tool-exec-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono, monospace);
  flex: 1;
}

/* 风趣幽默的展示文字样式覆盖 */
.cute-status-text {
  font-family: var(--font-sans), system-ui, -apple-system, sans-serif !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  letter-spacing: 0px !important;
  color: var(--text-primary);
  text-transform: none !important;
}

.cute-status-text.status-error {
  color: var(--danger, #ff453a) !important;
}

.cute-emoji-icon {
  font-size: 12px;
  line-height: 1;
}

.running-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--accent-emerald, #34c759);
  box-shadow: 0 0 8px var(--accent-emerald, #34c759);
  animation: pulse 1.6s infinite ease-in-out;
}

.tool-exec-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.status-error-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--danger, #ff453a);
  background: rgba(255, 69, 58, 0.12);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
}

.duration-label {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
}

.header-chevron-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border-radius: 4px;
  transition: all 0.2s ease;
  outline: none;
}

.header-chevron-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.toggle-chevron {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toggle-chevron.open {
  transform: rotate(180deg);
}

.tool-exec-body {
  border-top: 1px solid var(--border-dim);
  padding: 12px;
  background: rgba(0, 0, 0, 0.02);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

body.theme-default .tool-exec-body,
body.theme-cyberpunk .tool-exec-body,
body.theme-emerald .tool-exec-body,
body.theme-amber .tool-exec-body {
  background: rgba(0, 0, 0, 0.12);
  border-top-color: rgba(255, 255, 255, 0.04);
}

.tool-exec-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* --- 💻 HIGH-END macOS IDE CODE CONTAINER --- */
.ide-code-container {
  display: flex;
  flex-direction: column;
  background: #0b0b0e !important;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.ide-code-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #121217 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  user-select: none;
}

.mac-control-dots {
  display: flex;
  gap: 5px;
  align-items: center;
  margin-right: 14px;
}

.mac-control-dots .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  opacity: 0.85;
}

.mac-control-dots .dot.close { background-color: #ff5f56; }
.mac-control-dots .dot.minimize { background-color: #ffbd2e; }
.mac-control-dots .dot.expand { background-color: #27c93f; }

.ide-tab-title {
  font-size: 10px;
  font-weight: 500;
  font-family: var(--font-mono, monospace);
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.5px;
  text-transform: lowercase;
}

.ide-copy-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.35);
  transition: all 0.2s ease;
  font-size: 10px;
  font-family: var(--font-sans);
  outline: none;
  padding: 2px 6px;
  border-radius: 4px;
}

.ide-copy-btn:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.05);
}

.ide-copy-btn.copied {
  color: var(--accent-emerald, #34c759);
}

.json-code {
  margin: 0;
  padding: 12px 14px;
  background: transparent !important;
  font-size: 11px;
  line-height: 1.6;
  color: #c9d1d9 !important; /* Elegant light text on obsidian backdrop */
  font-family: var(--font-mono, monospace);
  overflow-x: auto;
  max-height: 320px;
  white-space: pre-wrap;
  word-break: break-all;
}

.json-code code {
  color: inherit !important;
  background: transparent !important;
}

.error-text {
  padding: 10px 12px;
  background: rgba(255, 69, 58, 0.06);
  border: 1px solid rgba(255, 69, 58, 0.15);
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.6;
  color: #ff453a;
  font-family: var(--font-mono, monospace);
  white-space: pre-wrap;
  word-break: break-all;
}

.tool-exec-group-summary {
  cursor: default;
  opacity: 0.75;
}

.tool-exec-group-summary .tool-exec-header {
  cursor: default;
}

.group-count-badge {
  margin-left: 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 10px;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

/* ── 顶奢审批操作区样式 ── */
.approval-action-block {
  margin-top: 12px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.04);
  border: 1px solid rgba(251, 191, 36, 0.15);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  position: relative;
  overflow: hidden;
  animation: cardPulseBorder 3s infinite ease-in-out;
}

.is-awaiting-approval {
  border-color: rgba(251, 191, 36, 0.3) !important;
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.1) !important;
}

.approval-pulse-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--warning-amber, #FBBF24);
  background: rgba(251, 191, 36, 0.12);
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.5px;
}

.pulse-dot-amber {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--warning-amber, #FBBF24);
  box-shadow: 0 0 8px var(--warning-amber, #FBBF24);
  animation: dotPulse 1.6s infinite ease-in-out;
}

.approval-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.warning-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.warning-icon {
  animation: pulse 2s infinite ease-in-out;
}

.approval-buttons-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.approval-btn {
  flex: 1;
  border: none;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.approval-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-hover-glow {
  position: absolute;
  top: 0;
  left: -100%;
  width: 300%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
  transition: all 0.6s ease;
}

.approval-btn:hover:not(:disabled) .btn-hover-glow {
  left: 100%;
}

.approval-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.approval-btn:active:not(:disabled) {
  transform: translateY(0);
}

/* 拒绝按钮 */
.reject-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.reject-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.5);
}

/* 全部授权按钮 */
.approve-all-btn {
  background: rgba(16, 185, 129, 0.05);
  color: var(--text-secondary);
  border: 1px solid var(--border-dim);
}

.approve-all-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  border-color: var(--text-muted);
}

/* 批准单次运行按钮 */
.approve-btn {
  background: rgba(16, 185, 129, 0.15);
  color: #10B981;
  border: 1px solid rgba(16, 185, 129, 0.35);
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.1);
}

.approve-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.35);
  border-color: rgba(16, 185, 129, 0.6);
}

@keyframes dotPulse {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.6;
    box-shadow: 0 0 4px rgba(251, 191, 36, 0.4);
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
    box-shadow: 0 0 10px rgba(251, 191, 36, 0.8);
  }
}

@keyframes cardPulseBorder {
  0%, 100% {
    border-color: rgba(251, 191, 36, 0.15);
  }
  50% {
    border-color: rgba(251, 191, 36, 0.35);
    box-shadow: 0 4px 22px rgba(251, 191, 36, 0.05);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}
</style>
