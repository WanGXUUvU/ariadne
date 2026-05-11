import re

with open('src/components/ChatPanel.vue', 'r') as f:
    content = f.read()

style = """<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-app);
  position: relative;
}

.panel-header {
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  background: rgba(10, 10, 10, 0.7);
  position: sticky;
  top: 0;
  z-index: 20;
}
</style>"""

content = re.sub(r'<style scoped>.*?</style>', style, content, flags=re.DOTALL)

with open('src/components/ChatPanel.vue', 'w') as f:
    f.write(content)

