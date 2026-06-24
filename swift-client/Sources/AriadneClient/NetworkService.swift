import Foundation
import Combine

public enum NetworkError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case badStatusCode(Int, String)
    case decodingError(Error)
    
    public var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid server URL."
        case .invalidResponse: return "Invalid response from the server."
        case .badStatusCode(let code, let msg): return "HTTP \(code): \(msg)"
        case .decodingError(let err): return "Failed to decode payload: \(err.localizedDescription)"
        }
    }
}

public class AriadneNetworkService: ObservableObject {
    public static let shared = AriadneNetworkService()
    
    @Published public var serverURLString: String = "http://127.0.0.1:8000"
    
    private var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        let formatterWithFractional = DateFormatter()
        formatterWithFractional.locale = Locale(identifier: "en_US_POSIX")
        formatterWithFractional.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        
        let formatterWithoutFractional = DateFormatter()
        formatterWithoutFractional.locale = Locale(identifier: "en_US_POSIX")
        formatterWithoutFractional.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        
        let iso8601Formatter = ISO8601DateFormatter()
        iso8601Formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        let iso8601FormatterNoFrac = ISO8601DateFormatter()
        iso8601FormatterNoFrac.formatOptions = [.withInternetDateTime]

        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateStr = try container.decode(String.self)
            
            if let date = formatterWithFractional.date(from: dateStr) { return date }
            if let date = formatterWithoutFractional.date(from: dateStr) { return date }
            if let date = iso8601Formatter.date(from: dateStr) { return date }
            if let date = iso8601FormatterNoFrac.date(from: dateStr) { return date }
            
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date: \(dateStr)")
        }
        return decoder
    }
    
    private init() {}
    
    private func getBaseURL() throws -> URL {
        guard let url = URL(string: serverURLString) else {
            throw NetworkError.invalidURL
        }
        return url
    }
    
    // MARK: - REST API Requests
    
    private func request<T: Decodable>(_ path: String, method: String = "GET", body: Data? = nil) async throws -> T {
        let baseURL = try getBaseURL()
        let url = baseURL.appendingPathComponent(path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        
        if !(200...299).contains(httpResponse.statusCode) {
            let errorMsg = String(data: data, encoding: .utf8) ?? "Unknown server error"
            throw NetworkError.badStatusCode(httpResponse.statusCode, errorMsg)
        }
        
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            print("Decoding failed for \(path): \(error)")
            throw NetworkError.decodingError(error)
        }
    }
    
    // MARK: - API Calls
    
    public func fetchSessions() async throws -> [SessionSummary] {
        return try await request("sessions")
    }
    
    public func createSession(
        workspacePath: String? = nil,
        workspaceName: String? = nil,
        sessionName: String? = nil,
        sessionType: String = "coding"
    ) async throws -> SessionSummary {
        var payload: [String: Any] = [:]
        if let workspacePath { payload["workspace_path"] = workspacePath }
        if let workspaceName { payload["workspace_name"] = workspaceName }
        if let sessionName { payload["session_name"] = sessionName }
        payload["session_type"] = sessionType
        
        let data = try JSONSerialization.data(withJSONObject: payload)
        return try await request("sessions", method: "POST", body: data)
    }
    
    public func getSessionDetail(sessionId: String) async throws -> SessionDetail {
        return try await request("sessions/\(sessionId)")
    }
    
    public func deleteSession(sessionId: String) async throws -> Bool {
        let res: [String: Bool] = try await request("sessions/\(sessionId)", method: "DELETE")
        return res["status"] ?? res["ok"] ?? false
    }
    
    public func renameSession(sessionId: String, sessionName: String) async throws -> Bool {
        let payload = ["session_name": sessionName]
        let data = try JSONSerialization.data(withJSONObject: payload)
        let res: [String: Bool] = try await request("sessions/\(sessionId)", method: "PATCH", body: data)
        return res["status"] ?? res["ok"] ?? false
    }
    
    public func patchSession(
        sessionId: String,
        modelId: String?,
        modelProviderId: Int?,
        thinkingEnabled: Bool,
        thinkingEffort: String
    ) async throws -> Bool {
        var payload: [String: Any] = [
            "thinking_enabled": thinkingEnabled,
            "thinking_effort": thinkingEffort
        ]
        if let modelId { payload["model_id"] = modelId } else { payload["model_id"] = NSNull() }
        if let modelProviderId { payload["model_provider_id"] = modelProviderId } else { payload["model_provider_id"] = NSNull() }
        
        let data = try JSONSerialization.data(withJSONObject: payload)
        let res: [String: Bool] = try await request("sessions/\(sessionId)", method: "PATCH", body: data)
        return res["status"] ?? res["ok"] ?? false
    }
    
    public func fetchModels() async throws -> [ModelOut] {
        return try await request("settings/models")
    }
    
    public func fetchProviders() async throws -> [ProviderOut] {
        return try await request("settings/providers")
    }
    
    public func fetchAgents() async throws -> [AgentDefinition] {
        return try await request("agents")
    }
    
    public func fetchWorkspaces() async throws -> [WorkspaceSummary] {
        return try await request("workspaces")
    }
    
    public func selectWorkspaceDialog() async throws -> WorkspaceSummary {
        return try await request("workspaces/select-dialog", method: "POST")
    }
    
    public func compactSession(sessionId: String) async throws -> CompactOutput {
        let input = CompactInput(sessionId: sessionId)
        let data = try JSONEncoder().encode(input)
        return try await request("compact", method: "POST", body: data)
    }
    
    public func truncateSession(sessionId: String, messageIndex: Int) async throws -> Bool {
        let payload = ["message_index": messageIndex]
        let data = try JSONSerialization.data(withJSONObject: payload)
        let res: [String: Bool] = try await request("sessions/\(sessionId)/truncate", method: "POST", body: data)
        return res["status"] ?? res["ok"] ?? false
    }
    
    public func forkSession(sessionId: String, messageIndex: Int, newContent: String?) async throws -> SessionSummary {
        var payload: [String: Any] = ["message_index": messageIndex]
        if let newContent {
            payload["new_content"] = newContent
        }
        let data = try JSONSerialization.data(withJSONObject: payload)
        return try await request("sessions/\(sessionId)/fork", method: "POST", body: data)
    }
    
    public func fetchSkills() async throws -> [SkillSummary] {
        return try await request("skills")
    }
    
    public func disableSkill(skillName: String) async throws -> SkillSummary {
        return try await request("skills/\(skillName)/disable", method: "POST")
    }
    
    public func enableSkill(skillName: String) async throws -> SkillSummary {
        return try await request("skills/\(skillName)/enable", method: "POST")
    }
    
    public func saveAgent(definition: AgentDefinition) async throws -> AgentDefinition {
        let data = try JSONEncoder().encode(definition)
        return try await request("agents", method: "POST", body: data)
    }
    
    public func deleteAgent(agentId: String) async throws -> Bool {
        let res: [String: String] = try await request("agents/\(agentId)", method: "DELETE")
        return res["status"] == "ok"
    }
    
    public func listMcpServers() async throws -> [McpServerOut] {
        return try await request("settings/mcp/servers")
    }
    
    public func createMcpServer(server: McpServerOut) async throws -> McpServerOut {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(server)
        return try await request("settings/mcp/servers", method: "POST", body: data)
    }
    
    public func patchMcpServer(serverId: String, server: McpServerOut) async throws -> McpServerOut {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(server)
        return try await request("settings/mcp/servers/\(serverId)", method: "PATCH", body: data)
    }
    
    public func deleteMcpServer(serverId: String) async throws -> Bool {
        let baseURL = try getBaseURL()
        let url = baseURL.appendingPathComponent("settings/mcp/servers/\(serverId)")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        return (200...299).contains(httpResponse.statusCode)
    }
    
    public func reloadMcpRuntime() async throws -> McpReloadOut {
        return try await request("settings/mcp/reload", method: "POST")
    }
    
    public func createProvider(name: String, baseUrl: String, apiKey: String) async throws -> ProviderOut {
        let payload = [
            "name": name,
            "base_url": baseUrl,
            "api_key": apiKey
        ]
        let data = try JSONSerialization.data(withJSONObject: payload)
        return try await request("settings/providers", method: "POST", body: data)
    }
    
    public func deleteProvider(providerId: Int) async throws -> Bool {
        let baseURL = try getBaseURL()
        let url = baseURL.appendingPathComponent("settings/providers/\(providerId)")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        let (_, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        return (200...299).contains(httpResponse.statusCode)
    }
    
    public func patchProvider(
        providerId: Int,
        name: String?,
        baseUrl: String?,
        apiKey: String?,
        isDefault: Bool?
    ) async throws -> ProviderOut {
        var payload: [String: Any] = [:]
        if let name { payload["name"] = name }
        if let baseUrl { payload["base_url"] = baseUrl }
        if let apiKey { payload["api_key"] = apiKey }
        if let isDefault { payload["is_default"] = isDefault }
        
        let data = try JSONSerialization.data(withJSONObject: payload)
        return try await request("settings/providers/\(providerId)", method: "PATCH", body: data)
    }
    
    public func syncProviderModels(providerId: Int) async throws -> [ModelOut] {
        return try await request("settings/providers/\(providerId)/models")
    }
    
    public func patchModel(modelId: Int, enabled: Bool, displayName: String?) async throws -> ModelOut {
        var payload: [String: Any] = ["enabled": enabled]
        if let displayName {
            payload["display_name"] = displayName
        }
        let data = try JSONSerialization.data(withJSONObject: payload)
        return try await request("settings/models/\(modelId)", method: "PATCH", body: data)
    }
    
    public func fetchTools() async throws -> [String] {
        let res: [[String: String]] = try await request("tools")
        return res.compactMap { $0["name"] }
    }
    
    // MARK: - Server-Sent Events (SSE) Stream
    
    public func streamRun(
        input: RunInput,
        onFrame: @escaping (StreamFrame) -> Void
    ) async throws {
        let baseURL = try getBaseURL()
        let url = baseURL.appendingPathComponent("run/stream")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        request.httpBody = try encoder.encode(input)
        
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        
        if !(200...299).contains(httpResponse.statusCode) {
            throw NetworkError.badStatusCode(httpResponse.statusCode, "Streaming request failed")
        }
        
        for try await line in bytes.lines {
            guard line.hasPrefix("data: ") else { continue }
            let jsonString = String(line.dropFirst(6)).trimmingCharacters(in: .whitespacesAndNewlines)
            if jsonString == "[DONE]" { break }
            guard let data = jsonString.data(using: .utf8) else { continue }
            
            do {
                let frame = try decoder.decode(StreamFrame.self, from: data)
                // UI updates must happen on the main queue
                await MainActor.run {
                    onFrame(frame)
                }
            } catch {
                print("SSE stream decode error: \(error) for line: \(jsonString)")
            }
        }
    }
    
    public func streamApproval(
        approvalId: String,
        action: String,
        onFrame: @escaping (StreamFrame) -> Void
    ) async throws {
        let baseURL = try getBaseURL()
        let url = baseURL.appendingPathComponent("approvals/\(approvalId)/\(action)")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        
        if !(200...299).contains(httpResponse.statusCode) {
            throw NetworkError.badStatusCode(httpResponse.statusCode, "Streaming approval failed")
        }
        
        for try await line in bytes.lines {
            guard line.hasPrefix("data: ") else { continue }
            let jsonString = String(line.dropFirst(6)).trimmingCharacters(in: .whitespacesAndNewlines)
            if jsonString == "[DONE]" { break }
            guard let data = jsonString.data(using: .utf8) else { continue }
            
            do {
                let frame = try decoder.decode(StreamFrame.self, from: data)
                await MainActor.run {
                    onFrame(frame)
                }
            } catch {
                print("SSE approval stream decode error: \(error) for line: \(jsonString)")
            }
        }
    }
}

