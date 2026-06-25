import SwiftUI

struct ContentView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var showingSettingsSheet = false

    var body: some View {
        NavigationSplitView {
            SessionSidebarView()
                .navigationSplitViewColumnWidth(min: 250, ideal: 292, max: 360)
        } detail: {
            if viewModel.currentSessionDetail != nil {
                ChatView()
            } else {
                WelcomeView()
            }
        }
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button {
                    showingSettingsSheet.toggle()
                } label: {
                    Label("Settings", systemImage: "gearshape")
                }
                .help("Settings & Servers")
            }
        }
        .sheet(isPresented: $showingSettingsSheet) {
            SettingsSheetView()
                .environmentObject(viewModel)
        }
        .overlay(alignment: .topTrailing) {
            if let message = viewModel.errorMessage {
                ServerNoticeBanner(message: message) {
                    viewModel.errorMessage = nil
                }
                .padding(.top, 12)
                .padding(.trailing, 18)
                .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
    }
}

struct ServerNoticeBanner: View {
    let message: String
    let dismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: AriadneDesign.Space.md) {
            Image(systemName: "exclamationmark.triangle")
                .foregroundStyle(AriadneDesign.ColorToken.warning)
                .padding(.top, 2)

            VStack(alignment: .leading, spacing: 3) {
                Text("Server Notice")
                    .font(.system(size: 12, weight: .semibold))
                Text(message)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }

            Button(action: dismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .semibold))
            }
            .buttonStyle(AriadneIconButtonStyle())
        }
        .padding(AriadneDesign.Space.md)
        .frame(width: 360, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }
}

struct WelcomeView: View {
    @EnvironmentObject var viewModel: SessionViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xxl) {
                header
                actionRow
                workspaceOverview
                connectionFooter
            }
            .padding(.horizontal, AriadneDesign.Space.page)
            .padding(.vertical, 44)
            .frame(maxWidth: 880, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(AriadneDesign.ColorToken.canvas)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
            Text("Ariadne")
                .font(.system(size: 34, weight: .semibold, design: .serif))
                .foregroundStyle(.primary)

            Text("Local agent workspace")
                .font(.system(size: 14))
                .foregroundStyle(.secondary)
        }
        .padding(.top, AriadneDesign.Space.lg)
    }

    private var actionRow: some View {
        HStack(spacing: AriadneDesign.Space.md) {
            WelcomeActionButton(
                title: "New coding session",
                detail: currentWorkspaceLabel,
                systemImage: "terminal"
            ) {
                Task {
                    await viewModel.createNewSession(
                        workspacePath: viewModel.currentSessionDetail?.workspacePath,
                        workspaceName: viewModel.currentSessionDetail?.workspaceName,
                        sessionType: "coding"
                    )
                }
            }

            WelcomeActionButton(
                title: "New assistant session",
                detail: "General conversation",
                systemImage: "bubble.left.and.bubble.right"
            ) {
                Task {
                    await viewModel.createNewSession(sessionType: "assistant")
                }
            }

            WelcomeActionButton(
                title: "Open workspace",
                detail: "Choose local folder",
                systemImage: "folder.badge.plus"
            ) {
                Task {
                    await viewModel.selectWorkspaceFromDialog()
                }
            }
        }
    }

    private var workspaceOverview: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.xl) {
            if !viewModel.workspaces.isEmpty {
                VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
                    AriadneSectionLabel(title: "Recent Workspaces", detail: "\(viewModel.workspaces.count) known")
                    VStack(spacing: 0) {
                        ForEach(Array(viewModel.workspaces.prefix(5).enumerated()), id: \.element.id) { index, workspace in
                            RecentWorkspaceRow(workspace: workspace)
                            if index < min(viewModel.workspaces.count, 5) - 1 {
                                AriadneDivider()
                                    .padding(.leading, 30)
                            }
                        }
                    }
                    .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                            .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
                    )
                }
            }

            let recentSessions = viewModel.sessions.prefix(5)
            if !recentSessions.isEmpty {
                VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
                    AriadneSectionLabel(title: "Recent Sessions", detail: "\(viewModel.sessions.count) total")
                    VStack(spacing: 0) {
                        ForEach(Array(recentSessions.enumerated()), id: \.element.id) { index, session in
                            RecentSessionRow(session: session)
                            if index < min(viewModel.sessions.count, 5) - 1 {
                                AriadneDivider()
                                    .padding(.leading, 30)
                            }
                        }
                    }
                    .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                            .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
                    )
                }
            }
        }
    }

    private var connectionFooter: some View {
        HStack(spacing: AriadneDesign.Space.sm) {
            Circle()
                .fill(viewModel.isLoading ? AriadneDesign.ColorToken.warning : AriadneDesign.ColorToken.success)
                .frame(width: 7, height: 7)
            Text(viewModel.isLoading ? "Syncing \(viewModel.serverURLString)" : "Connected to \(viewModel.serverURLString)")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer()
        }
        .padding(.top, AriadneDesign.Space.sm)
    }

    private var currentWorkspaceLabel: String {
        viewModel.currentSessionDetail?.workspaceName ?? "Current workspace"
    }
}

struct WelcomeActionButton: View {
    let title: String
    let detail: String
    let systemImage: String
    let action: () -> Void
    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
                Image(systemName: systemImage)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(AriadneDesign.ColorToken.accent)
                    .frame(width: 24, height: 24, alignment: .leading)

                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.primary)
                    Text(detail)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 94, alignment: .leading)
            .padding(AriadneDesign.Space.lg)
            .background(isHovered ? AriadneDesign.ColorToken.elevated : AriadneDesign.ColorToken.surface)
            .clipShape(RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                    .stroke(isHovered ? AriadneDesign.ColorToken.accent.opacity(0.22) : AriadneDesign.ColorToken.line, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}

struct RecentWorkspaceRow: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let workspace: WorkspaceSummary
    @State private var isHovered = false

    var body: some View {
        Button {
            Task {
                await viewModel.createNewSession(
                    workspacePath: workspace.path,
                    workspaceName: workspace.name,
                    sessionType: "coding"
                )
            }
        } label: {
            HStack(spacing: AriadneDesign.Space.md) {
                Image(systemName: "folder")
                    .foregroundStyle(AriadneDesign.ColorToken.accent)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 2) {
                    Text(workspace.name)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                    Text(workspace.path)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.tertiary)
                    .opacity(isHovered ? 1 : 0)
            }
            .padding(.horizontal, AriadneDesign.Space.lg)
            .padding(.vertical, AriadneDesign.Space.md)
            .background(isHovered ? AriadneDesign.ColorToken.accentSoft : Color.clear)
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}

struct RecentSessionRow: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let session: SessionSummary
    @State private var isHovered = false

    var body: some View {
        Button {
            Task {
                await viewModel.selectSession(session.sessionId)
            }
        } label: {
            HStack(spacing: AriadneDesign.Space.md) {
                Image(systemName: session.sessionType == "coding" ? "terminal" : "text.bubble")
                    .foregroundStyle(.secondary)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 2) {
                    Text(session.sessionName ?? "Untitled Session")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                    Text(session.lastReplyPreview?.isEmpty == false ? session.lastReplyPreview! : "Empty conversation")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer()
                AriadneBadge(text: session.sessionType == "assistant" ? "Assistant" : "Coding", color: .secondary)
                    .opacity(isHovered ? 1 : 0.65)
            }
            .padding(.horizontal, AriadneDesign.Space.lg)
            .padding(.vertical, AriadneDesign.Space.md)
            .background(isHovered ? AriadneDesign.ColorToken.accentSoft : Color.clear)
        }
        .buttonStyle(.plain)
        .onHover { isHovered = $0 }
    }
}
