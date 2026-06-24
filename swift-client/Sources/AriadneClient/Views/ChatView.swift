import SwiftUI

struct ChatView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var scrollTarget: String? = nil
    
    @State private var breathingScale: CGFloat = 1.0
    @State private var breathingOpacity: Double = 0.5
    
    var body: some View {
        VStack(spacing: 0) {
            // Header Bar
            headerBar
            
            // Conversation Scroll View
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        if let detail = viewModel.currentSessionDetail {
                            ForEach(Array(detail.state.messages.enumerated()), id: \.element.id) { index, message in
                                MessageBubbleView(message: message, index: index)
                            }
                        }
                        
                        // Active Streaming Bubble
                        if viewModel.isStreaming {
                            StreamingBubbleView()
                                .id("streaming_anchor")
                        }
                    }
                    .padding()
                }
                .onChange(of: viewModel.isStreaming) { isStreaming in
                    if isStreaming {
                        withAnimation {
                            proxy.scrollTo("streaming_anchor", anchor: .bottom)
                        }
                    }
                }
                .onChange(of: viewModel.streamingReply) { _ in
                    withAnimation {
                        proxy.scrollTo("streaming_anchor", anchor: .bottom)
                    }
                }
                .onChange(of: viewModel.streamingThinking) { _ in
                    withAnimation {
                        proxy.scrollTo("streaming_anchor", anchor: .bottom)
                    }
                }
            }
            .background(Color(NSColor.textBackgroundColor).opacity(0.15))
            
            Divider()
            
            // Bottom Message Composer
            ChatComposerView()
        }
    }
    
    private var headerBar: some View {
        HStack {
            VStack(alignment: .leading, spacing: 3) {
                if let detail = viewModel.currentSessionDetail {
                    Text(detail.sessionName ?? "Session Detail")
                        .font(.headline)
                    
                    if let workspace = detail.workspacePath {
                        Text(workspace)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
            }
            
            Spacer()
            
            // Quick status indicator
            if viewModel.isStreaming {
                HStack(spacing: 8) {
                    Circle()
                        .fill(Color.orange)
                        .frame(width: 8, height: 8)
                        .scaleEffect(breathingScale)
                        .opacity(breathingOpacity)
                        .onAppear {
                            withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) {
                                breathingScale = 1.4
                                breathingOpacity = 1.0
                            }
                        }
                    
                    Text("Agent is running...")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(.ultraThinMaterial)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.orange.opacity(0.2), lineWidth: 1)
                )
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// MARK: - Message Bubble

struct MessageBubbleView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let message: ChatMessage
    let index: Int
    
    @State private var isEditing = false
    @State private var editedContent = ""
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            if message.role == "user" {
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    if isEditing {
                        VStack(alignment: .trailing, spacing: 6) {
                            TextEditor(text: $editedContent)
                                .font(.body)
                                .frame(width: 320, height: 80)
                                .cornerRadius(8)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(Color.secondary.opacity(0.3), lineWidth: 1)
                                )
                            
                            HStack(spacing: 8) {
                                Button("Cancel") {
                                    isEditing = false
                                }
                                .buttonStyle(.bordered)
                                
                                Button("Save") {
                                    isEditing = false
                                    Task {
                                        await viewModel.editAndResendMessage(at: index, newContent: editedContent)
                                    }
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                    } else {
                        Text(message.content ?? "")
                            .padding(.vertical, 8)
                            .padding(.horizontal, 12)
                            .font(.body)
                            .foregroundColor(.white)
                            .background(
                                LinearGradient(
                                    colors: [Color.accentColor, Color.accentColor.opacity(0.85)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .cornerRadius(14)
                            .shadow(color: Color.accentColor.opacity(0.15), radius: 4, y: 2)
                            .onTapGesture(count: 2) {
                                editedContent = message.content ?? ""
                                isEditing = true
                            }
                            .help("Double click to edit message")
                    }
                }
                
                Image(systemName: "person.crop.circle.fill")
                    .font(.title2)
                    .foregroundColor(.accentColor)
            } else if message.role == "assistant" {
                Image(systemName: "cpu.fill")
                    .font(.title2)
                    .foregroundColor(.purple)
                
                VStack(alignment: .leading, spacing: 6) {
                    if let content = message.content {
                        if content.contains("<thinking>") && content.contains("</thinking>") {
                            let parts = parseThinking(content)
                            if !parts.thinking.isEmpty {
                                DisclosureGroup {
                                    Text(parts.thinking)
                                        .font(.system(.body, design: .serif))
                                        .italic()
                                        .foregroundColor(.secondary)
                                        .padding(.vertical, 4)
                                } label: {
                                    HStack(spacing: 6) {
                                        Image(systemName: "brain")
                                        Text("Thinking Process")
                                    }
                                    .font(.caption)
                                    .foregroundColor(.purple)
                                }
                                .padding(10)
                                .background(Color.purple.opacity(0.04))
                                .cornerRadius(8)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(Color.purple.opacity(0.12), lineWidth: 1)
                                )
                            }
                            
                            if !parts.reply.isEmpty {
                                Text(parts.reply)
                                    .font(.body)
                                    .lineSpacing(4)
                                    .textSelection(.enabled)
                            }
                        } else {
                            Text(content)
                                .font(.body)
                                .lineSpacing(4)
                                .textSelection(.enabled)
                        }
                    }
                }
                .padding(.vertical, 10)
                .padding(.horizontal, 14)
                .background(.thinMaterial)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.primary.opacity(0.08), lineWidth: 1)
                )
                .shadow(color: Color.black.opacity(0.03), radius: 6, y: 3)
                
                Spacer()
            } else if message.role == "tool" {
                Image(systemName: "wrench.adjust.fill")
                    .font(.title3)
                    .foregroundColor(.orange)
                
                VStack(alignment: .leading, spacing: 6) {
                DisclosureGroup {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Tool Call ID:")
                                .font(.caption2)
                                .foregroundColor(.secondary)
                            Text(message.toolCallId ?? "unknown")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundColor(.primary)
                        }
                        
                        if let content = message.content {
                            Text("OUTPUT")
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .foregroundColor(.secondary)
                            
                            ScrollView(.horizontal) {
                                Text(content)
                                    .font(.system(size: 11, design: .monospaced))
                                    .padding(10)
                                    .background(Color(NSColor.textBackgroundColor).opacity(0.5))
                                    .cornerRadius(6)
                                    .textSelection(.enabled)
                            }
                        }
                    }
                    .padding(.vertical, 6)
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "wrench.adjust.fill")
                            .foregroundColor(.orange)
                        Text("Tool: \(message.toolCallId?.prefix(8) ?? "call")")
                            .font(.system(.subheadline, design: .monospaced))
                            .fontWeight(.semibold)
                            .foregroundColor(.orange)
                        Spacer()
                        Text("COMPLETED")
                            .font(.system(size: 8, weight: .bold))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.green.opacity(0.15))
                            .foregroundColor(.green)
                            .cornerRadius(4)
                    }
                }
                .padding(12)
                .background(.ultraThinMaterial)
                .cornerRadius(12)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.orange.opacity(0.18), lineWidth: 1)
                )
            }
                
                Spacer()
            }
        }
        .contextMenu {
            Button("Fork from this message") {
                Task {
                    await viewModel.forkCurrentSession(messageIndex: index, newContent: nil)
                }
            }
            Button("Truncate session from here") {
                Task {
                    await viewModel.truncateCurrentSession(messageIndex: index)
                }
            }
        }
    }
    
    private func parseThinking(_ text: String) -> (thinking: String, reply: String) {
        guard let startRange = text.range(of: "<thinking>"),
              let endRange = text.range(of: "</thinking>") else {
            return ("", text)
        }
        let thinking = String(text[startRange.upperBound..<endRange.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
        let reply = String(text[endRange.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
        return (thinking, reply)
    }
}

// MARK: - Streaming Message Bubble

struct StreamingBubbleView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var thinkingExpanded = true
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "cpu.fill")
                .font(.title2)
                .foregroundColor(.purple)
            
            VStack(alignment: .leading, spacing: 10) {
                // 1. Thinking block
                if !viewModel.streamingThinking.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Button(action: {
                            withAnimation {
                                thinkingExpanded.toggle()
                            }
                        }) {
                            HStack {
                                Image(systemName: "brain.headProfile")
                                    .foregroundColor(.purple)
                                Text("Thinking Process")
                                    .fontWeight(.semibold)
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .rotationEffect(.degrees(thinkingExpanded ? 90 : 0))
                            }
                            .font(.caption)
                            .foregroundColor(.secondary)
                        }
                        .buttonStyle(.plain)
                        
                        if thinkingExpanded {
                            Text(viewModel.streamingThinking)
                                .font(.system(.body, design: .serif))
                                .italic()
                                .foregroundColor(.secondary)
                                .padding(.leading, 8)
                                .padding(.vertical, 4)
                        }
                    }
                    .padding(10)
                    .background(Color.purple.opacity(0.05))
                    .cornerRadius(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.purple.opacity(0.12), lineWidth: 1)
                    )
                }
                
                // 2. Active tool executions
                if !viewModel.streamingEvents.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(viewModel.streamingEvents) { event in
                            StreamingToolCard(event: event)
                        }
                    }
                }
                
                // 3. Final reply text
                if !viewModel.streamingReply.isEmpty {
                    Text(viewModel.streamingReply)
                        .font(.body)
                        .lineSpacing(4)
                }
            }
            
            Spacer()
        }
    }
}

// MARK: - Streaming Tool Execution Card

struct StreamingToolCard: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let event: RunEvent
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "hammer.fill")
                    .foregroundColor(.orange)
                Text("Calling Tool: \(event.toolName ?? "Unknown")")
                    .fontWeight(.medium)
                
                Spacer()
                
                if event.type == "approval_required" {
                    Text("WAITING APPROVAL")
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.yellow)
                        .cornerRadius(4)
                } else if event.type == "tool_result" {
                    Text("COMPLETED")
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.green)
                        .cornerRadius(4)
                } else {
                    ProgressView()
                        .controlSize(.small)
                }
            }
            .font(.caption)
            
            if event.type == "approval_required", let callId = event.toolCallId {
                HStack(spacing: 12) {
                    Button(action: {
                        Task {
                            await viewModel.resolveApproval(approvalId: callId, action: "approve")
                        }
                    }) {
                        Text("Approve")
                            .font(.caption)
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 4)
                            .background(Color.green)
                            .cornerRadius(6)
                    }
                    .buttonStyle(.plain)
                    
                    Button(action: {
                        Task {
                            await viewModel.resolveApproval(approvalId: callId, action: "reject")
                        }
                    }) {
                        Text("Reject")
                            .font(.caption)
                            .foregroundColor(.white)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 4)
                            .background(Color.red)
                            .cornerRadius(6)
                    }
                    .buttonStyle(.plain)
                }
                .padding(.top, 4)
            }
        }
        .padding(8)
        .background(Color.orange.opacity(0.04))
        .cornerRadius(6)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(Color.orange.opacity(0.12), lineWidth: 1)
        )
    }
}

// MARK: - Input Composer View

struct ChatComposerView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    
    var body: some View {
        VStack(spacing: 8) {
            // Options Row
            HStack(spacing: 15) {
                // Agent Selector
                Picker("Agent", selection: $viewModel.selectedAgentName) {
                    ForEach(viewModel.agents) { agent in
                        Text(agent.name).tag(agent.name)
                    }
                }
                .frame(width: 150)
                
                // Model Selector
                Picker("Model", selection: $viewModel.selectedModelId) {
                    Text("Default Model").tag(nil as String?)
                    ForEach(viewModel.models) { model in
                        Text(model.displayName ?? model.modelId).tag(model.modelId as String?)
                    }
                }
                .frame(width: 200)
                .onChange(of: viewModel.selectedModelId) { _ in
                    Task {
                        await viewModel.updateSessionSettings()
                    }
                }
                
                Spacer()
                
                // Deep Thinking Option
                Toggle(isOn: $viewModel.thinkingEnabled) {
                    Text("Deep Thinking")
                        .font(.subheadline)
                }
                .toggleStyle(.checkbox)
                .onChange(of: viewModel.thinkingEnabled) { _ in
                    Task {
                        await viewModel.updateSessionSettings()
                    }
                }
                
                if viewModel.thinkingEnabled {
                    Picker("Effort", selection: $viewModel.thinkingEffort) {
                        Text("Low").tag("low")
                        Text("Medium").tag("medium")
                        Text("High").tag("high")
                    }
                    .frame(width: 110)
                    .onChange(of: viewModel.thinkingEffort) { _ in
                        Task {
                            await viewModel.updateSessionSettings()
                        }
                    }
                }
            }
            .padding(.horizontal)
            .padding(.top, 8)
            
            // Text Area Input
            HStack(alignment: .bottom, spacing: 10) {
                TextEditor(text: $viewModel.inputText)
                    .font(.body)
                    .frame(minHeight: 44, maxHeight: 120)
                    .scrollContentBackground(.hidden)
                    .padding(4)
                    .background(Color(NSColor.textBackgroundColor).opacity(0.5))
                    .cornerRadius(10)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(Color.primary.opacity(0.12), lineWidth: 1)
                    )
                
                Button(action: {
                    Task {
                        await viewModel.sendMessage()
                    }
                }) {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundColor(.white)
                        .frame(width: 36, height: 36)
                        .background(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Color.secondary.opacity(0.4) : Color.accentColor)
                        .clipShape(Circle())
                        .shadow(color: viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Color.clear : Color.accentColor.opacity(0.3), radius: 4, y: 2)
                }
                .buttonStyle(.plain)
                .disabled(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isStreaming)
            }
            .padding([.horizontal, .bottom])
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
}
