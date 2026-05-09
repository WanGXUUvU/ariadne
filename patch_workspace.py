import re

with open('frontend/src/composables/useWorkspace.ts', 'r') as f:
    content = f.read()

content = content.replace("const messages = ref<AgentMessage[]>([]);", "const currentMessages = ref<AgentMessage[]>([]);\n  const historyMessages = ref<AgentMessage[]>([]);")

content = content.replace("  // Computed Properties", "  // Computed Properties\n  const messages = computed(() => [...historyMessages.value, ...currentMessages.value]);")

content = content.replace("messages.value = [];", "historyMessages.value = [];\n      currentMessages.value = [];")

content = content.replace("messages.value = detail.state?.messages || [];", "currentMessages.value = detail.state?.messages || [];")

content = content.replace("if (messages.value.length > 12) {", "if (currentMessages.value.length > 12) {")
content = content.replace("messages.value.push({ role: 'user', content: input });", "currentMessages.value.push({ role: 'user', content: input });")
content = content.replace("messages.value = res.state?.messages || [];", "currentMessages.value = res.state?.messages || [];")

reset_func_old = """      await api.resetSession(currentId);
      historyMessages.value = [];
      currentMessages.value = [];
      events.value = [];"""

reset_func_new = """      await api.resetSession(currentId);
      historyMessages.value = [
        ...historyMessages.value,
        ...currentMessages.value,
        { role: 'system', content: '[RESET_MARKER]', name: 'SYSTEM' } as AgentMessage
      ];
      currentMessages.value = [];
      events.value = [];"""

content = content.replace(reset_func_old, reset_func_new)

with open('frontend/src/composables/useWorkspace.ts', 'w') as f:
    f.write(content)

