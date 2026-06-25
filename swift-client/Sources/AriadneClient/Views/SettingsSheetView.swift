import SwiftUI

enum SettingsPane: String, CaseIterable, Identifiable {
    case general
    case providers
    case models
    case mcp

    var id: String { rawValue }

    var title: String {
        switch self {
        case .general: return "General"
        case .providers: return "Providers"
        case .models: return "Models"
        case .mcp: return "MCP Servers"
        }
    }

    var systemImage: String {
        switch self {
        case .general: return "macwindow"
        case .providers: return "network"
        case .models: return "cpu"
        case .mcp: return "server.rack"
        }
    }
}

struct SettingsSheetView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @Environment(\.dismiss) var dismiss

    @State private var selectedPane: SettingsPane = .general
    @State private var serverAddress = ""

    @State private var showingAddProvider = false
    @State private var providerName = ""
    @State private var providerBaseUrl = ""
    @State private var providerApiKey = ""

    @State private var showingAddMcp = false
    @State private var mcpId = ""
    @State private var mcpName = ""
    @State private var mcpTransport = "stdio"
    @State private var mcpCommand = ""
    @State private var mcpArgs = ""
    @State private var mcpEnv = ""
    @State private var mcpUrl = ""

    var body: some View {
        HStack(spacing: 0) {
            sidebar
            AriadneDivider()
                .frame(width: 1)
            detail
        }
        .frame(width: 820, height: 560)
        .background(AriadneDesign.ColorToken.canvas)
        .onAppear {
            serverAddress = viewModel.serverURLString
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.lg) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Settings")
                    .font(.system(size: 22, weight: .semibold, design: .serif))
                Text("Runtime and workspace controls")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, AriadneDesign.Space.lg)
            .padding(.top, AriadneDesign.Space.xl)

            VStack(spacing: 2) {
                ForEach(SettingsPane.allCases) { pane in
                    Button {
                        selectedPane = pane
                    } label: {
                        HStack(spacing: AriadneDesign.Space.md) {
                            Image(systemName: pane.systemImage)
                                .frame(width: 16)
                                .foregroundStyle(selectedPane == pane ? AriadneDesign.ColorToken.accent : .secondary)
                            Text(pane.title)
                                .font(.system(size: 13, weight: selectedPane == pane ? .semibold : .regular))
                                .foregroundStyle(.primary)
                            Spacer()
                        }
                        .padding(.horizontal, AriadneDesign.Space.md)
                        .padding(.vertical, AriadneDesign.Space.sm)
                        .background(
                            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                                .fill(selectedPane == pane ? AriadneDesign.ColorToken.accentSoft : Color.clear)
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, AriadneDesign.Space.sm)

            Spacer()

            HStack(spacing: AriadneDesign.Space.sm) {
                Circle()
                    .fill(viewModel.isLoading ? AriadneDesign.ColorToken.warning : AriadneDesign.ColorToken.success)
                    .frame(width: 7, height: 7)
                Text(viewModel.isLoading ? "Syncing" : "Ready")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .padding(AriadneDesign.Space.lg)
        }
        .frame(width: 188)
        .background(AriadneDesign.ColorToken.surface.opacity(0.72))
    }

    private var detail: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(selectedPane.title)
                        .font(.system(size: 17, weight: .semibold))
                    Text(detailSubtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Done") {
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding(.horizontal, AriadneDesign.Space.xl)
            .padding(.vertical, AriadneDesign.Space.lg)

            AriadneDivider()

            Group {
                switch selectedPane {
                case .general:
                    generalPane
                case .providers:
                    providersPane
                case .models:
                    modelsPane
                case .mcp:
                    mcpPane
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
    }

    private var detailSubtitle: String {
        switch selectedPane {
        case .general: return "Server endpoint and current inventory"
        case .providers: return "Model API providers and sync controls"
        case .models: return "Visible model names and capabilities"
        case .mcp: return "Tool server runtime configuration"
        }
    }

    private var generalPane: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xl) {
                SettingsSection(title: "Daemon Server") {
                    HStack(spacing: AriadneDesign.Space.md) {
                        TextField("Server address", text: $serverAddress)
                            .textFieldStyle(.roundedBorder)
                        Button("Save") {
                            saveServerAddress()
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(serverAddress.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }

                SettingsSection(title: "Workspace Inventory") {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 116), spacing: AriadneDesign.Space.md)], spacing: AriadneDesign.Space.md) {
                        SettingsMetric(title: "Sessions", value: "\(viewModel.sessions.count)", systemImage: "message")
                        SettingsMetric(title: "Workspaces", value: "\(viewModel.workspaces.count)", systemImage: "folder")
                        SettingsMetric(title: "Providers", value: "\(viewModel.providers.count)", systemImage: "network")
                        SettingsMetric(title: "Models", value: "\(viewModel.models.count)", systemImage: "cpu")
                        SettingsMetric(title: "MCP", value: "\(viewModel.mcpServers.count)", systemImage: "server.rack")
                    }
                }
            }
            .padding(AriadneDesign.Space.xl)
        }
    }

    private var providersPane: some View {
        VStack(spacing: 0) {
            paneActionBar(
                primaryTitle: showingAddProvider ? "Cancel" : "Add Provider",
                primaryImage: showingAddProvider ? "xmark" : "plus",
                secondaryTitle: nil,
                secondaryImage: nil,
                primaryAction: {
                    showingAddProvider.toggle()
                    if !showingAddProvider {
                        clearProviderForm()
                    }
                },
                secondaryAction: nil
            )

            if showingAddProvider {
                providerForm
            } else {
                providerList
            }
        }
    }

    private var providerList: some View {
        ScrollView {
            VStack(spacing: AriadneDesign.Space.sm) {
                if viewModel.providers.isEmpty {
                    EmptySettingsState(
                        title: "No providers",
                        detail: "Add a provider before syncing models.",
                        systemImage: "network.slash"
                    )
                } else {
                    ForEach(viewModel.providers) { provider in
                        ProviderSettingsRow(provider: provider)
                            .environmentObject(viewModel)
                    }
                }
            }
            .padding(AriadneDesign.Space.xl)
        }
    }

    private var providerForm: some View {
        ScrollView {
            SettingsSection(title: "Add Model Provider") {
                VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
                    TextField("Name", text: $providerName)
                        .textFieldStyle(.roundedBorder)
                    TextField("Base URL", text: $providerBaseUrl)
                        .textFieldStyle(.roundedBorder)
                    SecureField("API Key", text: $providerApiKey)
                        .textFieldStyle(.roundedBorder)
                    HStack {
                        Spacer()
                        Button("Save Provider") {
                            Task {
                                await viewModel.addProvider(name: providerName, baseUrl: providerBaseUrl, apiKey: providerApiKey)
                                showingAddProvider = false
                                clearProviderForm()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(providerName.isEmpty || providerBaseUrl.isEmpty)
                    }
                }
            }
            .padding(AriadneDesign.Space.xl)
        }
    }

    private var modelsPane: some View {
        ScrollView {
            VStack(spacing: AriadneDesign.Space.sm) {
                if viewModel.models.isEmpty {
                    EmptySettingsState(
                        title: "No models",
                        detail: "Sync from a provider first.",
                        systemImage: "cpu"
                    )
                } else {
                    ForEach(viewModel.models) { model in
                        ModelSettingsRow(model: model)
                            .environmentObject(viewModel)
                    }
                }
            }
            .padding(AriadneDesign.Space.xl)
        }
    }

    private var mcpPane: some View {
        VStack(spacing: 0) {
            paneActionBar(
                primaryTitle: showingAddMcp ? "Cancel" : "Add Server",
                primaryImage: showingAddMcp ? "xmark" : "plus",
                secondaryTitle: "Reload Runtime",
                secondaryImage: "arrow.triangle.2.circlepath",
                primaryAction: {
                    showingAddMcp.toggle()
                    if !showingAddMcp {
                        clearMcpForm()
                    }
                },
                secondaryAction: {
                    Task {
                        await viewModel.reloadMcpRuntime()
                    }
                }
            )

            if showingAddMcp {
                mcpForm
            } else {
                mcpList
            }
        }
    }

    private var mcpList: some View {
        ScrollView {
            VStack(spacing: AriadneDesign.Space.sm) {
                if viewModel.mcpServers.isEmpty {
                    EmptySettingsState(
                        title: "No MCP servers",
                        detail: "Configure a local command or streamable HTTP endpoint.",
                        systemImage: "server.rack"
                    )
                } else {
                    ForEach(viewModel.mcpServers) { server in
                        McpSettingsRow(server: server)
                            .environmentObject(viewModel)
                    }
                }
            }
            .padding(AriadneDesign.Space.xl)
        }
    }

    private var mcpForm: some View {
        ScrollView {
            SettingsSection(title: "Configure MCP Server") {
                VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
                    TextField("Server ID", text: $mcpId)
                        .textFieldStyle(.roundedBorder)
                    TextField("Display Name", text: $mcpName)
                        .textFieldStyle(.roundedBorder)
                    Picker("Transport", selection: $mcpTransport) {
                        Text("STDIO").tag("stdio")
                        Text("Streamable HTTP").tag("streamable_http")
                    }
                    .pickerStyle(.segmented)

                    if mcpTransport == "stdio" {
                        TextField("Command", text: $mcpCommand)
                            .textFieldStyle(.roundedBorder)
                        TextField("Arguments, comma separated", text: $mcpArgs)
                            .textFieldStyle(.roundedBorder)
                        TextField("Env JSON", text: $mcpEnv)
                            .textFieldStyle(.roundedBorder)
                    } else {
                        TextField("Endpoint URL", text: $mcpUrl)
                            .textFieldStyle(.roundedBorder)
                    }

                    HStack {
                        Spacer()
                        Button("Save Server") {
                            saveMcpServer()
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(mcpId.isEmpty || (mcpTransport == "stdio" && mcpCommand.isEmpty) || (mcpTransport == "streamable_http" && mcpUrl.isEmpty))
                    }
                }
            }
            .padding(AriadneDesign.Space.xl)
        }
    }

    private func paneActionBar(
        primaryTitle: String,
        primaryImage: String,
        secondaryTitle: String?,
        secondaryImage: String?,
        primaryAction: @escaping () -> Void,
        secondaryAction: (() -> Void)?
    ) -> some View {
        HStack(spacing: AriadneDesign.Space.sm) {
            Spacer()
            if let secondaryTitle, let secondaryImage, let secondaryAction {
                Button(action: secondaryAction) {
                    Label(secondaryTitle, systemImage: secondaryImage)
                }
                .buttonStyle(.bordered)
            }
            Button(action: primaryAction) {
                Label(primaryTitle, systemImage: primaryImage)
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(.horizontal, AriadneDesign.Space.xl)
        .padding(.vertical, AriadneDesign.Space.md)
        .background(AriadneDesign.ColorToken.canvas)
        .overlay(alignment: .bottom) {
            AriadneDivider()
        }
    }

    private func saveServerAddress() {
        let trimmed = serverAddress.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        viewModel.serverURLString = trimmed
        AriadneNetworkService.shared.serverURLString = trimmed
        Task {
            await viewModel.loadAllData()
        }
    }

    private func clearProviderForm() {
        providerName = ""
        providerBaseUrl = ""
        providerApiKey = ""
    }

    private func saveMcpServer() {
        let argsArray = mcpArgs.split(separator: ",").map { String($0).trimmingCharacters(in: .whitespaces) }
        var envDict: [String: String] = [:]
        if let data = mcpEnv.data(using: .utf8),
           let parsed = try? JSONSerialization.jsonObject(with: data) as? [String: String] {
            envDict = parsed
        }

        let server = McpServerOut(
            serverId: mcpId,
            displayName: mcpName.isEmpty ? nil : mcpName,
            transport: mcpTransport,
            enabled: true,
            required: false,
            startupTimeoutSec: 10,
            toolTimeoutSec: 30,
            command: mcpTransport == "stdio" ? mcpCommand : nil,
            args: mcpTransport == "stdio" ? argsArray : [],
            env: mcpTransport == "stdio" ? envDict : [:],
            cwd: nil,
            url: mcpTransport == "streamable_http" ? mcpUrl : nil,
            bearerToken: nil,
            httpHeaders: [:],
            runtimeStatus: "not_started",
            toolCount: 0,
            lastError: nil
        )

        Task {
            await viewModel.addMcpServer(server: server)
            showingAddMcp = false
            clearMcpForm()
        }
    }

    private func clearMcpForm() {
        mcpId = ""
        mcpName = ""
        mcpCommand = ""
        mcpArgs = ""
        mcpEnv = ""
        mcpUrl = ""
    }
}

struct SettingsSection<Content: View>: View {
    let title: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
            AriadneSectionLabel(title: title)
            content
        }
        .padding(AriadneDesign.Space.lg)
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }
}

struct SettingsMetric: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
            Image(systemName: systemImage)
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(AriadneDesign.ColorToken.accent)
            Text(value)
                .font(.system(size: 22, weight: .semibold, design: .monospaced))
            Text(title)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(AriadneDesign.Space.md)
        .background(AriadneDesign.ColorToken.elevated, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                .stroke(AriadneDesign.ColorToken.softLine, lineWidth: 1)
        )
    }
}

struct EmptySettingsState: View {
    let title: String
    let detail: String
    let systemImage: String

    var body: some View {
        VStack(spacing: AriadneDesign.Space.md) {
            Image(systemName: systemImage)
                .font(.system(size: 26))
                .foregroundStyle(.tertiary)
            Text(title)
                .font(.system(size: 14, weight: .semibold))
            Text(detail)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 190)
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }
}

struct ProviderSettingsRow: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let provider: ProviderOut

    var body: some View {
        HStack(alignment: .top, spacing: AriadneDesign.Space.md) {
            Image(systemName: "network")
                .foregroundStyle(AriadneDesign.ColorToken.accent)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
                HStack(spacing: AriadneDesign.Space.sm) {
                    Text(provider.name)
                        .font(.system(size: 14, weight: .semibold))
                    if provider.isDefault {
                        AriadneBadge(text: "Default", color: AriadneDesign.ColorToken.success)
                    }
                }
                Text(provider.baseUrl)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                if let hint = provider.apiKeyHint {
                    Label("Key \(hint)", systemImage: "key")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Button {
                Task {
                    await viewModel.syncProviderModels(providerId: provider.id)
                }
            } label: {
                Label("Sync", systemImage: "arrow.triangle.2.circlepath")
            }
            .buttonStyle(.bordered)
            Button(role: .destructive) {
                Task {
                    await viewModel.removeProvider(providerId: provider.id)
                }
            } label: {
                Image(systemName: "trash")
            }
            .buttonStyle(.borderless)
        }
        .padding(AriadneDesign.Space.lg)
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }
}

struct ModelSettingsRow: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let model: ModelOut
    @State private var draftName: String
    @FocusState private var isNameFocused: Bool

    init(model: ModelOut) {
        self.model = model
        _draftName = State(initialValue: model.displayName ?? model.modelId)
    }

    var body: some View {
        HStack(alignment: .center, spacing: AriadneDesign.Space.md) {
            Image(systemName: "cpu")
                .foregroundStyle(AriadneDesign.ColorToken.accent)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
                TextField("Display name", text: $draftName)
                    .textFieldStyle(.plain)
                    .font(.system(size: 14, weight: .semibold))
                    .focused($isNameFocused)
                    .onSubmit { commitRename() }
                    .onChange(of: isNameFocused) { _, focused in
                        if !focused {
                            commitRename()
                        }
                    }

                Text(model.modelId)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)

                HStack(spacing: AriadneDesign.Space.xs) {
                    if model.supportsThinking {
                        AriadneBadge(text: "Thinking", color: AriadneDesign.ColorToken.accent)
                    }
                    if model.supportsTools {
                        AriadneBadge(text: "Tools", color: .secondary)
                    }
                }
            }
            Spacer()
            Toggle("", isOn: Binding(
                get: { model.enabled },
                set: { _ in
                    Task {
                        await viewModel.toggleModel(model)
                    }
                }
            ))
            .toggleStyle(.switch)
            .labelsHidden()
        }
        .padding(AriadneDesign.Space.lg)
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
        .onChange(of: model.displayName) { _, newDisplayName in
            if !isNameFocused {
                draftName = newDisplayName ?? model.modelId
            }
        }
    }

    private func commitRename() {
        let trimmed = draftName.trimmingCharacters(in: .whitespacesAndNewlines)
        let currentName = model.displayName ?? model.modelId
        guard !trimmed.isEmpty else {
            draftName = currentName
            return
        }
        guard trimmed != currentName else { return }
        Task {
            await viewModel.renameModel(model, newDisplayName: trimmed)
        }
    }
}

struct McpSettingsRow: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let server: McpServerOut

    var body: some View {
        HStack(alignment: .top, spacing: AriadneDesign.Space.md) {
            Image(systemName: "server.rack")
                .foregroundStyle(AriadneDesign.ColorToken.accent)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
                HStack(spacing: AriadneDesign.Space.sm) {
                    Text(server.displayName ?? server.serverId)
                        .font(.system(size: 14, weight: .semibold))
                    AriadneBadge(text: server.runtimeStatus, color: statusColor)
                    AriadneBadge(text: "\(server.toolCount) tools", color: .secondary)
                }
                if let command = server.command {
                    Text(([command] + server.args).joined(separator: " "))
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                if let url = server.url {
                    Text(url)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                if let error = server.lastError {
                    Text(error)
                        .font(.system(size: 11))
                        .foregroundStyle(AriadneDesign.ColorToken.danger)
                        .lineLimit(2)
                }
            }
            Spacer()
            Button(role: .destructive) {
                Task {
                    await viewModel.removeMcpServer(serverId: server.serverId)
                }
            } label: {
                Image(systemName: "trash")
            }
            .buttonStyle(.borderless)
        }
        .padding(AriadneDesign.Space.lg)
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }

    private var statusColor: Color {
        switch server.runtimeStatus.lowercased() {
        case "connected", "running": return AriadneDesign.ColorToken.success
        case "failed", "error": return AriadneDesign.ColorToken.danger
        default: return AriadneDesign.ColorToken.warning
        }
    }
}
