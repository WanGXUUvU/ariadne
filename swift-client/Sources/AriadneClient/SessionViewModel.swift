import Foundation
import Combine
import SwiftUI

@MainActor
public class SessionViewModel: ObservableObject {
    @Published public var sessions: [SessionSummary] = []
    @Published public var currentSessionId: String? = nil
    @Published public var currentSessionDetail: SessionDetail? = nil
    @Published public var agents: [AgentDefinition] = []
    @Published public var models: [ModelOut] = []
    @Published public var providers: [ProviderOut] = []
    @Published public var workspaces: [WorkspaceSummary] = []
    @Published public var skills: [SkillSummary] = []
    @Published public var mcpServers: [McpServerOut] = []
    @Published public var tools: [String] = []
    
    // Session state settings
    @Published public var selectedAgentName: String = "assistant"
    @Published public var selectedModelId: String? = nil
    @Published public var selectedProviderId: Int? = nil
    @Published public var thinkingEnabled: Bool = false
    @Published public var thinkingEffort: String = "medium"
    
    // Chat state
    @Published public var inputText: String = ""
    @Published public var isStreaming: Bool = false
    @Published public var streamingThinking: String = ""
    @Published public var streamingReply: String = ""
    @Published public var streamingEvents: [RunEvent] = []
    @Published public var activeRunId: String? = nil
    
    // Status message for error alerts/toasts
    @Published public var errorMessage: String? = nil
    @Published public var isLoading: Bool = false
    @Published public var isCompacting: Bool = false
    @Published public var serverURLString: String = "http://127.0.0.1:8000"
    
    private var cancellables = Set<AnyCancellable>()
    
    public init() {
        // Automatically sync configuration when currentSessionDetail changes
        $currentSessionDetail
            .compactMap { $0 }
            .sink { [weak self] detail in
                guard let self else { return }
                self.thinkingEnabled = detail.thinkingEnabled
                self.thinkingEffort = detail.thinkingEffort
                self.selectedModelId = detail.modelId
                self.selectedProviderId = detail.modelProviderId
            }
            .store(in: &cancellables)
    }
    
    // MARK: - Initial Sync
    
    public func loadAllData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let fetchedSessions = AriadneNetworkService.shared.fetchSessions()
            async let fetchedAgents = AriadneNetworkService.shared.fetchAgents()
            async let fetchedModels = AriadneNetworkService.shared.fetchModels()
            async let fetchedProviders = AriadneNetworkService.shared.fetchProviders()
            async let fetchedWorkspaces = AriadneNetworkService.shared.fetchWorkspaces()
            async let fetchedSkills = AriadneNetworkService.shared.fetchSkills()
            async let fetchedMcp = AriadneNetworkService.shared.listMcpServers()
            async let fetchedTools = AriadneNetworkService.shared.fetchTools()
            
            self.sessions = try await fetchedSessions
            self.agents = try await fetchedAgents
            self.models = try await fetchedModels
            self.providers = try await fetchedProviders
            self.workspaces = try await fetchedWorkspaces
            self.skills = try await fetchedSkills
            self.mcpServers = try await fetchedMcp
            self.tools = try await fetchedTools
            
            if currentSessionId == nil, let firstSession = sessions.first {
                await selectSession(firstSession.sessionId)
            }
        } catch {
            self.errorMessage = "Failed to sync data: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Session Actions
    
    public func selectSession(_ sessionId: String) async {
        currentSessionId = sessionId
        isLoading = true
        defer { isLoading = false }
        do {
            let detail = try await tryGetSessionDetailWithRetry(sessionId: sessionId, retryCount: 2)
            self.currentSessionDetail = detail
            
            // Set initial selected values if needed
            if let firstAgent = agents.first(where: { $0.isBuiltin }) {
                self.selectedAgentName = firstAgent.name
            } else if let firstAgent = agents.first {
                self.selectedAgentName = firstAgent.name
            }
        } catch {
            self.errorMessage = "Failed to load session details: \(error.localizedDescription)"
        }
    }
    
    private func tryGetSessionDetailWithRetry(sessionId: String, retryCount: Int) async throws -> SessionDetail {
        var lastError: Error?
        for _ in 0...retryCount {
            do {
                return try await AriadneNetworkService.shared.getSessionDetail(sessionId: sessionId)
            } catch {
                lastError = error
                try? await Task.sleep(nanoseconds: 500_000_000) // Sleep 0.5s before retry
            }
        }
        throw lastError ?? NetworkError.invalidResponse
    }
    
    public func createNewSession(workspacePath: String? = nil, workspaceName: String? = nil) async {
        do {
            let sessionName = "Session \(sessions.count + 1)"
            let newSession = try await AriadneNetworkService.shared.createSession(
                workspacePath: workspacePath,
                workspaceName: workspaceName,
                sessionName: sessionName
            )
            self.sessions.insert(newSession, at: 0)
            await selectSession(newSession.sessionId)
        } catch {
            self.errorMessage = "Failed to create session: \(error.localizedDescription)"
        }
    }
    
    public func renameSession(_ sessionId: String, newName: String) async {
        do {
            let success = try await AriadneNetworkService.shared.renameSession(sessionId: sessionId, sessionName: newName)
            if success {
                if let index = sessions.firstIndex(where: { $0.sessionId == sessionId }) {
                    let old = sessions[index]
                    sessions[index] = SessionSummary(
                        sessionId: old.sessionId,
                        sessionName: newName,
                        createdAt: old.createdAt,
                        updatedAt: Date(),
                        lastAgentName: old.lastAgentName,
                        messageCount: old.messageCount,
                        lastReplyPreview: old.lastReplyPreview,
                        permissionProfile: old.permissionProfile,
                        contextTokens: old.contextTokens,
                        workspacePath: old.workspacePath,
                        workspaceName: old.workspaceName,
                        sessionType: old.sessionType,
                        parentSessionId: old.parentSessionId,
                        forkMessageIndex: old.forkMessageIndex
                    )
                }
                if currentSessionId == sessionId {
                    await selectSession(sessionId)
                }
            }
        } catch {
            self.errorMessage = "Failed to rename session: \(error.localizedDescription)"
        }
    }
    
    public func deleteSession(_ sessionId: String) async {
        do {
            let success = try await AriadneNetworkService.shared.deleteSession(sessionId: sessionId)
            if success {
                sessions.removeAll(where: { $0.sessionId == sessionId })
                if currentSessionId == sessionId {
                    currentSessionId = sessions.first?.sessionId
                    currentSessionDetail = nil
                    if let firstId = currentSessionId {
                        await selectSession(firstId)
                    }
                }
            }
        } catch {
            self.errorMessage = "Failed to delete session: \(error.localizedDescription)"
        }
    }
    
    public func updateSessionSettings() async {
        guard let sessionId = currentSessionId else { return }
        do {
            _ = try await AriadneNetworkService.shared.patchSession(
                sessionId: sessionId,
                modelId: selectedModelId,
                modelProviderId: selectedProviderId,
                thinkingEnabled: thinkingEnabled,
                thinkingEffort: thinkingEffort
            )
            // Refresh detail
            self.currentSessionDetail = try await AriadneNetworkService.shared.getSessionDetail(sessionId: sessionId)
        } catch {
            self.errorMessage = "Failed to save settings: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Message Run / SSE Stream execution
    
    public func sendMessage() async {
        guard let sessionId = currentSessionId, !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        
        let textToSend = inputText
        self.inputText = ""
        
        // Intercept slash command
        let trimmed = textToSend.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed == "/fork" || trimmed.hasPrefix("/fork ") {
            let messageIndex = currentSessionDetail?.state.messages.count ?? 0
            var newPrompt: String? = nil
            if trimmed.hasPrefix("/fork ") {
                newPrompt = String(trimmed.dropFirst(6)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
            
            isLoading = true
            defer { isLoading = false }
            do {
                let newSession = try await AriadneNetworkService.shared.forkSession(sessionId: sessionId, messageIndex: messageIndex, newContent: nil)
                self.sessions = try await AriadneNetworkService.shared.fetchSessions()
                await selectSession(newSession.sessionId)
                
                if let prompt = newPrompt, !prompt.isEmpty {
                    self.inputText = prompt
                    Task {
                        await sendMessage()
                    }
                }
            } catch {
                self.errorMessage = "Failed to fork session: \(error.localizedDescription)"
            }
            return
        }
        
        // Setup local temporary streaming state
        self.isStreaming = true
        self.streamingThinking = ""
        self.streamingReply = ""
        self.streamingEvents = []
        self.activeRunId = nil
        
        // Append user message locally for immediate UI response
        if var detail = currentSessionDetail {
            let userMsg = ChatMessage(role: "user", content: textToSend)
            let updatedMessages = detail.state.messages + [userMsg]
            detail = SessionDetail(
                sessionId: detail.sessionId,
                sessionName: detail.sessionName,
                createdAt: detail.createdAt,
                updatedAt: detail.updatedAt,
                lastAgentName: detail.lastAgentName,
                messageCount: detail.messageCount + 1,
                lastReplyPreview: textToSend,
                permissionProfile: detail.permissionProfile,
                contextTokens: detail.contextTokens,
                workspacePath: detail.workspacePath,
                workspaceName: detail.workspaceName,
                sessionType: detail.sessionType,
                state: RunState(messages: updatedMessages, step: detail.state.step + 1, agentName: detail.state.agentName),
                modelId: detail.modelId,
                modelProviderId: detail.modelProviderId,
                thinkingEnabled: detail.thinkingEnabled,
                thinkingEffort: detail.thinkingEffort,
                workspaceExists: detail.workspaceExists
            )
            self.currentSessionDetail = detail
        }
        
        let input = RunInput(
            sessionId: sessionId,
            userInput: textToSend,
            agentName: selectedAgentName,
            workspacePath: currentSessionDetail?.workspacePath
        )
        
        do {
            try await AriadneNetworkService.shared.streamRun(input: input) { [weak self] frame in
                guard let self else { return }
                switch frame.type {
                case "start":
                    if let rid = frame.data["run_id"]?.value as? String {
                        self.activeRunId = rid
                    }
                case "thinking_delta":
                    if let content = frame.data["content"]?.value as? String {
                        self.streamingThinking += content
                    }
                case "delta":
                    if let content = frame.data["content"]?.value as? String {
                        self.streamingReply += content
                    }
                case "run_event":
                    do {
                        let jsonObject = frame.data
                        let data = try JSONSerialization.data(withJSONObject: jsonObject)
                        // Wait, data contains key "data" inside StreamFrame, let's decode from data directly
                        // Let's print or decode
                        // Since AnyCodable wraps dictionaries, we can decode the RunEvent from the JSON serialization of frame.data
                        let event = try JSONDecoder().decode(RunEvent.self, from: data)
                        // Add or replace event by index
                        if let index = self.streamingEvents.firstIndex(where: { $0.index == event.index }) {
                            self.streamingEvents[index] = event
                        } else {
                            self.streamingEvents.append(event)
                            self.streamingEvents.sort { $0.index < $1.index }
                        }
                    } catch {
                        print("Error decoding RunEvent from stream frame data: \(error)")
                    }
                case "paused":
                    print("Run paused for approval")
                case "end":
                    print("Stream run ended")
                case "error":
                    if let message = frame.data["message"]?.value as? String {
                        self.errorMessage = "Agent error: \(message)"
                    }
                default:
                    break
                }
            }
        } catch {
            self.errorMessage = "Stream disconnected: \(error.localizedDescription)"
        }
        
        // Clean up stream states and sync full session detail from server
        self.isStreaming = false
        self.streamingThinking = ""
        self.streamingReply = ""
        self.streamingEvents = []
        self.activeRunId = nil
        
        await selectSession(sessionId)
    }
    
    public func resolveApproval(approvalId: String, action: String) async {
        guard let sessionId = currentSessionId else { return }
        
        self.isStreaming = true
        self.streamingThinking = ""
        self.streamingReply = ""
        self.streamingEvents = []
        
        do {
            try await AriadneNetworkService.shared.streamApproval(approvalId: approvalId, action: action) { [weak self] frame in
                guard let self else { return }
                switch frame.type {
                case "thinking_delta":
                    if let content = frame.data["content"]?.value as? String {
                        self.streamingThinking += content
                    }
                case "delta":
                    if let content = frame.data["content"]?.value as? String {
                        self.streamingReply += content
                    }
                case "run_event":
                    do {
                        let jsonObject = frame.data
                        let data = try JSONSerialization.data(withJSONObject: jsonObject)
                        let event = try JSONDecoder().decode(RunEvent.self, from: data)
                        if let index = self.streamingEvents.firstIndex(where: { $0.index == event.index }) {
                            self.streamingEvents[index] = event
                        } else {
                            self.streamingEvents.append(event)
                            self.streamingEvents.sort { $0.index < $1.index }
                        }
                    } catch {
                        print("Error decoding RunEvent from stream frame data: \(error)")
                    }
                case "paused":
                    print("Run paused for approval")
                case "end":
                    print("Stream run ended")
                case "error":
                    if let message = frame.data["message"]?.value as? String {
                        self.errorMessage = "Agent error: \(message)"
                    }
                default:
                    break
                }
            }
        } catch {
            self.errorMessage = "Approval stream failed: \(error.localizedDescription)"
        }
        
        self.isStreaming = false
        self.streamingThinking = ""
        self.streamingReply = ""
        self.streamingEvents = []
        self.activeRunId = nil
        
        await selectSession(sessionId)
    }
    
    // MARK: - Workspace Dialog
    
    public func selectWorkspaceFromDialog() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let workspace = try await AriadneNetworkService.shared.selectWorkspaceDialog()
            self.workspaces = try await AriadneNetworkService.shared.fetchWorkspaces()
            await createNewSession(workspacePath: workspace.path, workspaceName: workspace.name)
        } catch {
            if case let NetworkError.badStatusCode(_, responseString) = error,
               responseString.contains("dialog_cancelled") {
                return // Silence user cancellation
            }
            self.errorMessage = "Failed to select workspace: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Compaction
    
    public func compactCurrentSession() async {
        guard let sessionId = currentSessionId else { return }
        isCompacting = true
        defer { isCompacting = false }
        do {
            let res = try await AriadneNetworkService.shared.compactSession(sessionId: sessionId)
            if res.ok {
                await selectSession(sessionId)
            }
        } catch {
            self.errorMessage = "Failed to compact: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Editing, Truncation & Forking
    
    public func forkCurrentSession(messageIndex: Int, newContent: String?) async {
        guard let sessionId = currentSessionId else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let newSession = try await AriadneNetworkService.shared.forkSession(sessionId: sessionId, messageIndex: messageIndex, newContent: newContent)
            self.sessions = try await AriadneNetworkService.shared.fetchSessions()
            await selectSession(newSession.sessionId)
        } catch {
            self.errorMessage = "Failed to fork session: \(error.localizedDescription)"
        }
    }
    
    public func truncateCurrentSession(messageIndex: Int) async {
        guard let sessionId = currentSessionId else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let success = try await AriadneNetworkService.shared.truncateSession(sessionId: sessionId, messageIndex: messageIndex)
            if success {
                await selectSession(sessionId)
            }
        } catch {
            self.errorMessage = "Failed to truncate session: \(error.localizedDescription)"
        }
    }
    
    public func editAndResendMessage(at messageIndex: Int, newContent: String) async {
        guard let sessionId = currentSessionId else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let success = try await AriadneNetworkService.shared.truncateSession(sessionId: sessionId, messageIndex: messageIndex)
            if success {
                self.inputText = newContent
                await sendMessage()
            }
        } catch {
            self.errorMessage = "Failed to edit and resend message: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Skills (Plugins)
    
    public func toggleSkill(_ skill: SkillSummary) async {
        do {
            let updated: SkillSummary
            if skill.enabled {
                updated = try await AriadneNetworkService.shared.disableSkill(skillName: skill.name)
            } else {
                updated = try await AriadneNetworkService.shared.enableSkill(skillName: skill.name)
            }
            if let index = skills.firstIndex(where: { $0.name == skill.name }) {
                skills[index] = updated
            }
        } catch {
            self.errorMessage = "Failed to toggle skill: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Providers CRUD
    
    public func addProvider(name: String, baseUrl: String, apiKey: String) async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await AriadneNetworkService.shared.createProvider(name: name, baseUrl: baseUrl, apiKey: apiKey)
            self.providers = try await AriadneNetworkService.shared.fetchProviders()
        } catch {
            self.errorMessage = "Failed to add provider: \(error.localizedDescription)"
        }
    }
    
    public func removeProvider(providerId: Int) async {
        isLoading = true
        defer { isLoading = false }
        do {
            let success = try await AriadneNetworkService.shared.deleteProvider(providerId: providerId)
            if success {
                self.providers = try await AriadneNetworkService.shared.fetchProviders()
                self.models = try await AriadneNetworkService.shared.fetchModels()
            }
        } catch {
            self.errorMessage = "Failed to delete provider: \(error.localizedDescription)"
        }
    }
    
    public func updateProvider(providerId: Int, name: String?, baseUrl: String?, apiKey: String?, isDefault: Bool?) async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await AriadneNetworkService.shared.patchProvider(providerId: providerId, name: name, baseUrl: baseUrl, apiKey: apiKey, isDefault: isDefault)
            self.providers = try await AriadneNetworkService.shared.fetchProviders()
        } catch {
            self.errorMessage = "Failed to update provider: \(error.localizedDescription)"
        }
    }
    
    public func syncProviderModels(providerId: Int) async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await AriadneNetworkService.shared.syncProviderModels(providerId: providerId)
            self.models = try await AriadneNetworkService.shared.fetchModels()
        } catch {
            self.errorMessage = "Failed to sync provider models: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Models Toggle & Edit
    
    public func toggleModel(_ model: ModelOut) async {
        do {
            _ = try await AriadneNetworkService.shared.patchModel(modelId: model.id, enabled: !model.enabled, displayName: model.displayName)
            self.models = try await AriadneNetworkService.shared.fetchModels()
        } catch {
            self.errorMessage = "Failed to toggle model: \(error.localizedDescription)"
        }
    }
    
    public func renameModel(_ model: ModelOut, newDisplayName: String) async {
        do {
            _ = try await AriadneNetworkService.shared.patchModel(modelId: model.id, enabled: model.enabled, displayName: newDisplayName)
            self.models = try await AriadneNetworkService.shared.fetchModels()
        } catch {
            self.errorMessage = "Failed to rename model: \(error.localizedDescription)"
        }
    }
    
    // MARK: - MCP Servers CRUD & reload
    
    public func addMcpServer(server: McpServerOut) async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await AriadneNetworkService.shared.createMcpServer(server: server)
            self.mcpServers = try await AriadneNetworkService.shared.listMcpServers()
        } catch {
            self.errorMessage = "Failed to add MCP server: \(error.localizedDescription)"
        }
    }
    
    public func updateMcpServer(serverId: String, server: McpServerOut) async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await AriadneNetworkService.shared.patchMcpServer(serverId: serverId, server: server)
            self.mcpServers = try await AriadneNetworkService.shared.listMcpServers()
        } catch {
            self.errorMessage = "Failed to update MCP server: \(error.localizedDescription)"
        }
    }
    
    public func removeMcpServer(serverId: String) async {
        isLoading = true
        defer { isLoading = false }
        do {
            let success = try await AriadneNetworkService.shared.deleteMcpServer(serverId: serverId)
            if success {
                self.mcpServers = try await AriadneNetworkService.shared.listMcpServers()
            }
        } catch {
            self.errorMessage = "Failed to delete MCP server: \(error.localizedDescription)"
        }
    }
    
    public func reloadMcpRuntime() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let res = try await AriadneNetworkService.shared.reloadMcpRuntime()
            self.mcpServers = try await AriadneNetworkService.shared.listMcpServers()
            if !res.ok {
                let errs = res.errors.map { "\($0.serverId): \($0.message)" }.joined(separator: "\n")
                self.errorMessage = "MCP reload errors:\n\(errs)"
            }
        } catch {
            self.errorMessage = "Failed to reload MCP runtime: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Custom Agent templates CRUD
    
    public func saveAgent(definition: AgentDefinition) async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await AriadneNetworkService.shared.saveAgent(definition: definition)
            self.agents = try await AriadneNetworkService.shared.fetchAgents()
        } catch {
            self.errorMessage = "Failed to save agent template: \(error.localizedDescription)"
        }
    }
    
    public func removeAgent(agentId: String) async {
        isLoading = true
        defer { isLoading = false }
        do {
            let success = try await AriadneNetworkService.shared.deleteAgent(agentId: agentId)
            if success {
                self.agents = try await AriadneNetworkService.shared.fetchAgents()
            }
        } catch {
            self.errorMessage = "Failed to delete agent template: \(error.localizedDescription)"
        }
    }
}

