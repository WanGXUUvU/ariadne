import Foundation

// MARK: - Core Entities

public struct ToolCallFunction: Codable, Equatable {
    public let name: String
    public let arguments: String
    
    public init(name: String, arguments: String) {
        self.name = name
        self.arguments = arguments
    }
}

public struct ToolCall: Codable, Equatable, Identifiable {
    public let id: String
    public let type: String
    public let function: ToolCallFunction
    
    public init(id: String, type: String = "function", function: ToolCallFunction) {
        self.id = id
        self.type = type
        self.function = function
    }
}

public struct ChatMessage: Codable, Identifiable, Equatable {
    public var id: String {
        if let toolCallId {
            return "tool-\(toolCallId)"
        }
        if let firstToolCall = toolCalls?.first {
            return "assistant-tool-\(firstToolCall.id)"
        }
        if let content {
            return "\(role)-\(content.hashValue)"
        }
        return "\(role)-empty"
    }
    
    public let role: String // "system" | "user" | "assistant" | "tool"
    public let content: String?
    public let toolCalls: [ToolCall]?
    public let toolCallId: String?
    
    enum CodingKeys: String, CodingKey {
        case role
        case content
        case toolCalls = "tool_calls"
        case toolCallId = "tool_call_id"
    }
    
    public init(role: String, content: String? = nil, toolCalls: [ToolCall]? = nil, toolCallId: String? = nil) {
        self.role = role
        self.content = content
        self.toolCalls = toolCalls
        self.toolCallId = toolCallId
    }
}

public struct RunState: Codable, Equatable {
    public let messages: [ChatMessage]
    public let step: Int
    public let agentName: String?
    
    enum CodingKeys: String, CodingKey {
        case messages
        case step
        case agentName = "agent_name"
    }
}

// MARK: - Sessions

public struct SessionSummary: Codable, Identifiable, Equatable {
    public var id: String { sessionId }
    
    public let sessionId: String
    public let sessionName: String?
    public let createdAt: Date
    public let updatedAt: Date
    public let lastAgentName: String?
    public let messageCount: Int
    public let lastReplyPreview: String?
    public let permissionProfile: String
    public let contextTokens: Int?
    public let workspacePath: String?
    public let workspaceName: String?
    public let sessionType: String?
    public let parentSessionId: String?
    public let forkMessageIndex: Int?
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case sessionName = "session_name"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastAgentName = "last_agent_name"
        case messageCount = "message_count"
        case lastReplyPreview = "last_reply_preview"
        case permissionProfile = "permission_profile"
        case contextTokens = "context_tokens"
        case workspacePath = "workspace_path"
        case workspaceName = "workspace_name"
        case sessionType = "session_type"
        case parentSessionId = "parent_session_id"
        case forkMessageIndex = "fork_message_index"
    }
}

public struct SessionDetail: Codable, Equatable {
    public let sessionId: String
    public let sessionName: String?
    public let createdAt: Date
    public let updatedAt: Date
    public let lastAgentName: String?
    public let messageCount: Int
    public let lastReplyPreview: String?
    public let permissionProfile: String
    public let contextTokens: Int?
    public let workspacePath: String?
    public let workspaceName: String?
    public let sessionType: String?
    public let state: RunState
    public let modelId: String?
    public let modelProviderId: Int?
    public let thinkingEnabled: Bool
    public let thinkingEffort: String
    public let workspaceExists: Bool
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case sessionName = "session_name"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case lastAgentName = "last_agent_name"
        case messageCount = "message_count"
        case lastReplyPreview = "last_reply_preview"
        case permissionProfile = "permission_profile"
        case contextTokens = "context_tokens"
        case workspacePath = "workspace_path"
        case workspaceName = "workspace_name"
        case sessionType = "session_type"
        case state
        case modelId = "model_id"
        case modelProviderId = "model_provider_id"
        case thinkingEnabled = "thinking_enabled"
        case thinkingEffort = "thinking_effort"
        case workspaceExists = "workspace_exists"
    }
}

// MARK: - Run & SSE Stream

public struct RunInput: Codable {
    public let sessionId: String
    public let userInput: String
    public let agentName: String?
    public let skillName: String?
    public let workspacePath: String?
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case userInput = "user_input"
        case agentName = "agent_name"
        case skillName = "skill_name"
        case workspacePath = "workspace_path"
    }
    
    public init(sessionId: String, userInput: String, agentName: String? = nil, skillName: String? = nil, workspacePath: String? = nil) {
        self.sessionId = sessionId
        self.userInput = userInput
        self.agentName = agentName
        self.skillName = skillName
        self.workspacePath = workspacePath
    }
}

public struct ToolError: Codable, Equatable {
    public let ok: Bool
    public let code: String
    public let toolName: String
    public let message: String
    
    enum CodingKeys: String, CodingKey {
        case ok, code
        case toolName = "tool_name"
        case message
    }
}

public struct ToolResult: Codable, Equatable {
    public let ok: Bool
    public let content: String?
    public let error: ToolError?
    
    public init(ok: Bool, content: String? = nil, error: ToolError? = nil) {
        self.ok = ok
        self.content = content
        self.error = error
    }
}

public struct RunEvent: Codable, Identifiable, Equatable {
    public var id: Int { index }
    
    public let index: Int
    public let type: String // "assistant_text" | "assistant_tool_call" | "tool_result" | "tool_error" | "final_answer" | "approval_required" | "thinking"
    public let content: String?
    public let toolName: String?
    public let toolCallId: String?
    public let toolResult: ToolResult?
    
    enum CodingKeys: String, CodingKey {
        case index, type, content
        case toolName = "tool_name"
        case toolCallId = "tool_call_id"
        case toolResult = "tool_result"
    }
}

public struct ModelUsage: Codable, Equatable {
    public let inputTokens: Int?
    public let outputTokens: Int?
    public let totalTokens: Int?
    
    enum CodingKeys: String, CodingKey {
        case inputTokens = "input_tokens"
        case outputTokens = "output_tokens"
        case totalTokens = "total_tokens"
    }
}

public struct UsageFrame: Codable, Identifiable, Equatable {
    public var id: Int { modelCallIndex }
    
    public let modelCallIndex: Int
    public let usage: ModelUsage
    
    enum CodingKeys: String, CodingKey {
        case modelCallIndex = "model_call_index"
        case usage
    }
}

public struct StreamFrame: Codable {
    public let type: String // "start" | "run_event" | "delta" | "end" | "error" | "paused" | "resume" | "thinking_delta" | "usage"
    public let data: [String: AnyCodable]
}

// MARK: - Settings & Mcp Servers

public struct ProviderOut: Codable, Identifiable, Equatable {
    public let id: Int
    public let name: String
    public let baseUrl: String
    public let apiKeyHint: String?
    public let isDefault: Bool
    public let createdAt: Date?
    
    enum CodingKeys: String, CodingKey {
        case id
        case name
        case baseUrl = "base_url"
        case apiKeyHint = "api_key_hint"
        case isDefault = "is_default"
        case createdAt = "created_at"
    }
}

public struct ModelOut: Codable, Identifiable, Equatable {
    public let id: Int
    public let providerId: Int
    public let modelId: String
    public let displayName: String?
    public let enabled: Bool
    public let supportsThinking: Bool
    public let thinkingStyle: String
    public let effortLevels: [String]
    public let contextLength: Int?
    public let supportsTools: Bool
    
    enum CodingKeys: String, CodingKey {
        case id
        case providerId = "provider_id"
        case modelId = "model_id"
        case displayName = "display_name"
        case enabled
        case supportsThinking = "supports_thinking"
        case thinkingStyle = "thinking_style"
        case effortLevels = "effort_levels"
        case contextLength = "context_length"
        case supportsTools = "supports_tools"
    }
}

public struct SkillSummary: Codable, Identifiable, Equatable {
    public var id: String { name }
    public let name: String
    public let description: String?
    public let path: String
    public let enabled: Bool
    public let error: String?
    
    public init(name: String, description: String? = nil, path: String, enabled: Bool = true, error: String? = nil) {
        self.name = name
        self.description = description
        self.path = path
        self.enabled = enabled
        self.error = error
    }
}

public struct McpServerOut: Codable, Identifiable, Equatable {
    public var id: String { serverId }
    public let serverId: String
    public let displayName: String?
    public let transport: String // "stdio" | "streamable_http"
    public let enabled: Bool
    public let required: Bool
    public let startupTimeoutSec: Int
    public let toolTimeoutSec: Int
    public let command: String?
    public let args: [String]
    public let env: [String: String]
    public let cwd: String?
    public let url: String?
    public let bearerToken: String?
    public let httpHeaders: [String: String]
    public let runtimeStatus: String
    public let toolCount: Int
    public let lastError: String?
    
    enum CodingKeys: String, CodingKey {
        case serverId = "server_id"
        case displayName = "display_name"
        case transport, enabled, required
        case startupTimeoutSec = "startup_timeout_sec"
        case toolTimeoutSec = "tool_timeout_sec"
        case command, args, env, cwd, url
        case bearerToken = "bearer_token"
        case httpHeaders = "http_headers"
        case runtimeStatus = "runtime_status"
        case toolCount = "tool_count"
        case lastError = "last_error"
    }
}

public struct McpReloadError: Codable, Equatable {
    public let serverId: String
    public let message: String
    
    enum CodingKeys: String, CodingKey {
        case serverId = "server_id"
        case message
    }
}

public struct McpReloadOut: Codable, Equatable {
    public let ok: Bool
    public let connectedServers: Int
    public let failedServers: Int
    public let errors: [McpReloadError]
    
    enum CodingKeys: String, CodingKey {
        case ok
        case connectedServers = "connected_servers"
        case failedServers = "failed_servers"
        case errors
    }
}

public struct CompactInput: Codable {
    public let sessionId: String
    
    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
    }
    
    public init(sessionId: String) {
        self.sessionId = sessionId
    }
}

public struct CompactOutput: Codable, Equatable {
    public let ok: Bool
    public let summary: String?
    public let removedCount: Int
    
    enum CodingKeys: String, CodingKey {
        case ok, summary
        case removedCount = "removed_count"
    }
}

public struct AgentDefinition: Codable, Identifiable, Equatable {
    public let id: String
    public let name: String
    public let systemPrompt: String?
    public let description: String?
    public let toolNames: [String]?
    public let isBuiltin: Bool
    
    enum CodingKeys: String, CodingKey {
        case id, name, description
        case systemPrompt = "system_prompt"
        case toolNames = "tool_names"
        case isBuiltin = "is_builtin"
    }
    
    public init(id: String = UUID().uuidString, name: String, systemPrompt: String? = nil, description: String? = nil, toolNames: [String]? = nil, isBuiltin: Bool = false) {
        self.id = id
        self.name = name
        self.systemPrompt = systemPrompt
        self.description = description
        self.toolNames = toolNames
        self.isBuiltin = isBuiltin
    }
}

public struct WorkspaceSummary: Codable, Identifiable, Equatable {
    public let id: Int
    public let name: String
    public let path: String
    public let createdAt: Date
    
    enum CodingKeys: String, CodingKey {
        case id, name, path
        case createdAt = "created_at"
    }
}

// MARK: - AnyCodable Utility for JSON dictionaries

public struct AnyCodable: Codable, Equatable {
    public let value: Any
    
    public init(_ value: Any) {
        self.value = value
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let boolVal = try? container.decode(Bool.self) {
            value = boolVal
        } else if let intVal = try? container.decode(Int.self) {
            value = intVal
        } else if let doubleVal = try? container.decode(Double.self) {
            value = doubleVal
        } else if let stringVal = try? container.decode(String.self) {
            value = stringVal
        } else if let arrayVal = try? container.decode([AnyCodable].self) {
            value = arrayVal.map { $0.value }
        } else if let dictVal = try? container.decode([String: AnyCodable].self) {
            value = dictVal.mapValues { $0.value }
        } else if container.decodeNil() {
            value = NSNull()
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unable to decode value as AnyCodable")
        }
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case is NSNull:
            try container.encodeNil()
        case let boolVal as Bool:
            try container.encode(boolVal)
        case let intVal as Int:
            try container.encode(intVal)
        case let doubleVal as Double:
            try container.encode(doubleVal)
        case let stringVal as String:
            try container.encode(stringVal)
        case let arrayVal as [Any]:
            try container.encode(arrayVal.map { AnyCodable($0) })
        case let dictVal as [String: Any]:
            try container.encode(dictVal.mapValues { AnyCodable($0) })
        default:
            throw EncodingError.invalidValue(value, EncodingError.Context(codingPath: container.codingPath, debugDescription: "Cannot encode AnyCodable value"))
        }
    }
    
    public static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        switch (lhs.value, rhs.value) {
        case (let l as Bool, let r as Bool): return l == r
        case (let l as Int, let r as Int): return l == r
        case (let l as Double, let r as Double): return l == r
        case (let l as String, let r as String): return l == r
        case (let l as [AnyCodable], let r as [AnyCodable]): return l == r
        case (let l as [String: AnyCodable], let r as [String: AnyCodable]): return l == r
        case (is NSNull, is NSNull): return true
        default: return false
        }
    }
}
