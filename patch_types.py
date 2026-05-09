import re
with open('frontend/src/composables/useWorkspace.ts', 'r') as f:
    content = f.read()

content = content.replace("if (trace && trace.runs) {", "if (trace && 'runs' in trace) {")
content = content.replace("events.value = trace.runs.flatMap((run: any) => run.events);", "events.value = (trace as TraceResponse).runs.flatMap((run: any) => run.events);")

with open('frontend/src/composables/useWorkspace.ts', 'w') as f:
    f.write(content)

