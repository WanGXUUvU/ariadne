import SwiftUI

struct SidebarTreeItem: Identifiable {
    let session: SessionSummary
    let depth: Int
    var id: String { session.sessionId }
}

struct SessionSidebarView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var editingSessionId: String?
    @State private var editingName = ""
    @State private var hoveredSessionId: String?
    @State private var showingPluginsSheet = false
    @State private var expandedWorkspaces: [String: Bool] = [:]

    var body: some View {
        VStack(spacing: 0) {
            header
            workspaceTools
            AriadneDivider()
            sessionList
            footer
        }
        .background(AriadneDesign.ColorToken.surface.opacity(0.74))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
            HStack(alignment: .center, spacing: AriadneDesign.Space.sm) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ariadne")
                        .font(.system(size: 18, weight: .semibold, design: .serif))
                        .foregroundStyle(.primary)
                    Text("Workspace")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Button {
                    Task {
                        await viewModel.selectWorkspaceFromDialog()
                    }
                } label: {
                    Image(systemName: "folder.badge.plus")
                }
                .buttonStyle(AriadneIconButtonStyle())
                .help("Open Workspace Folder")

                Button {
                    Task {
                        await viewModel.createNewSession(
                            workspacePath: viewModel.currentSessionDetail?.workspacePath,
                            workspaceName: viewModel.currentSessionDetail?.workspaceName,
                            sessionType: "coding"
                        )
                    }
                } label: {
                    Image(systemName: "square.and.pencil")
                }
                .buttonStyle(AriadneIconButtonStyle())
                .help("New Conversation")
            }

            currentWorkspacePill
        }
        .padding(.horizontal, AriadneDesign.Space.lg)
        .padding(.top, AriadneDesign.Space.xl)
        .padding(.bottom, AriadneDesign.Space.md)
    }

    private var currentWorkspacePill: some View {
        HStack(spacing: AriadneDesign.Space.sm) {
            Image(systemName: "folder")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(AriadneDesign.ColorToken.accent)
            Text(viewModel.currentSessionDetail?.workspaceName ?? "No active workspace")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, AriadneDesign.Space.md)
        .padding(.vertical, AriadneDesign.Space.sm)
        .background(AriadneDesign.ColorToken.accentSoft, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                .stroke(AriadneDesign.ColorToken.accent.opacity(0.12), lineWidth: 1)
        )
    }

    private var workspaceTools: some View {
        HStack(spacing: AriadneDesign.Space.sm) {
            Button {
                showingPluginsSheet = true
            } label: {
                Label("Plugins & Agents", systemImage: "puzzlepiece.extension")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            .sheet(isPresented: $showingPluginsSheet) {
                SkillsAndAgentsSheet()
                    .environmentObject(viewModel)
            }

            Spacer()

            Text("\(viewModel.sessions.count)")
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, AriadneDesign.Space.lg)
        .padding(.bottom, AriadneDesign.Space.md)
    }

    private var sessionList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: AriadneDesign.Space.lg) {
                ForEach(uniqueWorkspacePaths, id: \.self) { workspacePath in
                    workspaceGroup(workspacePath)
                }
            }
            .padding(.horizontal, AriadneDesign.Space.sm)
            .padding(.vertical, AriadneDesign.Space.md)
        }
    }

    @ViewBuilder
    private func workspaceGroup(_ path: String?) -> some View {
        let key = path ?? "global"
        let isExpanded = expandedWorkspaces[key, default: true]
        let treeItems = buildTreeItems(for: path)

        if !treeItems.isEmpty {
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
                Button {
                    expandedWorkspaces[key] = !isExpanded
                } label: {
                    HStack(spacing: AriadneDesign.Space.xs) {
                        Image(systemName: "chevron.right")
                            .font(.system(size: 9, weight: .semibold))
                            .rotationEffect(.degrees(isExpanded ? 90 : 0))
                            .foregroundStyle(.tertiary)
                        Text(workspaceName(for: path))
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                        Spacer()
                    }
                    .padding(.horizontal, AriadneDesign.Space.sm)
                    .padding(.vertical, AriadneDesign.Space.xxs)
                }
                .buttonStyle(.plain)

                if isExpanded {
                    VStack(spacing: 2) {
                        ForEach(treeItems) { item in
                            sessionRow(item)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func sessionRow(_ item: SidebarTreeItem) -> some View {
        let session = item.session
        let isSelected = session.sessionId == viewModel.currentSessionId
        let isHovered = hoveredSessionId == session.sessionId

        HStack(alignment: .top, spacing: AriadneDesign.Space.sm) {
            if item.depth > 0 {
                Image(systemName: "arrow.turn.down.right")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(.tertiary)
                    .padding(.leading, CGFloat(item.depth - 1) * 12)
                    .padding(.top, 3)
            }

            Image(systemName: session.sessionType == "coding" ? "terminal" : "text.bubble")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(isSelected ? AriadneDesign.ColorToken.accent : .secondary)
                .frame(width: 16)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 2) {
                if editingSessionId == session.sessionId {
                    TextField("", text: $editingName, onCommit: {
                        commitSessionRename(session.sessionId)
                    })
                    .textFieldStyle(.plain)
                    .font(.system(size: 13, weight: .medium))
                } else {
                    Text(session.sessionName ?? "New Session")
                        .font(.system(size: 13, weight: isSelected ? .semibold : .medium))
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                }

                Text(previewText(for: session))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer(minLength: AriadneDesign.Space.xs)

            if isHovered && editingSessionId != session.sessionId {
                HStack(spacing: 2) {
                    Button {
                        editingSessionId = session.sessionId
                        editingName = session.sessionName ?? ""
                    } label: {
                        Image(systemName: "pencil")
                    }
                    .buttonStyle(AriadneIconButtonStyle())
                    .help("Rename")

                    Button(role: .destructive) {
                        let targetId = session.sessionId
                        Task {
                            await viewModel.deleteSession(targetId)
                        }
                    } label: {
                        Image(systemName: "trash")
                    }
                    .buttonStyle(AriadneIconButtonStyle())
                    .help("Delete")
                }
            }
        }
        .padding(.horizontal, AriadneDesign.Space.sm)
        .padding(.vertical, 7)
        .background(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                .fill(isSelected ? AriadneDesign.ColorToken.accentSoft : (isHovered ? Color.primary.opacity(0.035) : Color.clear))
        )
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                .stroke(isSelected ? AriadneDesign.ColorToken.accent.opacity(0.16) : Color.clear, lineWidth: 1)
        )
        .contentShape(Rectangle())
        .onTapGesture {
            if editingSessionId != session.sessionId {
                Task {
                    await viewModel.selectSession(session.sessionId)
                }
            }
        }
        .onHover { hovered in
            hoveredSessionId = hovered ? session.sessionId : (hoveredSessionId == session.sessionId ? nil : hoveredSessionId)
        }
    }

    private var footer: some View {
        VStack(spacing: AriadneDesign.Space.md) {
            AriadneDivider()

            if let detail = viewModel.currentSessionDetail,
               let contextTokens = detail.contextTokens {
                let maxTokens = viewModel.models.first(where: { $0.modelId == detail.modelId })?.contextLength ?? 128000
                ContextMeterView(contextTokens: contextTokens, contextLength: maxTokens)
                    .padding(.horizontal, AriadneDesign.Space.md)
            }

            HStack(spacing: AriadneDesign.Space.sm) {
                Circle()
                    .fill(viewModel.isStreaming ? AriadneDesign.ColorToken.warning : AriadneDesign.ColorToken.success)
                    .frame(width: 7, height: 7)
                Text(viewModel.isStreaming ? "Running" : "Ready")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.secondary)
                Spacer()
                Text(viewModel.serverURLString.replacingOccurrences(of: "http://", with: ""))
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
            }
            .padding(.horizontal, AriadneDesign.Space.lg)
            .padding(.bottom, AriadneDesign.Space.md)
        }
    }

    private var uniqueWorkspacePaths: [String?] {
        var paths: [String?] = []
        for workspace in viewModel.workspaces {
            paths.append(workspace.path)
        }
        for session in viewModel.sessions where !paths.contains(session.workspacePath) {
            paths.append(session.workspacePath)
        }
        if !paths.contains(nil) {
            paths.append(nil)
        }
        return paths
    }

    private func workspaceName(for path: String?) -> String {
        guard let path else { return "Global Sessions" }
        if let workspace = viewModel.workspaces.first(where: { $0.path == path }) {
            return workspace.name
        }
        return URL(fileURLWithPath: path).lastPathComponent
    }

    private func previewText(for session: SessionSummary) -> String {
        if session.sessionId == viewModel.currentSessionId,
           let detail = viewModel.currentSessionDetail,
           let preview = previewText(from: detail.state.messages) {
            return preview
        }
        if let preview = session.lastReplyPreview, !preview.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return preview
        }
        if session.messageCount > 0 {
            return "\(session.messageCount) messages"
        }
        return "Empty conversation"
    }

    private func previewText(from messages: [ChatMessage]) -> String? {
        var visibleMessages = messages
        if let last = visibleMessages.last,
           last.role == "user",
           let lastContent = last.content?.trimmingCharacters(in: .whitespacesAndNewlines),
           !lastContent.isEmpty,
           visibleMessages.dropLast().contains(where: {
               $0.role == "user" && $0.content?.trimmingCharacters(in: .whitespacesAndNewlines) == lastContent
           }) {
            visibleMessages.removeLast()
        }

        for message in visibleMessages.reversed() {
            if let content = message.content?.trimmingCharacters(in: .whitespacesAndNewlines), !content.isEmpty {
                let prefix = message.role == "tool" ? "Tool: " : ""
                return prefix + ToolCallFormatter.compact(content, max: 92)
            }
            if message.role == "assistant",
               let toolCall = message.toolCalls?.first {
                return "\(ToolCallFormatter.displayName(toolCall.function.name)) requested"
            }
        }
        return nil
    }

    private func commitSessionRename(_ sessionId: String) {
        let name = editingName.trimmingCharacters(in: .whitespacesAndNewlines)
        editingSessionId = nil
        guard !name.isEmpty else { return }
        Task {
            await viewModel.renameSession(sessionId, newName: name)
        }
    }

    private func buildTreeItems(for workspacePath: String?) -> [SidebarTreeItem] {
        let workspaceSessions = viewModel.sessions.filter { $0.workspacePath == workspacePath }
        let sessionMap = Dictionary(uniqueKeysWithValues: workspaceSessions.map { ($0.sessionId, $0) })

        var childrenMap: [String: [SessionSummary]] = [:]
        for session in workspaceSessions {
            if let parentId = session.parentSessionId {
                childrenMap[parentId, default: []].append(session)
            }
        }

        for key in childrenMap.keys {
            childrenMap[key]?.sort(by: { $0.createdAt < $1.createdAt })
        }

        var roots = workspaceSessions.filter { session in
            if let parentId = session.parentSessionId {
                return sessionMap[parentId] == nil
            }
            return true
        }
        roots.sort(by: { $0.updatedAt > $1.updatedAt })

        var treeItems: [SidebarTreeItem] = []
        func traverse(node: SessionSummary, depth: Int) {
            treeItems.append(SidebarTreeItem(session: node, depth: depth))
            if let children = childrenMap[node.sessionId] {
                for child in children {
                    traverse(node: child, depth: depth + 1)
                }
            }
        }

        for root in roots {
            traverse(node: root, depth: 0)
        }
        return treeItems
    }
}

struct ContextMeterView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let contextTokens: Int
    let contextLength: Int

    @State private var showingBreakdown = false

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.sm) {
            HStack {
                Text("Context")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(fmtTokens(contextTokens)) / \(fmtTokens(contextLength))")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.tertiary)
            }

            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.primary.opacity(0.07))
                    Capsule()
                        .fill(progressColor.opacity(0.82))
                        .frame(width: proxy.size.width * CGFloat(min(1.0, Double(contextTokens) / Double(max(contextLength, 1)))))
                }
            }
            .frame(height: 5)

            HStack {
                Button {
                    showingBreakdown.toggle()
                } label: {
                    Label("Breakdown", systemImage: "info.circle")
                        .font(.system(size: 10))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .popover(isPresented: $showingBreakdown) {
                    VStack(alignment: .leading, spacing: AriadneDesign.Space.sm) {
                        Text("Estimated Token Allocation")
                            .font(.headline)
                        let system = Int(Double(contextTokens) * 0.033)
                        let toolDefs = Int(Double(contextTokens) * 0.087)
                        let messages = Int(Double(contextTokens) * 0.61)
                        let toolResults = Int(Double(contextTokens) * 0.27)
                        Group {
                            Text("System: \(system) tokens (\(pct(system)))")
                            Text("Tool definitions: \(toolDefs) tokens (\(pct(toolDefs)))")
                            Text("Messages: \(messages) tokens (\(pct(messages)))")
                            Text("Tool results: \(toolResults) tokens (\(pct(toolResults)))")
                        }
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                    }
                    .padding()
                    .frame(width: 280)
                }

                Spacer()

                Button {
                    Task {
                        await viewModel.compactCurrentSession()
                    }
                } label: {
                    if viewModel.isCompacting {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Label("Compact", systemImage: "arrow.down.right.and.arrow.up.left")
                            .font(.system(size: 10))
                    }
                }
                .buttonStyle(.plain)
                .foregroundStyle(AriadneDesign.ColorToken.accent)
                .disabled(viewModel.isCompacting)
            }
        }
        .padding(AriadneDesign.Space.md)
        .background(AriadneDesign.ColorToken.elevated, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }

    private func pct(_ count: Int) -> String {
        guard contextLength > 0 else { return "0%" }
        return String(format: "%.1f%%", (Double(count) / Double(contextLength)) * 100)
    }

    private func fmtTokens(_ value: Int) -> String {
        if value >= 1000 {
            return String(format: "%.1fK", Double(value) / 1000.0)
        }
        return String(value)
    }

    private var progressColor: Color {
        let ratio = Double(contextTokens) / Double(max(contextLength, 1))
        if ratio > 0.8 { return AriadneDesign.ColorToken.danger }
        if ratio > 0.6 { return AriadneDesign.ColorToken.warning }
        return AriadneDesign.ColorToken.accent
    }
}
