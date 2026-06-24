<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { settingsApi } from '../../api/settings';
import type { McpReloadResult, McpServer, McpTransport } from '../../api/settings';

const props = defineProps<{
  isActive: boolean;
}>();

type PairItem = { key: string; value: string };

type McpFormState = {
  server_id: string;
  display_name: string;
  transport: McpTransport;
  enabled: boolean;
  required: boolean;
  startup_timeout_sec: number;
  tool_timeout_sec: number;
  command: string;
  args: string[];
  envPairs: PairItem[];
  cwd: string;
  url: string;
  bearer_token: string;
  httpHeaderPairs: PairItem[];
};

const servers = ref<McpServer[]>([]);
const selectedServerId = ref<string | null>(null);
const showAddModal = ref(false);
const isLoading = ref(false);
const isSaving = ref(false);
const isReloading = ref(false);
const errorMsg = ref<string | null>(null);
const infoMsg = ref<string | null>(null);

const form = ref<McpFormState>(createEmptyForm());
const addForm = ref<McpFormState>(createEmptyForm());

function createEmptyForm(): McpFormState {
  return {
    server_id: '',
    display_name: '',
    transport: 'stdio',
    enabled: true,
    required: false,
    startup_timeout_sec: 10,
    tool_timeout_sec: 30,
    command: '',
    args: [],
    envPairs: [],
    cwd: '',
    url: '',
    bearer_token: '',
    httpHeaderPairs: [],
  };
}

function toPairItems(record: Record<string, string>): PairItem[] {
  return Object.entries(record).map(([key, value]) => ({ key, value }));
}

function fromPairItems(items: PairItem[]): Record<string, string> {
  return items.reduce<Record<string, string>>((acc, item) => {
    const key = item.key.trim();
    if (!key) return acc;
    acc[key] = item.value;
    return acc;
  }, {});
}

function fromServer(server: McpServer): McpFormState {
  return {
    server_id: server.server_id,
    display_name: server.display_name || '',
    transport: server.transport,
    enabled: server.enabled,
    required: server.required,
    startup_timeout_sec: server.startup_timeout_sec,
    tool_timeout_sec: server.tool_timeout_sec,
    command: server.command || '',
    args: server.args ? [...server.args] : [],
    envPairs: toPairItems(server.env || {}),
    cwd: server.cwd || '',
    url: server.url || '',
    bearer_token: server.bearer_token || '',
    httpHeaderPairs: toPairItems(server.http_headers || {}),
  };
}

function buildPayload(source: McpFormState) {
  const base = {
    server_id: source.server_id.trim(),
    display_name: source.display_name.trim() || null,
    transport: source.transport,
    enabled: source.enabled,
    required: source.required,
    startup_timeout_sec: source.startup_timeout_sec,
    tool_timeout_sec: source.tool_timeout_sec,
  };

  if (source.transport === 'stdio') {
    return {
      ...base,
      command: source.command.trim(),
      args: source.args.map(item => item.trim()).filter(Boolean),
      env: fromPairItems(source.envPairs),
      cwd: source.cwd.trim() || null,
    };
  }

  return {
    ...base,
    url: source.url.trim(),
    bearer_token: source.bearer_token.trim() || null,
    http_headers: fromPairItems(source.httpHeaderPairs),
  };
}

const selectedServer = computed(() => {
  return servers.value.find(server => server.server_id === selectedServerId.value) || null;
});

const enabledCount = computed(() => servers.value.filter(server => server.enabled).length);
const connectedCount = computed(() => servers.value.filter(server => server.runtime_status === 'connected').length);

const canSave = computed(() => {
  if (!form.value.server_id.trim()) return false;
  if (form.value.transport === 'stdio') {
    return !!form.value.command.trim();
  }
  return !!form.value.url.trim();
});

const canSaveAdd = computed(() => {
  const serverId = addForm.value.server_id.trim();
  if (!serverId) return false;
  const exists = servers.value.some(s => s.server_id === serverId);
  if (exists) return false;

  if (addForm.value.transport === 'stdio') {
    return !!addForm.value.command.trim();
  }
  return !!addForm.value.url.trim();
});

function setFormFromServer(server: McpServer | null) {
  form.value = server ? fromServer(server) : createEmptyForm();
}

async function loadServers(preferredServerId?: string | null) {
  try {
    isLoading.value = true;
    errorMsg.value = null;
    servers.value = await settingsApi.listMcpServers();

    if (servers.value.length === 0) {
      selectedServerId.value = null;
      setFormFromServer(null);
      return;
    }

    if (preferredServerId) {
      const found = servers.value.find(server => server.server_id === preferredServerId);
      if (found) {
        selectedServerId.value = found.server_id;
        setFormFromServer(found);
        return;
      }
    }

    if (selectedServerId.value) {
      const current = servers.value.find(server => server.server_id === selectedServerId.value);
      if (current) {
        setFormFromServer(current);
        return;
      }
    }

    // Default to the first server in the list
    selectedServerId.value = servers.value[0].server_id;
    setFormFromServer(servers.value[0]);
  } catch (err: any) {
    errorMsg.value = `加载 MCP 配置失败: ${err.message}`;
  } finally {
    isLoading.value = false;
  }
}

async function reloadRuntime(successMessage = 'MCP runtime 已重新加载') {
  try {
    isReloading.value = true;
    const result: McpReloadResult = await settingsApi.reloadMcpRuntime();
    const errorSummary = result.errors.map(item => `${item.server_id}: ${item.message}`).join('；');
    infoMsg.value = errorSummary
      ? `${successMessage}。成功 ${result.connected_servers} 个，失败 ${result.failed_servers} 个：${errorSummary}`
      : `${successMessage}。成功连接 ${result.connected_servers} 个 server。`;
  } catch (err: any) {
    errorMsg.value = `MCP runtime 重载失败: ${err.message}`;
    throw err;
  } finally {
    isReloading.value = false;
  }
}

function startCreateServer() {
  addForm.value = createEmptyForm();
  showAddModal.value = true;
  errorMsg.value = null;
  infoMsg.value = null;
}

function closeAddModal() {
  showAddModal.value = false;
  errorMsg.value = null;
  infoMsg.value = null;
}

function selectServer(server: McpServer) {
  selectedServerId.value = server.server_id;
  errorMsg.value = null;
  infoMsg.value = null;
  setFormFromServer(server);
}

async function saveNewServer() {
  if (!canSaveAdd.value) return;

  try {
    isSaving.value = true;
    errorMsg.value = null;
    infoMsg.value = null;

    const payload = buildPayload(addForm.value);
    const saved = await settingsApi.createMcpServer(payload);

    try {
      await reloadRuntime('MCP server 已连接并应用');
    } catch {
      // 错误已由 reloadRuntime 处理
    }

    showAddModal.value = false;
    await loadServers(saved.server_id);
  } catch (err: any) {
    errorMsg.value = `添加 MCP 配置失败: ${err.message}`;
  } finally {
    isSaving.value = false;
  }
}

async function saveServer() {
  if (!canSave.value) {
    errorMsg.value = '请先补全必填字段。';
    return;
  }

  try {
    isSaving.value = true;
    errorMsg.value = null;
    infoMsg.value = null;

    const payload = buildPayload(form.value);
    let saved: McpServer;

    if (selectedServerId.value) {
      const patchPayload = { ...payload };
      delete (patchPayload as { server_id?: string }).server_id;
      saved = await settingsApi.patchMcpServer(selectedServerId.value, patchPayload);
    } else {
      throw new Error('未找到要保存的 MCP server');
    }

    try {
      await reloadRuntime('MCP 配置已保存并应用');
    } catch {
      // 错误已由 reloadRuntime 处理
    }

    await loadServers(saved.server_id);
  } catch (err: any) {
    errorMsg.value = `保存 MCP 配置失败: ${err.message}`;
  } finally {
    isSaving.value = false;
  }
}

async function removeServer(server: McpServer) {
  if (!confirm(`确定删除 MCP server「${server.server_id}」吗？`)) return;

  try {
    errorMsg.value = null;
    infoMsg.value = null;
    await settingsApi.deleteMcpServer(server.server_id);

    try {
      await reloadRuntime(`MCP server ${server.server_id} 已删除并应用`);
    } catch {
      // 错误已由 reloadRuntime 处理
    }

    const nextServerId = servers.value.find(item => item.server_id !== server.server_id)?.server_id ?? null;
    await loadServers(nextServerId);
  } catch (err: any) {
    errorMsg.value = `删除 MCP 配置失败: ${err.message}`;
  }
}

async function toggleEnabled(server: McpServer) {
  try {
    errorMsg.value = null;
    infoMsg.value = null;
    await settingsApi.patchMcpServer(server.server_id, { enabled: !server.enabled });

    try {
      await reloadRuntime(`${server.server_id} 启用状态已更新并应用`);
    } catch {
      // 错误消息已经由 reloadRuntime 提示
    }

    await loadServers(server.server_id);
  } catch (err: any) {
    errorMsg.value = `更新启用状态失败: ${err.message}`;
  }
}

function addArgRow() {
  form.value.args.push('');
}

function removeArgRow(index: number) {
  form.value.args.splice(index, 1);
}

function addEnvRow() {
  form.value.envPairs.push({ key: '', value: '' });
}

function removeEnvRow(index: number) {
  form.value.envPairs.splice(index, 1);
}

function addHeaderRow() {
  form.value.httpHeaderPairs.push({ key: '', value: '' });
}

function removeHeaderRow(index: number) {
  form.value.httpHeaderPairs.splice(index, 1);
}

function getStatusLabel(status: McpServer['runtime_status']) {
  if (status === 'connected') return '已连接';
  if (status === 'disabled') return '已禁用';
  if (status === 'error') return '连接失败';
  return '未启动';
}

function getTransportLabel(transport: McpTransport) {
  return transport === 'stdio' ? 'STDIO' : '流式 HTTP';
}

function getEnabledLabel(enabled: boolean) {
  return enabled ? '已启用' : '已关闭';
}

onMounted(() => {
  if (props.isActive) {
    loadServers();
  }
});

watch(() => props.isActive, active => {
  if (active) {
    loadServers(selectedServerId.value);
  }
});
</script>\n\n<template>
  <div class="settings-panel-view">
    <div class="mcp-header">
      <div class="mcp-title-block">
        <div class="mcp-page-title">MCP 服务器</div>
        <div class="view-description mcp-description">
          配置并管理 Model Context Protocol (MCP) 服务器，动态扩展智能体的工具集能力。
        </div>
      </div>
    </div>

    <div v-if="errorMsg" class="settings-error">
      <span>{{ errorMsg }}</span>
      <button @click="errorMsg = null">✕</button>
    </div>

    <div v-if="infoMsg" class="settings-info">
      <span>{{ infoMsg }}</span>
      <button @click="infoMsg = null">✕</button>
    </div>

    <div class="mcp-split-layout">
      <!-- Left Side: List Panel -->
      <div class="mcp-sidebar-panel">
        <div class="mcp-sidebar-header">
          <div class="mcp-mini-state">
            <span>{{ servers.length }} 台服务器</span>
            <span>{{ connectedCount }} 已连接</span>
          </div>
          <div class="mcp-sidebar-actions">
            <button
              type="button"
              class="ghost-action-btn compact"
              :disabled="isReloading"
              @click="reloadRuntime()"
              title="重载 MCP 运行时"
            >
              <svg :class="{ 'spin': isReloading }" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
              </svg>
            </button>
            <button type="button" class="save-btn compact" @click="startCreateServer" title="添加服务器">＋ 添加</button>
          </div>
        </div>

        <div v-if="isLoading" class="mcp-list-empty">正在加载 MCP server 列表...</div>
        <div v-else-if="servers.length === 0" class="mcp-list-empty">暂无服务器配置</div>
        <div v-else class="mcp-servers-list-container">
          <div
            v-for="server in servers"
            :key="server.server_id"
            class="mcp-server-row"
            :class="{ active: selectedServerId === server.server_id }"
            @click="selectServer(server)"
          >
            <div class="server-row-main">
              <div class="server-title-line">
                <span class="server-online-dot" :class="server.runtime_status"></span>
                <span class="server-name" :title="server.display_name || server.server_id">
                  {{ server.display_name || server.server_id }}
                </span>
              </div>
              <div class="server-status-line">
                <span class="server-state-badge" :class="server.enabled ? 'enabled' : 'disabled'">
                  {{ getEnabledLabel(server.enabled) }}
                </span>
                <span class="server-state-badge" :class="server.runtime_status">
                  {{ getStatusLabel(server.runtime_status) }}
                </span>
                <span v-if="server.tool_count > 0" class="server-state-badge tool-count">
                  {{ server.tool_count }} 工具
                </span>
              </div>
            </div>
            <div class="server-row-side">
              <button
                type="button"
                class="switch-toggle"
                :class="{ active: server.enabled }"
                @click.stop="toggleEnabled(server)"
                title="切换启用状态"
              >
                <span class="switch-dot"></span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Side: Details Panel -->
      <div class="mcp-detail-panel">
        <div v-if="selectedServerId" class="mcp-surface mcp-form-card">
          <div class="editor-head">
            <div>
              <div class="editor-title">{{ form.display_name || form.server_id || '编辑配置' }}</div>
              <div class="editor-subtitle">
                {{ form.transport === 'stdio' ? '本地进程通过 stdio 握手' : '远端 endpoint 通过 streamable HTTP 握手' }}
              </div>
              <div v-if="selectedServer" class="editor-status-row">
                <span class="server-state-badge" :class="selectedServer.enabled ? 'enabled' : 'disabled'">
                  {{ getEnabledLabel(selectedServer.enabled) }}
                </span>
                <span class="server-state-badge" :class="selectedServer.runtime_status">
                  {{ getStatusLabel(selectedServer.runtime_status) }}
                </span>
              </div>
              <div v-if="selectedServer && selectedServer.last_error" class="server-error-container">
                <div class="server-error-text">
                  {{ selectedServer.last_error }}
                </div>
              </div>
            </div>
            <span class="editor-status-chip" :class="form.transport">
              {{ getTransportLabel(form.transport) }}
            </span>
          </div>

          <div class="mcp-form-scroll-container">
            <div class="mcp-form-group two-column">
              <label>
                <span class="form-label">名称 / ID</span>
                <input v-model="form.server_id" :disabled="true" type="text" placeholder="mcp-server-id" />
              </label>
              <label>
                <span class="form-label">显示名称</span>
                <input v-model="form.display_name" type="text" placeholder="可选，用于界面展示" />
              </label>
            </div>

            <div class="mcp-form-group">
              <span class="form-label">传输协议 (Transport)</span>
              <div>
                <span class="editor-status-chip read-only" :class="form.transport">
                  {{ getTransportLabel(form.transport) }}
                </span>
                <span class="transport-lock-desc">已创建服务器的传输协议不可修改</span>
              </div>
            </div>

            <div class="mcp-form-group two-column compact-row">
              <label class="checkbox-line">
                <input v-model="form.enabled" type="checkbox" />
                <span>启用服务器</span>
              </label>
              <label class="checkbox-line">
                <input v-model="form.required" type="checkbox" />
                <span>设为必需 (阻断运行如果失败)</span>
              </label>
            </div>

            <div class="mcp-form-group two-column">
              <label>
                <span class="form-label">启动超时（秒）</span>
                <input v-model.number="form.startup_timeout_sec" type="number" min="1" />
              </label>
              <label>
                <span class="form-label">工具超时（秒）</span>
                <input v-model.number="form.tool_timeout_sec" type="number" min="1" />
              </label>
            </div>

            <!-- STDIO Config -->
            <template v-if="form.transport === 'stdio'">
              <div class="mcp-form-group">
                <label>
                  <span class="form-label">启动命令 (Command)</span>
                  <input v-model="form.command" type="text" placeholder="例如 npx, python3, node..." />
                </label>
              </div>

              <div class="mcp-form-group">
                <span class="form-label">启动参数 (Arguments)</span>
                <div class="pair-list" v-if="form.args.length > 0">
                  <div v-for="(arg, index) in form.args" :key="`arg-${index}`" class="single-row">
                    <input v-model="form.args[index]" type="text" placeholder="参数值" />
                    <button type="button" class="row-delete-btn" @click="removeArgRow(index)" title="删除参数">✕</button>
                  </div>
                </div>
                <div v-else class="empty-list-placeholder">未配置任何启动参数</div>
                <button type="button" class="ghost-inline-btn" @click="addArgRow">+ 添加参数</button>
              </div>

              <div class="mcp-form-group">
                <span class="form-label">环境变量 (Environment)</span>
                <div class="pair-list" v-if="form.envPairs.length > 0">
                  <div v-for="(pair, index) in form.envPairs" :key="`env-${index}`" class="pair-row">
                    <input v-model="pair.key" type="text" placeholder="键 (e.g. API_KEY)" />
                    <input v-model="pair.value" type="text" placeholder="值" />
                    <button type="button" class="row-delete-btn" @click="removeEnvRow(index)" title="删除环境变量">✕</button>
                  </div>
                </div>
                <div v-else class="empty-list-placeholder">未配置任何环境变量</div>
                <button type="button" class="ghost-inline-btn" @click="addEnvRow">+ 添加环境变量</button>
              </div>

              <div class="mcp-form-group">
                <label>
                  <span class="form-label">工作目录 (CWD)</span>
                  <input v-model="form.cwd" type="text" placeholder="例如 ~/projects/mcp-server" />
                </label>
              </div>
            </template>

            <!-- HTTP Config -->
            <template v-else>
              <div class="mcp-form-group">
                <label>
                  <span class="form-label">连接 URL</span>
                  <input v-model="form.url" type="text" placeholder="http://localhost:8000/sse" />
                </label>
              </div>

              <div class="mcp-form-group">
                <label>
                  <span class="form-label">Bearer Token</span>
                  <input v-model="form.bearer_token" type="password" placeholder="留空或输入 Token" />
                </label>
              </div>

              <div class="mcp-form-group">
                <span class="form-label">请求标头 (HTTP Headers)</span>
                <div class="pair-list" v-if="form.httpHeaderPairs.length > 0">
                  <div v-for="(pair, index) in form.httpHeaderPairs" :key="`header-${index}`" class="pair-row">
                    <input v-model="pair.key" type="text" placeholder="键" />
                    <input v-model="pair.value" type="text" placeholder="值" />
                    <button type="button" class="row-delete-btn" @click="removeHeaderRow(index)" title="删除标头">✕</button>
                  </div>
                </div>
                <div v-else class="empty-list-placeholder">未配置任何自定义 HTTP 标头</div>
                <button type="button" class="ghost-inline-btn" @click="addHeaderRow">+ 添加标头</button>
              </div>
            </template>
          </div>

          <div class="mcp-editor-actions">
            <button
              type="button"
              class="cancel-btn"
              @click="selectedServer && setFormFromServer(selectedServer)"
            >
              重置
            </button>
            <button
              v-if="selectedServer"
              type="button"
              class="tiny-card-btn danger"
              @click="removeServer(selectedServer)"
            >
              删除服务器
            </button>
            <button type="button" class="save-btn" :disabled="isSaving || !canSave" @click="saveServer">
              {{ isSaving ? '保存中…' : '保存并应用' }}
            </button>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="mcp-blank-state">
          <div class="blank-icon">
            <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.2" fill="none" class="pulse-icon">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
              <line x1="8" y1="21" x2="16" y2="21"/>
              <line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
          </div>
          <div class="blank-title">选择或添加 MCP 服务器</div>
          <div class="blank-description">
            在左侧列表中选择一个 MCP 服务器以查看及编辑其配置，或者点击“＋ 添加”按钮新增一个自定义服务器连接。
          </div>
        </div>
      </div>
    </div>

    <!-- Add Server Pop-up Modal Dialog -->
    <Transition name="fade">
      <div v-if="showAddModal" class="mcp-dialog-overlay" @click.self="closeAddModal">
        <Transition name="zoom">
          <div class="mcp-dialog-card">
            <div class="mcp-dialog-header">
              <h3 class="mcp-dialog-title">连接新 MCP 服务器</h3>
              <button type="button" class="close-dialog-btn" @click="closeAddModal">✕</button>
            </div>
            
            <div class="mcp-dialog-body">
              <div class="mcp-form-group two-column">
                <label>
                  <span class="form-label">名称 / ID *</span>
                  <input v-model="addForm.server_id" type="text" placeholder="例如: mcp-sqlite" />
                </label>
                <label>
                  <span class="form-label">显示名称</span>
                  <input v-model="addForm.display_name" type="text" placeholder="可选，用于界面显示" />
                </label>
              </div>

              <div class="mcp-form-group">
                <span class="form-label">传输协议 (Transport)</span>
                <div class="transport-segment">
                  <button
                    type="button"
                    class="transport-btn"
                    :class="{ active: addForm.transport === 'stdio' }"
                    @click="addForm.transport = 'stdio'"
                  >
                    本地进程 (STDIO)
                  </button>
                  <button
                    type="button"
                    class="transport-btn"
                    :class="{ active: addForm.transport === 'streamable_http' }"
                    @click="addForm.transport = 'streamable_http'"
                  >
                    远程服务 (HTTP SSE)
                  </button>
                </div>
                <div class="transport-desc">
                  {{ addForm.transport === 'stdio' ? '适用于本地可执行文件、数据库或自定义脚本。通过命令行子进程与系统 STDIO 进行数据握手。' : '适用于通过网络部署的远程 MCP 节点或 API 代理服务。通过 HTTP Server-Sent Events (SSE) 协议连接。' }}
                </div>
              </div>

              <div class="mcp-form-group two-column">
                <label>
                  <span class="form-label">启动超时（秒）</span>
                  <input v-model.number="addForm.startup_timeout_sec" type="number" min="1" />
                </label>
                <label>
                  <span class="form-label">工具超时（秒）</span>
                  <input v-model.number="addForm.tool_timeout_sec" type="number" min="1" />
                </label>
              </div>

              <!-- STDIO Config -->
              <template v-if="addForm.transport === 'stdio'">
                <div class="mcp-form-group">
                  <label>
                    <span class="form-label">启动命令 (Command) *</span>
                    <input v-model="addForm.command" type="text" placeholder="npx, python3, node 等..." />
                  </label>
                </div>

                <div class="mcp-form-group">
                  <span class="form-label">启动参数 (Arguments)</span>
                  <div class="pair-list" v-if="addForm.args.length > 0">
                    <div v-for="(arg, index) in addForm.args" :key="`add-arg-${index}`" class="single-row">
                      <input v-model="addForm.args[index]" type="text" placeholder="参数值" />
                      <button type="button" class="row-delete-btn" @click="addForm.args.splice(index, 1)">✕</button>
                    </div>
                  </div>
                  <button type="button" class="ghost-inline-btn" @click="addForm.args.push('')">+ 添加参数</button>
                </div>

                <div class="mcp-form-group">
                  <span class="form-label">环境变量 (Environment)</span>
                  <div class="pair-list" v-if="addForm.envPairs.length > 0">
                    <div v-for="(pair, index) in addForm.envPairs" :key="`add-env-${index}`" class="pair-row">
                      <input v-model="pair.key" type="text" placeholder="键" />
                      <input v-model="pair.value" type="text" placeholder="值" />
                      <button type="button" class="row-delete-btn" @click="addForm.envPairs.splice(index, 1)">✕</button>
                    </div>
                  </div>
                  <button type="button" class="ghost-inline-btn" @click="addForm.envPairs.push({ key: '', value: '' })">+ 添加环境变量</button>
                </div>

                <div class="mcp-form-group">
                  <label>
                    <span class="form-label">工作目录 (CWD)</span>
                    <input v-model="addForm.cwd" type="text" placeholder="可选工作目录绝对路径" />
                  </label>
                </div>
              </template>

              <!-- HTTP Config -->
              <template v-else>
                <div class="mcp-form-group">
                  <label>
                    <span class="form-label">连接 URL *</span>
                    <input v-model="addForm.url" type="text" placeholder="http://localhost:8000/sse" />
                  </label>
                </div>

                <div class="mcp-form-group">
                  <label>
                    <span class="form-label">Bearer Token</span>
                    <input v-model="addForm.bearer_token" type="password" placeholder="留空或输入 Token" />
                  </label>
                </div>

                <div class="mcp-form-group">
                  <span class="form-label">请求标头 (HTTP Headers)</span>
                  <div class="pair-list" v-if="addForm.httpHeaderPairs.length > 0">
                    <div v-for="(pair, index) in addForm.httpHeaderPairs" :key="`add-header-${index}`" class="pair-row">
                      <input v-model="pair.key" type="text" placeholder="键" />
                      <input v-model="pair.value" type="text" placeholder="值" />
                      <button type="button" class="row-delete-btn" @click="addForm.httpHeaderPairs.splice(index, 1)">✕</button>
                    </div>
                  </div>
                  <button type="button" class="ghost-inline-btn" @click="addForm.httpHeaderPairs.push({ key: '', value: '' })">+ 添加标头</button>
                </div>
              </template>
            </div>

            <div class="mcp-dialog-footer">
              <button type="button" class="cancel-btn" @click="closeAddModal">取消</button>
              <button type="button" class="save-btn" :disabled="isSaving || !canSaveAdd" @click="saveNewServer">
                {{ isSaving ? '连接中…' : '确认连接' }}
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </div>
</template>
\n\n<style scoped>
.settings-panel-view {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.mcp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 12px;
}

.mcp-title-block {
  min-width: 0;
}

.mcp-page-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.mcp-description {
  margin-bottom: 10px;
  max-width: 720px;
}

.settings-error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: #f87171;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-family: var(--font-mono, monospace);
}

.settings-error button {
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
}

.settings-info {
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.18);
  color: #6ee7b7;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-family: var(--font-mono, monospace);
}

.settings-info button {
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
}

/* Master-Detail Split Layout */
.mcp-split-layout {
  display: grid;
  grid-template-columns: 290px 1fr;
  gap: 20px;
  height: 560px;
  max-height: 560px;
  margin-top: 10px;
  min-width: 0;
}

/* Left Sidebar Panel */
.mcp-sidebar-panel {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 12px;
  height: 100%;
  box-sizing: border-box;
  min-width: 0;
}

.mcp-sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.mcp-sidebar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mcp-mini-state {
  display: flex;
  gap: 6px;
  font-size: 10px;
  color: var(--text-muted);
}

.mcp-mini-state span {
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ghost-action-btn.compact {
  padding: 5px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
  cursor: pointer;
}

.ghost-action-btn.compact:hover {
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.18);
}

.save-btn.compact {
  padding: 4px 8px;
  font-size: 10.5px;
  border-radius: 6px;
  background: var(--accent);
  color: #fff;
  border: none;
  cursor: pointer;
  font-weight: 500;
}

.save-btn.compact:hover {
  background: var(--accent-hover, #6d28d9);
}

.spin {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.mcp-list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
  border: 1px dashed rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}

.mcp-servers-list-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}

/* Scrollbar styling */
.mcp-servers-list-container::-webkit-scrollbar,
.mcp-form-scroll-container::-webkit-scrollbar {
  width: 4px;
}

.mcp-servers-list-container::-webkit-scrollbar-track,
.mcp-form-scroll-container::-webkit-scrollbar-track {
  background: transparent;
}

.mcp-servers-list-container::-webkit-scrollbar-thumb,
.mcp-form-scroll-container::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 99px;
}

.mcp-server-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.012);
  border: 1px solid rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.mcp-server-row:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.07);
}

.mcp-server-row.active {
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.08);
  border-color: var(--accent);
  box-shadow: inset 0 0 0 1px rgba(var(--accent-rgb, 124, 106, 247), 0.2);
}

.server-row-main {
  min-width: 0;
  flex: 1;
  padding-right: 8px;
}

.server-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.server-online-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  flex-shrink: 0;
  background: #94a3b8;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.12);
}

.server-online-dot.connected {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.14);
}

.server-online-dot.not_started {
  background: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.14);
}

.server-online-dot.error {
  background: #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.14);
}

.server-online-dot.disabled {
  background: #94a3b8;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.08);
}

.server-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 170px;
}

.server-status-line {
  display: flex;
  gap: 4px;
  align-items: center;
  margin-top: 5px;
  flex-wrap: wrap;
}

.server-state-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 18px;
  padding: 0 5px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.01em;
  border: 1px solid rgba(148, 163, 184, 0.15);
  background: rgba(148, 163, 184, 0.06);
  color: var(--text-secondary);
}

.server-state-badge.enabled {
  background: rgba(236, 72, 153, 0.06);
  border-color: rgba(236, 72, 153, 0.15);
  color: #f472b6;
}

.server-state-badge.disabled {
  background: rgba(148, 163, 184, 0.04);
  border-color: rgba(148, 163, 184, 0.1);
  color: var(--text-muted);
}

.server-state-badge.connected {
  background: rgba(34, 197, 94, 0.06);
  border-color: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.server-state-badge.not_started {
  background: rgba(245, 158, 11, 0.06);
  border-color: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.server-state-badge.error {
  background: rgba(239, 68, 68, 0.06);
  border-color: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.server-state-badge.tool-count {
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.06);
  border-color: rgba(var(--accent-rgb, 124, 106, 247), 0.15);
  color: var(--accent);
}

.server-row-side {
  display: flex;
  align-items: center;
}

.switch-toggle {
  position: relative;
  width: 30px;
  height: 18px;
  border: none;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  cursor: pointer;
  transition: background 0.16s ease;
}

.switch-toggle.active {
  background: linear-gradient(135deg, #ec4899, #f472b6);
}

.switch-dot {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: transform 0.16s ease;
}

.switch-toggle.active .switch-dot {
  transform: translateX(12px);
}

/* Right Details Panel */
.mcp-detail-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.mcp-surface {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.01);
}

.mcp-form-card {
  height: 100%;
  padding: 16px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.editor-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.editor-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.editor-subtitle {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.4;
}

.editor-status-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.server-error-container {
  margin-top: 8px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.12);
  border-radius: 6px;
  padding: 6px 10px;
  max-width: 100%;
}

.server-error-text {
  color: #f87171;
  font-size: 11px;
  line-height: 1.4;
  font-family: var(--font-mono, monospace);
  word-break: break-all;
}

.editor-status-chip {
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  color: var(--text-secondary);
}

.editor-status-chip.stdio {
  color: var(--text-primary);
}

.editor-status-chip.streamable_http {
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.1);
  border-color: rgba(var(--accent-rgb, 124, 106, 247), 0.18);
  color: var(--text-primary);
}

.mcp-form-scroll-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 6px;
  margin-top: 14px;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.mcp-form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mcp-form-group.two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.mcp-form-group label {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
}

input:not([type="checkbox"]) {
  background: var(--bg-app);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12.5px;
  color: var(--text-primary);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  width: 100%;
  box-sizing: border-box;
}

input:not([type="checkbox"]):hover {
  border-color: var(--border-strong);
}

input:not([type="checkbox"]):focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

input:not([type="checkbox"]):disabled {
  background: var(--bg-hover);
  color: var(--text-muted);
  cursor: not-allowed;
  border-color: var(--border-dim);
}

.transport-segment {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  padding: 3px;
  border: 1px solid var(--border-dim);
  border-radius: 10px;
  background: var(--bg-app);
  overflow: hidden;
  box-sizing: border-box;
}

.transport-btn {
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 7px;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.transport-btn:hover:not(.active) {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.transport-btn.active {
  color: var(--text-primary);
  background: var(--bg-panel);
  border-color: var(--border-dim);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
}

.compact-row {
  align-items: center;
}

.checkbox-line {
  flex-direction: row !important;
  align-items: center;
  gap: 8px !important;
  cursor: pointer;
  user-select: none;
}

.checkbox-line span {
  font-size: 12px;
  color: var(--text-secondary);
}

.checkbox-line input {
  width: 14px;
  height: 14px;
  padding: 0;
  accent-color: var(--accent);
}

.pair-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pair-row,
.single-row {
  display: grid;
  gap: 8px;
  align-items: center;
}

.pair-row {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
}

.single-row {
  grid-template-columns: minmax(0, 1fr) auto;
}

.row-delete-btn {
  border: 1px solid var(--border-dim);
  background: var(--bg-hover);
  color: var(--text-muted);
  width: 34px;
  height: 34px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  transition: all 0.2s ease;
}

.row-delete-btn:hover {
  background: rgba(239, 68, 68, 0.06);
  color: var(--danger, #ff453a);
  border-color: rgba(239, 68, 68, 0.15);
}

.empty-list-placeholder {
  font-size: 11px;
  color: var(--text-muted);
  font-style: italic;
  padding: 8px 12px;
  background: var(--bg-hover);
  border: 1px dashed var(--border-dim);
  border-radius: 8px;
  text-align: center;
}

.ghost-inline-btn {
  border: 1px dashed var(--border-strong);
  background: var(--bg-hover);
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s ease;
}

.ghost-inline-btn:hover {
  color: var(--text-primary);
  background: var(--bg-active);
  border-color: var(--accent);
}

.mcp-editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--border-dim);
}

.cancel-btn,
.save-btn,
.tiny-card-btn {
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.cancel-btn {
  border: 1px solid var(--border-dim);
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.cancel-btn:hover {
  color: var(--text-primary);
  background: var(--bg-active);
  border-color: var(--border-strong);
}

.tiny-card-btn.danger {
  border: 1px solid rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.04);
  color: var(--danger, #ff453a);
  margin-right: auto;
}

.tiny-card-btn.danger:hover {
  background: rgba(239, 68, 68, 0.08);
  border-color: var(--danger, #ff453a);
}

.save-btn {
  background: var(--accent);
  color: var(--bg-panel);
  border: none;
  font-weight: 600;
  box-shadow: 0 2px 6px var(--accent-glow);
}

.save-btn:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: 0 4px 12px var(--accent-glow);
}

.save-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

.mono-text {
  font-family: var(--font-mono, monospace);
}

/* Blank Empty State */
.mcp-blank-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  border: 1px dashed var(--border-dim);
  border-radius: 12px;
  background: var(--bg-hover);
  padding: 40px;
  text-align: center;
  box-sizing: border-box;
}

.blank-icon {
  color: var(--text-muted);
  opacity: 0.35;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pulse-icon {
  animation: pulse 3s infinite ease-in-out;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.35; }
  50% { transform: scale(1.06); opacity: 0.65; }
  100% { transform: scale(1); opacity: 0.35; }
}

.blank-title {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.blank-description {
  font-size: 11.5px;
  color: var(--text-muted);
  max-width: 300px;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .mcp-split-layout {
    grid-template-columns: 1fr;
    height: auto;
    max-height: none;
  }
  .mcp-sidebar-panel {
    height: 250px;
  }
}

/* Dialog / Modal styles */
.mcp-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.mcp-dialog-card {
  width: 100%;
  max-width: 580px;
  background: var(--bg-panel);
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  box-shadow: var(--shadow-app);
  display: flex;
  flex-direction: column;
  max-height: 85vh;
  overflow: hidden;
}

.mcp-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-dim);
}

.mcp-dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.close-dialog-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 6px;
  font-size: 14px;
  line-height: 1;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-dialog-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.mcp-dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Scrollbar for dialog body */
.mcp-dialog-body::-webkit-scrollbar {
  width: 4px;
}
.mcp-dialog-body::-webkit-scrollbar-track {
  background: transparent;
}
.mcp-dialog-body::-webkit-scrollbar-thumb {
  background: var(--border-dim);
  border-radius: 99px;
}

.mcp-dialog-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-dim);
  background: var(--bg-app);
}

.transport-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-top: 4px;
}

.transport-lock-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: 10px;
  vertical-align: middle;
}

.editor-status-chip.read-only {
  display: inline-flex;
  vertical-align: middle;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.zoom-enter-active,
.zoom-leave-active {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.2s ease;
}
.zoom-enter-from,
.zoom-leave-to {
  transform: scale(0.96) translateY(8px);
  opacity: 0;
}
</style>