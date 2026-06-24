import SwiftUI

struct SidebarTreeItem: Identifiable {
    let session: SessionSummary
    let depth: Int
    var id: String { session.sessionId }
}

struct SessionSidebarView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var editingSessionId: String? = nil
    @State private var editingName: String = ""
    @State private var hoveredSessionId: String? = nil
    @State private var showingPluginsSheet = false
    @State private var expandedWorkspaces: [String: Bool] = [:]
    
    var body: some View {
        VStack(spacing: 0) {
            // Sidebar Header
            HStack {
                Text("Ariadne workspace")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                // Choose Workspace Folder
                Button(action: {
                    Task {
                        await viewModel.selectWorkspaceFromDialog()
                    }
                }) {
                    Image(systemName: "folder.badge.plus")
                        .font(.title3)
                        .foregroundColor(.primary)
                }
                .buttonStyle(.plain)
                .help("Open Workspace Folder")
                
                // New Session Button
                Button(action: {
                    Task {
                        await viewModel.createNewSession(
                            workspacePath: viewModel.currentSessionDetail?.workspacePath,
                            workspaceName: viewModel.currentSessionDetail?.workspaceName
                        )
                    }
                }) {
                    Image(systemName: "square.and.pencil")
                        .font(.title3)
                        .foregroundColor(.primary)
                }
                .buttonStyle(.plain)
                .help("New Conversation")
            }
            .padding(.horizontal)
            .padding(.top, 20)
            .padding(.bottom, 10)
            
            // Plugins & Custom Agents Button
            HStack {
                Button(action: {
                    showingPluginsSheet = true
                }) {
                    Label("Plugins & Agents", systemImage: "puzzlepiece.extension")
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.secondary.opacity(0.15))
                        .cornerRadius(6)
                }
                .buttonStyle(.plain)
                .sheet(isPresented: $showingPluginsSheet) {
                    SkillsAndAgentsSheet()
                        .environmentObject(viewModel)
                }
                Spacer()
            }
            .padding(.horizontal)
            .padding(.bottom, 10)
            
            // Session Groups (by Workspaces)
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    ForEach(uniqueWorkspacePaths, id: \.self) { wsPath in
                        workspaceGroup(wsPath)
                    }
                }
                .padding(.horizontal, 8)
            }
            
            Spacer()
            
            // Context Compaction Meter
            if let detail = viewModel.currentSessionDetail,
               let contextTokens = detail.contextTokens {
                let maxTokens = viewModel.models.first(where: { $0.modelId == detail.modelId })?.contextLength ?? 128000
                ContextMeterView(contextTokens: contextTokens, contextLength: maxTokens)
                    .padding(.horizontal, 10)
                    .padding(.bottom, 10)
            }
            
            // Workspace selector footer
            VStack(spacing: 8) {
                Divider()
                HStack {
                    Image(systemName: "folder")
                        .foregroundColor(.secondary)
                    
                    if let workspaceName = viewModel.currentSessionDetail?.workspaceName {
                        Text(workspaceName)
                            .font(.footnote)
                            .fontWeight(.medium)
                            .lineLimit(1)
                    } else {
                        Text("No active workspace")
                            .font(.footnote)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                }
                .padding(.horizontal)
                .padding(.vertical, 12)
            }
            .background(Color(NSColor.windowBackgroundColor).opacity(0.4))
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
    
    // MARK: - Workspace Group view builder
    @ViewBuilder
    private func workspaceGroup(_ path: String?) -> some View {
        let key = path ?? "global"
        let isExpanded = expandedWorkspaces[key, default: true]
        let treeItems = buildTreeItems(for: path)
        
        if !treeItems.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                // Header toggle button
                Button(action: {
                    expandedWorkspaces[key] = !isExpanded
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: isExpanded ? "chevron.down" : "chevron.right")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        Text(workspaceName(for: path))
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                .padding(.vertical, 2)
                
                if isExpanded {
                    VStack(spacing: 4) {
                        ForEach(treeItems) { item in
                            sessionRow(item)
                        }
                    }
                }
            }
        }
    }
    
    // MARK: - Session row builder
    @ViewBuilder
    private func sessionRow(_ item: SidebarTreeItem) -> some View {
        let session = item.session
        let isSelected = (session.sessionId == viewModel.currentSessionId)
        
        HStack(spacing: 6) {
            // Indentation & Connection lines for branched forks
            if item.depth > 0 {
                Image(systemName: "arrow.turn.down.right")
                    .foregroundColor(isSelected ? .white.opacity(0.7) : .secondary.opacity(0.6))
                    .font(.caption)
                    .padding(.leading, CGFloat(item.depth - 1) * 12)
            }
            
            Image(systemName: session.sessionType == "coding" ? "terminal" : "bubble.left.and.bubble.right")
                .foregroundColor(isSelected ? .white : .secondary)
                .frame(width: 18)
            
            VStack(alignment: .leading, spacing: 2) {
                if editingSessionId == session.sessionId {
                    TextField("", text: $editingName, onCommit: {
                        let targetId = session.sessionId
                        let name = editingName
                        editingSessionId = nil
                        Task {
                            await viewModel.renameSession(targetId, newName: name)
                        }
                    })
                    .textFieldStyle(.plain)
                    .foregroundColor(isSelected ? .white : .primary)
                    .font(.body)
                } else {
                    Text(session.sessionName ?? "New Session")
                        .font(.body)
                        .fontWeight(isSelected ? .medium : .regular)
                        .foregroundColor(isSelected ? .white : .primary)
                        .lineLimit(1)
                }
                
                if let preview = session.lastReplyPreview, !preview.isEmpty {
                    Text(preview)
                        .font(.caption)
                        .foregroundColor(isSelected ? .white.opacity(0.8) : .secondary)
                        .lineLimit(1)
                } else {
                    Text("Empty conversation")
                        .font(.caption)
                        .foregroundColor(isSelected ? .white.opacity(0.6) : .secondary)
                        .italic()
                }
            }
            
            Spacer()
            
            // Hover action icons
            if hoveredSessionId == session.sessionId && editingSessionId != session.sessionId {
                HStack(spacing: 8) {
                    Button(action: {
                        editingSessionId = session.sessionId
                        editingName = session.sessionName ?? ""
                    }) {
                        Image(systemName: "pencil")
                            .foregroundColor(isSelected ? .white : .secondary)
                    }
                    .buttonStyle(.plain)
                    
                    Button(action: {
                        let targetId = session.sessionId
                        Task {
                            await viewModel.deleteSession(targetId)
                        }
                    }) {
                        Image(systemName: "trash")
                            .foregroundColor(isSelected ? .white : .red.opacity(0.8))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(.vertical, 6)
        .padding(.horizontal, 8)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isSelected ? Color.accentColor : (hoveredSessionId == session.sessionId ? Color.secondary.opacity(0.1) : Color.clear))
        )
        .onTapGesture {
            if editingSessionId != session.sessionId {
                Task {
                    await viewModel.selectSession(session.sessionId)
                }
            }
        }
        .onHover { isHovered in
            if isHovered {
                hoveredSessionId = session.sessionId
            } else if hoveredSessionId == session.sessionId {
                hoveredSessionId = nil
            }
        }
    }
    
    // MARK: - Tree and workspace helper methods
    
    private var uniqueWorkspacePaths: [String?] {
        var paths: [String?] = []
        for ws in viewModel.workspaces {
            paths.append(ws.path)
        }
        for s in viewModel.sessions {
            if let path = s.workspacePath, !paths.contains(path) {
                paths.append(path)
            }
        }
        if !paths.contains(nil) {
            paths.append(nil)
        }
        return paths
    }
    
    private func workspaceName(for path: String?) -> String {
        if let path {
            if let ws = viewModel.workspaces.first(where: { $0.path == path }) {
                return ws.name
            }
            return URL(fileURLWithPath: path).lastPathComponent
        }
        return "Global Sessions"
    }
    
    private func buildTreeItems(for workspacePath: String?) -> [SidebarTreeItem] {
        let wsSessions = viewModel.sessions.filter { $0.workspacePath == workspacePath }
        let sessionMap = Dictionary(uniqueKeysWithValues: wsSessions.map { ($0.sessionId, $0) })
        
        var childrenMap: [String: [SessionSummary]] = [:]
        for s in wsSessions {
            if let parentId = s.parentSessionId {
                childrenMap[parentId, default: []].append(s)
            }
        }
        
        for key in childrenMap.keys {
            childrenMap[key]?.sort(by: { $0.createdAt < $1.createdAt })
        }
        
        var roots = wsSessions.filter { s in
            if let parentId = s.parentSessionId {
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

// MARK: - Context Meter Helper View
struct ContextMeterView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let contextTokens: Int
    let contextLength: Int
    
    @State private var showingBreakdown = false
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Context Window")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(fmtTokens(contextTokens))/\(fmtTokens(contextLength)) (\(pctText)%)")
                    .font(.system(.caption, design: .monospaced))
                    .foregroundColor(.secondary)
            }
            
            // Progress Bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color.secondary.opacity(0.2))
                    
                    RoundedRectangle(cornerRadius: 3)
                        .fill(progressColor)
                        .frame(width: geo.size.width * CGFloat(min(1.0, Double(contextTokens) / Double(contextLength))))
                }
            }
            .frame(height: 5)
            
            HStack {
                // Info button for breakdown popover
                Button(action: {
                    showingBreakdown.toggle()
                }) {
                    Label("Breakdown", systemImage: "info.circle")
                        .font(.caption2)
                        .foregroundColor(.accentColor)
                }
                .buttonStyle(.plain)
                .popover(isPresented: $showingBreakdown) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Estimated Token Allocation")
                            .font(.headline)
                            .padding(.bottom, 4)
                        
                        let sys = Int(Double(contextTokens) * 0.033)
                        let toolDefs = Int(Double(contextTokens) * 0.087)
                        let msgs = Int(Double(contextTokens) * 0.61)
                        let toolRes = Int(Double(contextTokens) * 0.27)
                        
                        Group {
                            Text("System Instructions: \(sys) tokens (\(pct(sys)))")
                            Text("Tool Definitions: \(toolDefs) tokens (\(pct(toolDefs)))")
                            Text("User Messages: \(msgs) tokens (\(pct(msgs)))")
                            Text("Tool Results: \(toolRes) tokens (\(pct(toolRes)))")
                        }
                        .font(.subheadline)
                    }
                    .padding()
                    .frame(width: 280)
                }
                
                Spacer()
                
                // Compact button
                Button(action: {
                    Task {
                        await viewModel.compactCurrentSession()
                    }
                }) {
                    HStack(spacing: 4) {
                        if viewModel.isCompacting {
                            ProgressView()
                                .controlSize(.small)
                                .scaleEffect(0.5)
                        } else {
                            Image(systemName: "arrow.down.right.and.arrow.up.left")
                        }
                        Text(viewModel.isCompacting ? "Compacting..." : "Compact")
                    }
                    .font(.caption2)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Color.secondary.opacity(0.15))
                    .cornerRadius(4)
                }
                .buttonStyle(.plain)
                .disabled(viewModel.isCompacting)
            }
        }
        .padding(10)
        .background(Color.secondary.opacity(0.08))
        .cornerRadius(10)
    }
    
    private var pctText: String {
        guard contextLength > 0 else { return "0" }
        return String(format: "%.0f", (Double(contextTokens) / Double(contextLength)) * 100)
    }
    
    private func pct(_ count: Int) -> String {
        guard contextLength > 0 else { return "0%" }
        return String(format: "%.1f%%", (Double(count) / Double(contextLength)) * 100)
    }
    
    private func fmtTokens(_ n: Int) -> String {
        if n >= 1000 {
            return String(format: "%.1fK", Double(n) / 1000.0)
        }
        return String(n)
    }
    
    private var progressColor: Color {
        let ratio = Double(contextTokens) / Double(contextLength)
        if ratio > 0.8 { return .red }
        if ratio > 0.6 { return .orange }
        return .blue
    }
}
