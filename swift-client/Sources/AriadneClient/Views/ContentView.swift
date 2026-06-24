import SwiftUI

struct ContentView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var showingSettingsSheet = false
    
    var body: some View {
        NavigationSplitView {
            SessionSidebarView()
                .navigationSplitViewColumnWidth(min: 240, ideal: 280, max: 360)
        } detail: {
            if viewModel.currentSessionDetail != nil {
                ChatView()
            } else {
                WelcomeView()
            }
        }
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button(action: {
                    showingSettingsSheet.toggle()
                }) {
                    Label("Settings", systemImage: "gearshape")
                }
                .help("Settings & Servers")
            }
        }
        .sheet(isPresented: $showingSettingsSheet) {
            SettingsSheetView()
                .environmentObject(viewModel)
        }
        .alert("Server Notice", isPresented: Binding(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.errorMessage = nil } }
        )) {
            Button("Dismiss", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }
}

struct WelcomeView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var isHoveringNew = false
    @State private var isHoveringWorkspace = false
    
    var body: some View {
        VStack(spacing: 30) {
            Spacer()
            
            // Premium Gradient Logo placeholder
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.blue, Color.purple, Color.pink],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 80, height: 80)
                    .blur(radius: 8)
                    .opacity(0.6)
                
                Image(systemName: "square.stack.3d.up.fill")
                    .font(.system(size: 40, weight: .semibold))
                    .foregroundColor(.white)
            }
            
            VStack(spacing: 10) {
                Text("Welcome to Ariadne")
                    .font(.system(size: 32, weight: .bold, design: .rounded))
                Text("Native macOS desktop companion for local python agent runtime")
                    .font(.title3)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 450)
            }
            
            HStack(spacing: 20) {
                // New Session Button
                Button(action: {
                    Task {
                        await viewModel.createNewSession()
                    }
                }) {
                    HStack {
                        Image(systemName: "plus.bubble.fill")
                        Text("New Coding Session")
                    }
                    .padding()
                    .frame(width: 220)
                    .background(Color.accentColor)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                    .shadow(color: Color.accentColor.opacity(0.3), radius: 8, y: 4)
                }
                .buttonStyle(.plain)
                .scaleEffect(isHoveringNew ? 1.02 : 1.0)
                .animation(.spring(response: 0.2, dampingFraction: 0.6), value: isHoveringNew)
                .onHover { isHoveringNew = $0 }
                
                // Select Workspace
                Button(action: {
                    // Create session with workspace selection placeholder
                    Task {
                        if let firstWorkspace = viewModel.workspaces.first {
                            await viewModel.createNewSession(
                                workspacePath: firstWorkspace.path,
                                workspaceName: firstWorkspace.name
                            )
                        } else {
                            await viewModel.createNewSession()
                        }
                    }
                }) {
                    HStack {
                        Image(systemName: "folder.badge.plus")
                        Text("Start with Workspace")
                    }
                    .padding()
                    .frame(width: 220)
                    .background(Color(NSColor.controlBackgroundColor))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.secondary.opacity(0.3), lineWidth: 1)
                    )
                    .cornerRadius(12)
                }
                .buttonStyle(.plain)
                .scaleEffect(isHoveringWorkspace ? 1.02 : 1.0)
                .animation(.spring(response: 0.2, dampingFraction: 0.6), value: isHoveringWorkspace)
                .onHover { isHoveringWorkspace = $0 }
            }
            .padding(.top, 20)
            
            Spacer()
            
            // Footer displaying server connection status
            HStack(spacing: 8) {
                Circle()
                    .fill(Color.green)
                    .frame(width: 8, height: 8)
                Text("Connected to \(viewModel.serverURLString)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.bottom, 30)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            LinearGradient(
                colors: [
                    Color(NSColor.windowBackgroundColor),
                    Color(NSColor.underPageBackgroundColor).opacity(0.5)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        )
    }
}

struct SettingsSheetView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var selectedTab = 0
    @State private var serverAddress = ""
    
    // Providers Form State
    @State private var showingAddProvider = false
    @State private var providerName = ""
    @State private var providerBaseUrl = ""
    @State private var providerApiKey = ""
    
    // MCP Form State
    @State private var showingAddMcp = false
    @State private var mcpId = ""
    @State private var mcpName = ""
    @State private var mcpTransport = "stdio"
    @State private var mcpCommand = ""
    @State private var mcpArgs = ""
    @State private var mcpEnv = ""
    @State private var mcpUrl = ""
    
    var body: some View {
        VStack(spacing: 0) {
            TabView(selection: $selectedTab) {
                generalTab()
                    .tabItem { Label("General", systemImage: "macwindow") }
                    .tag(0)
                
                providersTab()
                    .tabItem { Label("Providers", systemImage: "network") }
                    .tag(1)
                
                modelsTab()
                    .tabItem { Label("Models", systemImage: "cpu") }
                    .tag(2)
                
                mcpTab()
                    .tabItem { Label("MCP Servers", systemImage: "server.rack") }
                    .tag(3)
            }
            .padding()
            
            Divider()
            
            HStack {
                Spacer()
                Button("Done") {
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            }
            .padding()
            .background(Color(NSColor.windowBackgroundColor))
        }
        .frame(width: 720, height: 520)
        .onAppear {
            serverAddress = viewModel.serverURLString
        }
    }
    
    // MARK: - General Tab
    @ViewBuilder
    private func generalTab() -> some View {
        Form {
            Section(header: Text("Daemon Server Configuration").font(.headline)) {
                HStack {
                    TextField("Server Address", text: $serverAddress)
                        .textFieldStyle(.roundedBorder)
                    
                    Button("Save") {
                        if !serverAddress.trimmingCharacters(in: .whitespaces).isEmpty {
                            viewModel.serverURLString = serverAddress
                            AriadneNetworkService.shared.serverURLString = serverAddress
                            Task {
                                await viewModel.loadAllData()
                            }
                        }
                    }
                }
                .padding(.vertical, 4)
            }
            
            Section(header: Text("System Statistics").font(.headline)) {
                LabeledContent("Conversations", value: "\(viewModel.sessions.count)")
                LabeledContent("Active Workspaces", value: "\(viewModel.workspaces.count)")
                LabeledContent("Configured Providers", value: "\(viewModel.providers.count)")
                LabeledContent("Available Models", value: "\(viewModel.models.count)")
                LabeledContent("MCP Server Count", value: "\(viewModel.mcpServers.count)")
            }
        }
        .formStyle(.grouped)
    }
    
    // MARK: - Providers Tab
    @ViewBuilder
    private func providersTab() -> some View {
        VStack(spacing: 12) {
            if showingAddProvider {
                addProviderForm()
            } else {
                HStack {
                    Text("Model Providers")
                        .font(.headline)
                    Spacer()
                    Button("Add Provider") {
                        showingAddProvider = true
                    }
                }
                
                List {
                    if viewModel.providers.isEmpty {
                        Text("No providers added yet.")
                            .foregroundColor(.secondary)
                            .italic()
                    } else {
                        ForEach(viewModel.providers) { provider in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text(provider.name)
                                        .font(.body)
                                        .fontWeight(.bold)
                                    
                                    if provider.isDefault {
                                        Text("Default")
                                            .font(.caption2)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2)
                                            .background(Color.green.opacity(0.15))
                                            .foregroundColor(.green)
                                            .cornerRadius(4)
                                    }
                                    
                                    Spacer()
                                    
                                    Button("Sync Models") {
                                        Task {
                                            await viewModel.syncProviderModels(providerId: provider.id)
                                        }
                                    }
                                    .buttonStyle(.borderless)
                                    
                                    Button(action: {
                                        Task {
                                            await viewModel.removeProvider(providerId: provider.id)
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .foregroundColor(.red)
                                    }
                                    .buttonStyle(.plain)
                                }
                                
                                Text(provider.baseUrl)
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundColor(.secondary)
                                
                                if let hint = provider.apiKeyHint {
                                    Text("Key: \(hint)")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
        }
    }
    
    @ViewBuilder
    private func addProviderForm() -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Add Model Provider")
                .font(.headline)
            
            Form {
                TextField("Name", text: $providerName)
                TextField("Base URL", text: $providerBaseUrl)
                SecureField("API Key", text: $providerApiKey)
            }
            .formStyle(.grouped)
            
            HStack {
                Spacer()
                Button("Cancel") {
                    showingAddProvider = false
                    clearProviderForm()
                }
                
                Button("Save") {
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
    
    private func clearProviderForm() {
        providerName = ""
        providerBaseUrl = ""
        providerApiKey = ""
    }
    
    // MARK: - Models Tab
    @ViewBuilder
    private func modelsTab() -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Supported Models")
                .font(.headline)
            Text("Toggle model visibility in conversation selectors or rename their local display name.")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            List {
                if viewModel.models.isEmpty {
                    Text("No models registered. Sync from a Provider first.")
                        .foregroundColor(.secondary)
                        .italic()
                } else {
                    ForEach(viewModel.models) { model in
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    // Custom inline rename textfield
                                    TextField("", text: Binding(
                                        get: { model.displayName ?? model.modelId },
                                        set: { newVal in
                                            Task {
                                                await viewModel.renameModel(model, newDisplayName: newVal)
                                            }
                                        }
                                    ))
                                    .textFieldStyle(.plain)
                                    .font(.body)
                                    .fontWeight(.semibold)
                                    
                                    Spacer()
                                }
                                
                                Text(model.modelId)
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundColor(.secondary)
                                
                                HStack(spacing: 8) {
                                    if model.supportsThinking {
                                        Text("Thinking")
                                            .font(.caption2)
                                            .padding(.horizontal, 4)
                                            .padding(.vertical, 1)
                                            .background(Color.purple.opacity(0.15))
                                            .foregroundColor(.purple)
                                            .cornerRadius(3)
                                    }
                                    if model.supportsTools {
                                        Text("Tools")
                                            .font(.caption2)
                                            .padding(.horizontal, 4)
                                            .padding(.vertical, 1)
                                            .background(Color.blue.opacity(0.15))
                                            .foregroundColor(.blue)
                                            .cornerRadius(3)
                                    }
                                }
                            }
                            
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
                        .padding(.vertical, 4)
                    }
                }
            }
            .listStyle(.inset(alternatesRowBackgrounds: true))
        }
    }
    
    // MARK: - MCP Tab
    @ViewBuilder
    private func mcpTab() -> some View {
        VStack(spacing: 12) {
            if showingAddMcp {
                addMcpForm()
            } else {
                HStack {
                    Text("Model Context Protocol (MCP) Runtime")
                        .font(.headline)
                    Spacer()
                    Button("Reload Runtime") {
                        Task {
                            await viewModel.reloadMcpRuntime()
                        }
                    }
                    .buttonStyle(.borderless)
                    
                    Button("Add Server") {
                        showingAddMcp = true
                    }
                }
                
                List {
                    if viewModel.mcpServers.isEmpty {
                        Text("No MCP servers configured.")
                            .foregroundColor(.secondary)
                            .italic()
                    } else {
                        ForEach(viewModel.mcpServers) { mcp in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text(mcp.displayName ?? mcp.serverId)
                                        .font(.body)
                                        .fontWeight(.bold)
                                    
                                    // Status Badge
                                    Text(mcp.runtimeStatus)
                                        .font(.caption2)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(mcpStatusColor(mcp.runtimeStatus).opacity(0.15))
                                        .foregroundColor(mcpStatusColor(mcp.runtimeStatus))
                                        .cornerRadius(4)
                                    
                                    Spacer()
                                    
                                    Button(action: {
                                        Task {
                                            await viewModel.removeMcpServer(serverId: mcp.serverId)
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .foregroundColor(.red)
                                    }
                                    .buttonStyle(.plain)
                                }
                                
                                if let cmd = mcp.command {
                                    Text("Command: \(cmd) \(mcp.args.joined(separator: " "))")
                                        .font(.system(.caption, design: .monospaced))
                                        .foregroundColor(.secondary)
                                }
                                
                                if let url = mcp.url {
                                    Text("URL: \(url)")
                                        .font(.system(.caption, design: .monospaced))
                                        .foregroundColor(.secondary)
                                }
                                
                                HStack {
                                    Text("Tools registered: \(mcp.toolCount)")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    
                                    if let err = mcp.lastError {
                                        Spacer()
                                        Text(err)
                                            .font(.caption)
                                            .foregroundColor(.red)
                                            .lineLimit(1)
                                    }
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
        }
    }
    
    @ViewBuilder
    private func addMcpForm() -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Configure MCP Server")
                .font(.headline)
            
            Form {
                TextField("Server ID", text: $mcpId)
                TextField("Display Name", text: $mcpName)
                
                Picker("Transport", selection: $mcpTransport) {
                    Text("STDIO (Local Command)").tag("stdio")
                    Text("Streamable HTTP").tag("streamable_http")
                }
                .pickerStyle(.radioGroup)
                
                if mcpTransport == "stdio" {
                    TextField("Command", text: $mcpCommand)
                    TextField("Arguments (comma separated)", text: $mcpArgs)
                    TextField("Env Variables (JSON e.g. {\"PATH\":\"...\"})", text: $mcpEnv)
                } else {
                    TextField("SSE Endpoint URL", text: $mcpUrl)
                }
            }
            .formStyle(.grouped)
            
            HStack {
                Spacer()
                Button("Cancel") {
                    showingAddMcp = false
                    clearMcpForm()
                }
                
                Button("Save") {
                    // Parse args
                    let argsArray = mcpArgs.split(separator: ",").map { String($0).trimmingCharacters(in: .whitespaces) }
                    // Parse env
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
                .buttonStyle(.borderedProminent)
                .disabled(mcpId.isEmpty || (mcpTransport == "stdio" && mcpCommand.isEmpty) || (mcpTransport == "streamable_http" && mcpUrl.isEmpty))
            }
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
    
    private func mcpStatusColor(_ status: String) -> Color {
        switch status.lowercased() {
        case "connected", "running": return .green
        case "failed", "error": return .red
        default: return .orange
        }
    }
}
