import AppKit
import SwiftUI

struct ChatView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var pulseOpacity = 0.45

    var body: some View {
        VStack(spacing: 0) {
            headerBar
            transcript
            ChatComposerView()
        }
        .background(AriadneDesign.ColorToken.canvas)
    }

    private var headerBar: some View {
        HStack(alignment: .center, spacing: AriadneDesign.Space.md) {
            VStack(alignment: .leading, spacing: 3) {
                Text(viewModel.currentSessionDetail?.sessionName ?? "Session")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(1)

                HStack(spacing: AriadneDesign.Space.sm) {
                    if let workspace = viewModel.currentSessionDetail?.workspacePath {
                        Text(workspace)
                            .lineLimit(1)
                    } else {
                        Text("No workspace")
                    }
                    Text("·")
                    Text(viewModel.selectedAgentName)
                    if let model = selectedModelLabel {
                        Text("·")
                        Text(model)
                    }
                }
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
            }

            Spacer()

            if viewModel.isStreaming {
                HStack(spacing: AriadneDesign.Space.sm) {
                    Circle()
                        .fill(AriadneDesign.ColorToken.warning)
                        .frame(width: 7, height: 7)
                        .opacity(pulseOpacity)
                        .onAppear {
                            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                                pulseOpacity = 1.0
                            }
                        }
                    Text("Running")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.horizontal, AriadneDesign.Space.xl)
        .padding(.vertical, AriadneDesign.Space.md)
        .background(AriadneDesign.ColorToken.surface.opacity(0.88))
        .overlay(alignment: .bottom) {
            AriadneDivider()
        }
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: AriadneDesign.Space.xl) {
                    if let detail = viewModel.currentSessionDetail {
                        ForEach(ChatTranscriptBuilder.items(from: detail.state.messages)) { item in
                            TranscriptItemView(item: item)
                        }
                    }

                    if viewModel.isStreaming {
                        StreamingMessageRow()
                            .id("streaming_anchor")
                    }
                }
                .padding(.horizontal, AriadneDesign.Space.xxl)
                .padding(.vertical, 34)
                .frame(maxWidth: AriadneDesign.readingWidth, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .top)
            }
            .onChange(of: viewModel.isStreaming) { _, isStreaming in
                if isStreaming {
                    withAnimation(.spring(response: 0.28, dampingFraction: 0.86)) {
                        proxy.scrollTo("streaming_anchor", anchor: .bottom)
                    }
                }
            }
            .onChange(of: viewModel.streamingReply) { _, _ in
                withAnimation(.easeOut(duration: 0.18)) {
                    proxy.scrollTo("streaming_anchor", anchor: .bottom)
                }
            }
            .onChange(of: viewModel.streamingThinking) { _, _ in
                withAnimation(.easeOut(duration: 0.18)) {
                    proxy.scrollTo("streaming_anchor", anchor: .bottom)
                }
            }
            .onChange(of: viewModel.streamingEvents.count) { _, _ in
                withAnimation(.spring(response: 0.28, dampingFraction: 0.86)) {
                    proxy.scrollTo("streaming_anchor", anchor: .bottom)
                }
            }
        }
    }

    private var selectedModelLabel: String? {
        guard let modelId = viewModel.selectedModelId else { return nil }
        return viewModel.models.first(where: { $0.modelId == modelId })?.displayName ?? modelId
    }
}

struct MessageRowView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let message: ChatMessage
    let index: Int

    @State private var isEditing = false
    @State private var editedContent = ""

    var body: some View {
        content
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

    private var roleRail: some View {
        VStack(spacing: AriadneDesign.Space.xs) {
            Image(systemName: roleIcon)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(roleColor)
                .frame(width: 24, height: 24)
                .background(roleColor.opacity(0.10), in: Circle())
            Text(roleLabel)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.tertiary)
                .frame(width: 62)
        }
        .frame(width: 62)
    }

    @ViewBuilder
    private var content: some View {
        switch message.role {
        case "user":
            userContent
        case "assistant":
            assistantContent
        case "tool":
            toolContent
        default:
            assistantContent
        }
    }

    private var userContent: some View {
        RunTimelineNode(label: "You", state: .completed) {
            VStack(alignment: .leading, spacing: AriadneDesign.Space.sm) {
                if isEditing {
                    ReliablePromptTextView(
                        text: $editedContent,
                        placeholder: "Edit message...",
                        minHeight: 82,
                        maxHeight: 180,
                        isFocused: .constant(true),
                        isEnabled: true,
                        submitOnReturn: false,
                        onSubmit: {}
                    )
                    .frame(minHeight: 82)
                    .modifier(ComposerTextFieldChrome(isFocused: true))

                    HStack(spacing: AriadneDesign.Space.sm) {
                        Button("Cancel") {
                            isEditing = false
                        }
                        .buttonStyle(.bordered)

                        Button("Save and resend") {
                            isEditing = false
                            Task {
                                await viewModel.editAndResendMessage(at: index, newContent: editedContent)
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                } else {
                    MarkdownMessageView(text: message.content ?? "")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(.primary)
                        .padding(.vertical, AriadneDesign.Space.xs)
                        .onTapGesture(count: 2) {
                            editedContent = message.content ?? ""
                            isEditing = true
                        }
                        .help("Double click to edit message")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var assistantContent: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
            if let content = message.content {
                if content.contains("<thinking>") && content.contains("</thinking>") {
                    let parts = parseThinking(content)
                    if !parts.thinking.isEmpty {
                        RunTimelineNode(label: "Thought", state: .completed) {
                            ThinkingDisclosure(text: parts.thinking)
                        }
                    }
                    if !parts.reply.isEmpty {
                        RunTimelineNode(label: "Ariadne", state: .completed) {
                            AssistantText(text: parts.reply)
                        }
                    }
                } else {
                    RunTimelineNode(label: "Ariadne", state: .completed) {
                        AssistantText(text: content)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var toolContent: some View {
        RunTimelineNode(label: "Tool Result", detail: message.toolCallId, state: .completed) {
            ToolExchangeContent(
                toolName: nil,
                arguments: nil,
                resultText: message.content,
                resultFallback: message.toolCallId ?? "Tool output",
                isRunning: false,
                isError: false
            )
        }
    }

    private var roleLabel: String {
        switch message.role {
        case "user": return "You"
        case "tool": return "Tool"
        default: return "Ariadne"
        }
    }

    private var roleIcon: String {
        switch message.role {
        case "user": return "person"
        case "tool": return "wrench.and.screwdriver"
        default: return "sparkle"
        }
    }

    private var roleColor: Color {
        switch message.role {
        case "user": return AriadneDesign.ColorToken.accent
        case "tool": return AriadneDesign.ColorToken.warning
        default: return .secondary
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

enum ChatTranscriptItem: Identifiable {
    case message(index: Int, message: ChatMessage)
    case toolExchange(index: Int, call: ToolCall?, result: ChatMessage?)

    var id: String {
        switch self {
        case let .message(index, message):
            return "message-\(index)-\(message.role)"
        case let .toolExchange(index, call, result):
            return "tool-\(index)-\(call?.id ?? result?.toolCallId ?? "unknown")"
        }
    }
}

enum ChatTranscriptBuilder {
    static func items(from messages: [ChatMessage]) -> [ChatTranscriptItem] {
        var output: [ChatTranscriptItem] = []
        var consumedToolIndexes = Set<Int>()
        var toolResultsById: [String: (Int, ChatMessage)] = [:]
        for (index, message) in messages.enumerated() where message.role == "tool" {
            guard let callId = message.toolCallId, toolResultsById[callId] == nil else { continue }
            toolResultsById[callId] = (index, message)
        }

        for (index, message) in messages.enumerated() {
            if consumedToolIndexes.contains(index) {
                continue
            }

            if isDuplicateTrailingUserEcho(message: message, index: index, messages: messages, output: output) {
                continue
            }

            if message.role == "assistant", let calls = message.toolCalls, !calls.isEmpty {
                if let content = message.content?.trimmingCharacters(in: .whitespacesAndNewlines), !content.isEmpty {
                    output.append(.message(index: index, message: ChatMessage(role: "assistant", content: content)))
                }
                for call in calls {
                    let resultPair = toolResultsById[call.id]
                    if let resultIndex = resultPair?.0 {
                        consumedToolIndexes.insert(resultIndex)
                    }
                    output.append(.toolExchange(index: index, call: call, result: resultPair?.1))
                }
                continue
            }

            if message.role == "tool" {
                output.append(.toolExchange(index: index, call: nil, result: message))
                continue
            }

            output.append(.message(index: index, message: message))
        }

        return output
    }

    private static func isDuplicateTrailingUserEcho(
        message: ChatMessage,
        index: Int,
        messages: [ChatMessage],
        output: [ChatTranscriptItem]
    ) -> Bool {
        guard message.role == "user",
              index == messages.indices.last,
              output.last?.isToolExchange == true,
              let content = message.content?.trimmingCharacters(in: .whitespacesAndNewlines),
              !content.isEmpty else {
            return false
        }
        return output.contains { item in
            if case let .message(_, previous) = item,
               previous.role == "user",
               previous.content?.trimmingCharacters(in: .whitespacesAndNewlines) == content {
                return true
            }
            return false
        }
    }
}

private extension ChatTranscriptItem {
    var isToolExchange: Bool {
        if case .toolExchange = self {
            return true
        }
        return false
    }
}

struct TranscriptItemView: View {
    let item: ChatTranscriptItem

    var body: some View {
        switch item {
        case let .message(index, message):
            MessageRowView(message: message, index: index)
        case let .toolExchange(index, call, result):
            ToolExchangeRowView(call: call, result: result, index: index)
        }
    }
}

struct ToolExchangeRowView: View {
    let call: ToolCall?
    let result: ChatMessage?
    let index: Int

    var body: some View {
        RunTimelineNode(
            label: state == .error ? "Tool Error" : ToolCallFormatter.displayName(call?.function.name, isRunning: false),
            detail: nil,
            state: state
        ) {
            ToolExchangeContent(
                toolName: call?.function.name,
                arguments: call?.function.arguments,
                resultText: result?.content,
                resultFallback: result == nil ? "No result recorded" : "Completed",
                isRunning: false,
                isError: state == .error
            )
        }
    }

    private var state: RunTimelineNodeState {
        guard let resultText = result?.content else { return .neutral }
        if resultText.localizedCaseInsensitiveContains("error") || resultText.localizedCaseInsensitiveContains("failed") {
            return .error
        }
        return .completed
    }
}

struct AssistantText: View {
    let text: String

    var body: some View {
        MarkdownMessageView(text: text)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

enum MarkdownBlock: Identifiable {
    case heading(level: Int, text: String)
    case paragraph(String)
    case code(language: String?, content: String)
    case rule
    case table(String)
    case list(items: [String], ordered: Bool)

    var id: String {
        switch self {
        case let .heading(level, text): return "h-\(level)-\(text.hashValue)"
        case let .paragraph(text): return "p-\(text.hashValue)"
        case let .code(language, content): return "c-\(language ?? "")-\(content.hashValue)"
        case .rule: return "r-\(UUID().uuidString)"
        case let .table(text): return "t-\(text.hashValue)"
        case let .list(items, ordered): return "l-\(ordered)-\(items.joined().hashValue)"
        }
    }
}

struct MarkdownMessageView: View {
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.md) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                blockView(block)
            }
        }
        .textSelection(.enabled)
    }

    @ViewBuilder
    private func blockView(_ block: MarkdownBlock) -> some View {
        switch block {
        case let .heading(level, text):
            Text(inlineMarkdown(text))
                .font(.system(size: headingSize(level), weight: .semibold))
                .foregroundStyle(.primary)
                .padding(.top, level == 1 ? AriadneDesign.Space.sm : 0)
        case let .paragraph(text):
            Text(inlineMarkdown(text))
                .font(.system(size: 14))
                .lineSpacing(4)
                .foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)
        case let .code(language, content):
            CodeBlockView(language: language, content: content)
        case .rule:
            AriadneDivider()
                .padding(.vertical, AriadneDesign.Space.xs)
        case let .table(text):
            MarkdownTableView(text: text)
        case let .list(items, ordered):
            VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
                ForEach(Array(items.enumerated()), id: \.offset) { index, item in
                    HStack(alignment: .firstTextBaseline, spacing: AriadneDesign.Space.sm) {
                        Text(ordered ? "\(index + 1)." : "-")
                            .font(.system(size: 14, weight: .medium))
                            .foregroundStyle(.secondary)
                            .frame(width: ordered ? 22 : 12, alignment: .trailing)
                        Text(inlineMarkdown(item))
                            .font(.system(size: 14))
                            .lineSpacing(3)
                            .foregroundStyle(.primary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
    }

    private var blocks: [MarkdownBlock] {
        MarkdownBlockParser.parse(text)
    }

    private func inlineMarkdown(_ text: String) -> AttributedString {
        (try? AttributedString(markdown: text, options: AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(text)
    }

    private func headingSize(_ level: Int) -> CGFloat {
        switch level {
        case 1: return 20
        case 2: return 17
        case 3: return 15
        default: return 14
        }
    }
}

enum MarkdownBlockParser {
    static func parse(_ text: String) -> [MarkdownBlock] {
        var blocks: [MarkdownBlock] = []
        var paragraph: [String] = []
        var codeLines: [String] = []
        var codeLanguage: String?
        var tableLines: [String] = []
        var listItems: [String] = []
        var listOrdered = false
        var inCode = false

        func flushParagraph() {
            guard !paragraph.isEmpty else { return }
            blocks.append(.paragraph(paragraph.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)))
            paragraph.removeAll()
        }

        func flushList() {
            guard !listItems.isEmpty else { return }
            blocks.append(.list(items: listItems, ordered: listOrdered))
            listItems.removeAll()
            listOrdered = false
        }

        func flushTable() {
            guard !tableLines.isEmpty else { return }
            blocks.append(.table(tableLines.joined(separator: "\n")))
            tableLines.removeAll()
        }

        let normalized = text.replacingOccurrences(of: "\r\n", with: "\n")
        for rawLine in normalized.components(separatedBy: "\n") {
            let line = rawLine.trimmingCharacters(in: .whitespaces)

            if line.hasPrefix("```") {
                if inCode {
                    blocks.append(.code(language: codeLanguage, content: codeLines.joined(separator: "\n")))
                    codeLines.removeAll()
                    codeLanguage = nil
                    inCode = false
                } else {
                    flushParagraph()
                    flushTable()
                    flushList()
                    codeLanguage = String(line.dropFirst(3)).trimmingCharacters(in: .whitespacesAndNewlines)
                    if codeLanguage?.isEmpty == true { codeLanguage = nil }
                    inCode = true
                }
                continue
            }

            if inCode {
                codeLines.append(rawLine)
                continue
            }

            if line.isEmpty {
                flushParagraph()
                flushTable()
                flushList()
                continue
            }

            if line == "---" || line == "***" {
                flushParagraph()
                flushTable()
                flushList()
                blocks.append(.rule)
                continue
            }

            if line.hasPrefix("|"), line.hasSuffix("|") {
                flushParagraph()
                flushList()
                tableLines.append(rawLine)
                continue
            } else {
                flushTable()
            }

            if let listItem = parseListItem(line) {
                flushParagraph()
                if !listItems.isEmpty, listOrdered != listItem.ordered {
                    flushList()
                }
                listOrdered = listItem.ordered
                listItems.append(listItem.text)
                continue
            } else {
                flushList()
            }

            if let heading = parseHeading(line) {
                flushParagraph()
                blocks.append(.heading(level: heading.level, text: heading.text))
                continue
            }

            paragraph.append(rawLine)
        }

        if inCode {
            blocks.append(.code(language: codeLanguage, content: codeLines.joined(separator: "\n")))
        }
        flushParagraph()
        flushTable()
        flushList()
        return blocks
    }

    private static func parseHeading(_ line: String) -> (level: Int, text: String)? {
        let hashes = line.prefix { $0 == "#" }
        guard !hashes.isEmpty, hashes.count <= 6 else { return nil }
        let rest = line.dropFirst(hashes.count)
        guard rest.first == " " else { return nil }
        return (hashes.count, String(rest.dropFirst()).trimmingCharacters(in: .whitespaces))
    }

    private static func parseListItem(_ line: String) -> (ordered: Bool, text: String)? {
        if line.hasPrefix("- ") || line.hasPrefix("* ") {
            return (false, String(line.dropFirst(2)).trimmingCharacters(in: .whitespaces))
        }
        guard let dotIndex = line.firstIndex(of: ".") else { return nil }
        let prefix = line[..<dotIndex]
        guard !prefix.isEmpty, prefix.allSatisfy(\.isNumber) else { return nil }
        let rest = line[line.index(after: dotIndex)...]
        guard rest.first == " " else { return nil }
        return (true, String(rest.dropFirst()).trimmingCharacters(in: .whitespaces))
    }
}

struct MarkdownTableView: View {
    let text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(rows.enumerated()), id: \.offset) { rowIndex, row in
                HStack(alignment: .top, spacing: 0) {
                    ForEach(Array(row.enumerated()), id: \.offset) { columnIndex, cell in
                        Text(cell)
                            .font(.system(size: 12, weight: rowIndex == 0 ? .semibold : .regular))
                            .foregroundStyle(rowIndex == 0 ? .primary : .secondary)
                            .lineLimit(3)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, AriadneDesign.Space.sm)
                            .padding(.vertical, AriadneDesign.Space.sm)
                            .background(rowIndex == 0 ? Color.primary.opacity(0.035) : Color.clear)
                            .overlay(alignment: .trailing) {
                                if columnIndex < row.count - 1 {
                                    Rectangle()
                                        .fill(AriadneDesign.ColorToken.softLine)
                                        .frame(width: 1)
                                }
                            }
                    }
                }
                if rowIndex < rows.count - 1 {
                    AriadneDivider()
                }
            }
        }
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }

    private var rows: [[String]] {
        text
            .components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
            .filter { !isDividerRow($0) }
            .map { line in
                line
                    .trimmingCharacters(in: CharacterSet(charactersIn: "|"))
                    .components(separatedBy: "|")
                    .map { $0.trimmingCharacters(in: .whitespaces) }
            }
    }

    private func isDividerRow(_ line: String) -> Bool {
        let stripped = line.replacingOccurrences(of: "|", with: "")
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: ":", with: "")
            .trimmingCharacters(in: .whitespaces)
        return stripped.isEmpty
    }
}

struct CodeBlockView: View {
    let language: String?
    let content: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text((language?.isEmpty == false ? language! : "code").uppercased())
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(.secondary)
                Spacer()
            }
            .padding(.horizontal, AriadneDesign.Space.md)
            .padding(.vertical, AriadneDesign.Space.sm)
            .background(Color.primary.opacity(0.035))

            ScrollView(.horizontal) {
                Text(content)
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(.primary)
                    .padding(AriadneDesign.Space.md)
                    .fixedSize(horizontal: true, vertical: false)
            }
        }
        .background(AriadneDesign.ColorToken.surface, in: RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: AriadneDesign.Radius.md, style: .continuous)
                .stroke(AriadneDesign.ColorToken.line, lineWidth: 1)
        )
    }
}

struct ThinkingDisclosure: View {
    let text: String
    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            MarkdownMessageView(text: text)
                .font(.system(size: 13, design: .serif))
                .foregroundStyle(.secondary)
                .padding(.top, AriadneDesign.Space.sm)
        } label: {
            ThoughtDisclosureLabel(
                isExpanded: isExpanded,
                mode: .completed,
                startedAt: nil,
                fallbackTitle: "Thought"
            )
        }
        .padding(.vertical, AriadneDesign.Space.xs)
    }
}

enum ThoughtDisclosureMode {
    case live
    case completed
}

struct ThoughtDisclosureLabel: View {
    let isExpanded: Bool
    let mode: ThoughtDisclosureMode
    let startedAt: Date?
    var fallbackTitle = "Thought"

    var body: some View {
        switch mode {
        case .live:
            TimelineView(.periodic(from: .now, by: 1.0)) { context in
                labelText(elapsed: elapsedSeconds(now: context.date))
            }
        case .completed:
            labelText(elapsed: nil)
        }
    }

    private func labelText(elapsed: Int?) -> some View {
        HStack(spacing: AriadneDesign.Space.sm) {
            Text(title(elapsed: elapsed))
                .font(.system(size: 12, weight: .semibold, design: .monospaced))
                .foregroundStyle(.secondary)
            Text(isExpanded ? "(collapse)" : "(click to expand)")
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundStyle(.tertiary)
            Spacer(minLength: 0)
        }
    }

    private func title(elapsed: Int?) -> String {
        guard let elapsed else { return fallbackTitle }
        return "Thought for \(max(1, elapsed))s"
    }

    private func elapsedSeconds(now: Date) -> Int? {
        guard let startedAt else { return nil }
        return Int(now.timeIntervalSince(startedAt))
    }
}

struct ToolOutputView: View {
    let text: String

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            Text(cliDisplayText)
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: true, vertical: false)
                .textSelection(.enabled)
        }
        .padding(.leading, AriadneDesign.Space.sm)
    }

    private var cliDisplayText: String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let value = trimmed.isEmpty ? "No output." : trimmed
        let flattened = value
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .joined(separator: "\n│  ")
        return "└ \(flattened)"
    }
}

enum ToolCallFormatter {
    static func displayName(_ raw: String?, isRunning: Bool = false) -> String {
        let name = raw ?? "Tool"
        let displaySource = name.contains(".") ? String(name.split(separator: ".").last ?? Substring(name)) : name
        if isRunning {
            switch name {
            case "web_search", "grep_search": return "SEARCHING"
            case "run_command": return "RUNNING"
            case "view_file", "list_dir": return "READING"
            case "write_file", "replace_file_content", "multi_replace_file_content": return "WRITING"
            case "invoke_subagent": return "CALLING"
            case "define_subagent": return "DEFINING"
            default:
                return "\(displaySource.uppercased())ING"
            }
        } else {
            switch name {
            case "web_search", "grep_search": return "SEARCH"
            case "run_command": return "RUN"
            case "view_file", "list_dir": return "READ"
            case "write_file", "replace_file_content", "multi_replace_file_content": return "WRITE"
            case "invoke_subagent": return "SUBAGENT"
            case "define_subagent": return "SUBAGENT"
            default:
                return displaySource.uppercased()
            }
        }
    }

    static func callExpression(toolName: String?, arguments: String?, isRunning: Bool = false) -> String {
        "\(displayName(toolName, isRunning: isRunning))(\(argumentPreview(arguments)))"
    }

    static func argumentPreview(_ rawArguments: String?) -> String {
        guard let raw = rawArguments?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty else {
            return ""
        }
        if let data = raw.data(using: .utf8),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            for key in ["query", "q", "command", "cmd", "path", "file_path", "url", "pattern"] {
                if let value = object[key] as? String, !value.isEmpty {
                    return quoted(value, max: 76)
                }
            }
            let pieces = object.prefix(2).map { key, value in
                "\(key): \(compact(String(describing: value), max: 44))"
            }
            return pieces.joined(separator: ", ")
        }
        return quoted(raw, max: 76)
    }

    static func summary(_ raw: String?, fallback: String = "Completed", max: Int = 118) -> String {
        guard let raw, !raw.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return fallback
        }
        if let data = raw.data(using: .utf8),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            for key in ["summary", "message", "content", "output", "stdout", "title"] {
                if let value = object[key] as? String, !value.isEmpty {
                    return compact(value, max: max)
                }
            }
            return compact(String(describing: object), max: max)
        }
        return compact(raw, max: max)
    }

    static func compact(_ value: String, max: Int) -> String {
        let normalized = value
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard normalized.count > max else { return normalized }
        let end = normalized.index(normalized.startIndex, offsetBy: max - 1)
        return String(normalized[..<end]) + "…"
    }

    private static func quoted(_ value: String, max: Int) -> String {
        "\"\(compact(value.replacingOccurrences(of: "\"", with: "\\\""), max: max))\""
    }
}

struct ToolExchangeContent: View {
    let toolName: String?
    let arguments: String?
    let resultText: String?
    var resultFallback: String = "Completed"
    var isRunning: Bool
    var isError: Bool
    var isApproval: Bool = false
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
            HStack(alignment: .firstTextBaseline, spacing: AriadneDesign.Space.sm) {
                Text(ToolCallFormatter.callExpression(toolName: toolName, arguments: arguments, isRunning: isRunning))
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundStyle(isError ? AriadneDesign.ColorToken.danger : .primary)
                    .lineLimit(1)

                if isRunning {
                    InlinePulseDots()
                }
            }

            Text(resultLine)
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(resultColor)
                .lineLimit(1)

            if hasDetails {
                DisclosureGroup(isExpanded: $isExpanded) {
                    VStack(alignment: .leading, spacing: AriadneDesign.Space.sm) {
                        if let arguments, !arguments.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            ToolOutputView(text: "parameters: \(arguments)")
                        }
                        if let resultText, !resultText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            ToolOutputView(text: resultText)
                        }
                    }
                    .padding(.top, AriadneDesign.Space.xs)
                } label: {
                    Text(isExpanded ? "└ collapse details" : "└ expand details")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding(.vertical, AriadneDesign.Space.xs)
    }

    private var resultLine: String {
        if isApproval { return "└ Waiting for approval" }
        if isRunning { return "└ Running" }
        if isError { return "└ \(ToolCallFormatter.summary(resultText, fallback: "Failed"))" }
        return "└ \(ToolCallFormatter.summary(resultText, fallback: resultFallback))"
    }

    private var resultColor: Color {
        if isError { return AriadneDesign.ColorToken.danger }
        if isApproval { return AriadneDesign.ColorToken.warning }
        if isRunning { return .secondary }
        return .secondary
    }

    private var hasDetails: Bool {
        let hasArgs = !(arguments?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true)
        let hasResult = !(resultText?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true)
        return hasArgs || hasResult
    }
}

struct InlinePulseDots: View {
    @State private var phase = 0

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.32)) { context in
            let tick = Int(context.date.timeIntervalSinceReferenceDate / 0.32)
            HStack(spacing: 2) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(AriadneDesign.ColorToken.accent.opacity((tick + index) % 3 == 0 ? 0.95 : 0.30))
                        .frame(width: 3.5, height: 3.5)
                        .scaleEffect((tick + index) % 3 == 0 ? 1.18 : 0.88)
                        .animation(.easeInOut(duration: 0.25), value: tick)
                }
            }
            .accessibilityHidden(true)
        }
        .frame(width: 18, height: 8)
    }
}

enum RunTimelineNodeState: Equatable {
    case completed
    case active
    case neutral
    case error
}

struct RunTimelineNode<Content: View>: View {
    let label: String
    var detail: String? = nil
    var state: RunTimelineNodeState = .completed
    @ViewBuilder var content: Content

    var body: some View {
        HStack(alignment: .top, spacing: AriadneDesign.Space.md) {
            ZStack(alignment: .top) {
                TimelineRailSegment(state: state)
                    .padding(.top, 4)
                    .padding(.bottom, -14)
                marker
                    .padding(.top, 4)
            }
            .frame(width: 18)

            VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
                HStack(spacing: AriadneDesign.Space.sm) {
                    Text(label)
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.secondary)
                    if let detail, !detail.isEmpty {
                        Text(detail)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.tertiary)
                            .lineLimit(1)
                    }
                }
                content
                    .padding(.bottom, AriadneDesign.Space.md)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .transition(.asymmetric(
            insertion: .opacity.combined(with: .move(edge: .bottom)),
            removal: .opacity
        ))
        .animation(.spring(response: 0.30, dampingFraction: 0.84), value: state)
    }

    @ViewBuilder
    private var marker: some View {
        switch state {
        case .completed:
            CompletedTimelineMarker()
        case .active:
            ActiveTimelineMarker()
        case .neutral:
            Circle()
                .fill(Color.secondary.opacity(0.45))
                .frame(width: 7, height: 7)
        case .error:
            Circle()
                .fill(AriadneDesign.ColorToken.danger)
                .frame(width: 8, height: 8)
        }
    }
}

struct TimelineRailSegment: View {
    let state: RunTimelineNodeState
    @State private var breath = false

    var body: some View {
        Rectangle()
            .fill(railColor)
            .frame(width: 1)
            .opacity(state == .active ? (breath ? 0.92 : 0.42) : 1)
            .shadow(color: state == .active ? AriadneDesign.ColorToken.accent.opacity(0.24) : .clear, radius: 3)
            .onAppear {
                guard state == .active else { return }
                withAnimation(.easeInOut(duration: 0.95).repeatForever(autoreverses: true)) {
                    breath = true
                }
            }
            .onChange(of: state) { _, newValue in
                guard newValue == .active else {
                    breath = false
                    return
                }
                withAnimation(.easeInOut(duration: 0.95).repeatForever(autoreverses: true)) {
                    breath = true
                }
            }
    }

    private var railColor: Color {
        switch state {
        case .active:
            return AriadneDesign.ColorToken.accent.opacity(0.42)
        case .error:
            return AriadneDesign.ColorToken.danger.opacity(0.30)
        case .neutral:
            return AriadneDesign.ColorToken.softLine
        case .completed:
            return AriadneDesign.ColorToken.softLine
        }
    }
}

struct CompletedTimelineMarker: View {
    @State private var appeared = false

    var body: some View {
        Circle()
            .fill(AriadneDesign.ColorToken.success)
            .frame(width: 8, height: 8)
            .scaleEffect(appeared ? 1 : 0.65)
            .opacity(appeared ? 1 : 0.35)
            .shadow(color: AriadneDesign.ColorToken.success.opacity(0.22), radius: 4, y: 1)
            .onAppear {
                withAnimation(.spring(response: 0.28, dampingFraction: 0.62)) {
                    appeared = true
                }
            }
    }
}

struct ActiveTimelineMarker: View {
    @State private var pulse = false

    var body: some View {
        ZStack {
            Circle()
                .fill(AriadneDesign.ColorToken.accent.opacity(pulse ? 0.12 : 0.04))
                .frame(width: 22, height: 22)
                .scaleEffect(pulse ? 1.05 : 0.72)
            Circle()
                .stroke(AriadneDesign.ColorToken.accent, lineWidth: 1.45)
                .background(Circle().fill(AriadneDesign.ColorToken.canvas))
                .frame(width: 10, height: 10)
                .scaleEffect(pulse ? 1.12 : 0.94)
                .opacity(pulse ? 1.0 : 0.70)
        }
            .onAppear {
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                    pulse = true
                }
            }
    }
}

struct StreamingMessageRow: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var thinkingExpanded = true
    @State private var startedAt = Date()

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.xs) {
            if !viewModel.streamingThinking.isEmpty || (viewModel.streamingEvents.isEmpty && viewModel.streamingReply.isEmpty) {
                RunTimelineNode(label: viewModel.streamingReply.isEmpty ? "Thinking" : "Thought", state: viewModel.streamingReply.isEmpty ? .active : .completed) {
                    DisclosureGroup(isExpanded: $thinkingExpanded) {
                        MarkdownMessageView(text: viewModel.streamingThinking.isEmpty ? "正在分析上下文和用户意图..." : viewModel.streamingThinking)
                            .font(.system(size: 13, design: .serif))
                            .foregroundStyle(.secondary)
                            .padding(.top, AriadneDesign.Space.sm)
                    } label: {
                        ThoughtDisclosureLabel(
                            isExpanded: thinkingExpanded,
                            mode: viewModel.streamingReply.isEmpty ? .live : .completed,
                            startedAt: startedAt,
                            fallbackTitle: "Thought"
                        )
                    }
                }
            }

            ForEach(StreamingToolTimelineBuilder.items(from: viewModel.streamingEvents)) { item in
                RunTimelineNode(
                    label: item.label,
                    detail: nil,
                    state: item.state
                ) {
                    StreamingToolExchangeView(item: item)
                }
            }

            if !viewModel.streamingReply.isEmpty {
                RunTimelineNode(label: "Ariadne", state: .active) {
                    AssistantText(text: viewModel.streamingReply)
                }
            }

            if shouldShowWorkingNode {
                RunTimelineNode(label: "Working", state: .active) {
                    RunActivityStrip()
                }
            }
        }
        .animation(.easeInOut(duration: 0.22), value: viewModel.streamingEvents.count)
        .animation(.easeInOut(duration: 0.22), value: viewModel.streamingReply)
    }

    private var shouldShowWorkingNode: Bool {
        viewModel.streamingReply.isEmpty && !StreamingToolTimelineBuilder.items(from: viewModel.streamingEvents).contains { $0.state == .active }
    }

}

struct StreamingToolTimelineItem: Identifiable, Equatable {
    let id: String
    let callId: String?
    let toolName: String?
    let arguments: String?
    let resultText: String?
    let state: RunTimelineNodeState
    let needsApproval: Bool

    var label: String {
        if state == .error { return "Tool Error" }
        return ToolCallFormatter.displayName(toolName, isRunning: state == .active)
    }
}

enum StreamingToolTimelineBuilder {
    static func items(from events: [RunEvent]) -> [StreamingToolTimelineItem] {
        struct Group {
            var firstIndex: Int
            var call: RunEvent?
            var approval: RunEvent?
            var result: RunEvent?
        }

        var groups: [String: Group] = [:]

        for event in events where isToolEvent(event) {
            let key = event.toolCallId ?? "event-\(event.index)"
            var group = groups[key] ?? Group(firstIndex: event.index, call: nil, approval: nil, result: nil)
            group.firstIndex = min(group.firstIndex, event.index)

            switch event.type {
            case "assistant_tool_call":
                group.call = event
            case "approval_required":
                group.approval = event
            case "tool_result", "tool_error":
                group.result = event
            default:
                break
            }
            groups[key] = group
        }

        return groups
            .sorted { $0.value.firstIndex < $1.value.firstIndex }
            .map { key, group in
                let terminal = group.result
                let state: RunTimelineNodeState
                if terminal?.type == "tool_error" || terminal?.toolResult?.ok == false {
                    state = .error
                } else if terminal != nil {
                    state = .completed
                } else {
                    state = .active
                }

                return StreamingToolTimelineItem(
                    id: key,
                    callId: group.call?.toolCallId ?? terminal?.toolCallId ?? group.approval?.toolCallId,
                    toolName: group.call?.toolName ?? terminal?.toolName ?? group.approval?.toolName,
                    arguments: group.call?.content ?? group.approval?.content,
                    resultText: resultText(for: terminal),
                    state: state,
                    needsApproval: group.approval != nil && terminal == nil
                )
            }
    }

    private static func isToolEvent(_ event: RunEvent) -> Bool {
        switch event.type {
        case "assistant_tool_call", "tool_result", "tool_error", "approval_required":
            return true
        default:
            return false
        }
    }

    private static func resultText(for event: RunEvent?) -> String? {
        guard let event else { return nil }
        if let result = event.toolResult {
            if let content = result.content {
                return content
            }
            if let error = result.error {
                return "\(error.code): \(error.message)"
            }
        }
        return event.content
    }
}

struct StreamingToolExchangeView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    let item: StreamingToolTimelineItem

    var body: some View {
        VStack(alignment: .leading, spacing: AriadneDesign.Space.sm) {
            ToolExchangeContent(
                toolName: item.toolName,
                arguments: item.arguments,
                resultText: item.resultText,
                isRunning: item.state == .active,
                isError: item.state == .error,
                isApproval: item.needsApproval
            )

            if item.needsApproval, let callId = item.callId {
                HStack(spacing: AriadneDesign.Space.sm) {
                    Button {
                        Task {
                            await viewModel.resolveApproval(approvalId: callId, action: "approve")
                        }
                    } label: {
                        Label("Approve", systemImage: "checkmark")
                    }
                    .buttonStyle(.borderedProminent)

                    Button(role: .destructive) {
                        Task {
                            await viewModel.resolveApproval(approvalId: callId, action: "reject")
                        }
                    } label: {
                        Label("Reject", systemImage: "xmark")
                    }
                    .buttonStyle(.bordered)
                }
                .controlSize(.small)
            }
        }
        .padding(.vertical, AriadneDesign.Space.xs)
    }
}

struct RunActivityStrip: View {
    @EnvironmentObject var viewModel: SessionViewModel
    private let startedAt = Date()
    private let thinkingWords = ["Thinking", "Hashing", "Reading", "Checking", "Planning"]
    private let tips = [
        "工具结果会先进入上下文，模型再基于结果继续生成。",
        "如果模型需要更多证据，它会继续请求工具而不是直接猜测。",
        "长回答通常会先整理结构，再逐段输出。",
        "运行中显示的是估算 token，模型返回 usage 后会替换成准确值。",
        "工具调用本身不产生模型 usage，只有模型调用结束时才会返回。"
    ]

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.9)) { context in
            let elapsed = max(0, Int(context.date.timeIntervalSince(startedAt)))
            let tick = max(0, Int(context.date.timeIntervalSince(startedAt) / 0.9))
            let tokenInfo = tokenDisplay(tick: tick)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: AriadneDesign.Space.sm) {
                    ActivityBars(tick: tick)
                    Text("\(activityWord(tick: tick))...")
                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                        .foregroundStyle(activityColor)
                    Text("\(elapsed)s · \(tokenInfo.estimated ? "~" : "")\(tokenInfo.value) tokens")
                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                Text("└─ \(tips[(tick / 2) % tips.count])")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            .padding(.top, AriadneDesign.Space.xs)
            .transition(.opacity.combined(with: .move(edge: .bottom)))
        }
    }

    private var activityColor: Color {
        if hasPendingApproval {
            return AriadneDesign.ColorToken.warning
        }
        return AriadneDesign.ColorToken.accent
    }

    private var timelineItems: [StreamingToolTimelineItem] {
        StreamingToolTimelineBuilder.items(from: viewModel.streamingEvents)
    }

    private var hasPendingApproval: Bool {
        timelineItems.contains { $0.needsApproval }
    }

    private var hasActiveTool: Bool {
        timelineItems.contains { $0.state == .active && !$0.needsApproval }
    }

    private func activityWord(tick: Int) -> String {
        if hasPendingApproval {
            return "Waiting"
        }
        if hasActiveTool {
            return tick.isMultiple(of: 2) ? "Running" : "Reading"
        }
        if !viewModel.streamingReply.isEmpty {
            return "Composing"
        }
        return thinkingWords[tick % thinkingWords.count]
    }

    private func tokenDisplay(tick: Int) -> (value: Int, estimated: Bool) {
        if let usage = viewModel.streamingLatestUsage?.usage {
            if let output = usage.outputTokens {
                return (output, false)
            }
            if let total = usage.totalTokens {
                return (total, false)
            }
        }
        let textSize = viewModel.streamingThinking.count + viewModel.streamingReply.count + viewModel.streamingEvents.count * 80
        return (max(8, Int(ceil(Double(textSize) / 3.0)) + tick * 3), true)
    }
}

struct ActivityBars: View {
    let tick: Int

    var body: some View {
        HStack(alignment: .bottom, spacing: 2) {
            ForEach(0..<4, id: \.self) { index in
                RoundedRectangle(cornerRadius: 1.5, style: .continuous)
                    .fill(AriadneDesign.ColorToken.accent.opacity((tick + index) % 4 == 0 ? 0.95 : 0.28))
                    .frame(width: 3, height: CGFloat(5 + ((tick + index) % 3) * 3))
                    .animation(.easeInOut(duration: 0.28), value: tick)
            }
        }
        .frame(width: 18, height: 13, alignment: .center)
        .accessibilityHidden(true)
    }
}

struct ChatComposerView: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @State private var isInputFocused = false

    private var canSend: Bool {
        !viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !viewModel.isStreaming
    }

    var body: some View {
        VStack(spacing: 0) {
            AriadneDivider()
            VStack(spacing: AriadneDesign.Space.sm) {
                controlsBar
                inputBar
            }
            .frame(maxWidth: AriadneDesign.composerWidth)
            .padding(.horizontal, AriadneDesign.Space.xl)
            .padding(.vertical, AriadneDesign.Space.md)
        }
        .frame(maxWidth: .infinity)
        .background(AriadneDesign.ColorToken.surface.opacity(0.90))
    }

    private var controlsBar: some View {
        HStack(spacing: AriadneDesign.Space.sm) {
            Picker("Agent", selection: $viewModel.selectedAgentName) {
                ForEach(viewModel.agents) { agent in
                    Text(agent.name).tag(agent.name)
                }
            }
            .labelsHidden()
            .frame(width: 154)
            .controlSize(.small)

            Picker("Model", selection: $viewModel.selectedModelId) {
                Text("Default Model").tag(nil as String?)
                ForEach(viewModel.models) { model in
                    Text(model.displayName ?? model.modelId).tag(model.modelId as String?)
                }
            }
            .labelsHidden()
            .frame(width: 232)
            .controlSize(.small)
            .onChange(of: viewModel.selectedModelId) { _, _ in
                Task {
                    await viewModel.updateSessionSettings()
                }
            }

            Spacer()

            Toggle(isOn: $viewModel.thinkingEnabled) {
                Label("Thinking", systemImage: "brain")
                    .font(.system(size: 11))
            }
            .toggleStyle(.checkbox)
            .onChange(of: viewModel.thinkingEnabled) { _, _ in
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
                .labelsHidden()
                .frame(width: 112)
                .controlSize(.small)
                .onChange(of: viewModel.thinkingEffort) { _, _ in
                    Task {
                        await viewModel.updateSessionSettings()
                    }
                }
            }
        }
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: AriadneDesign.Space.md) {
            ReliablePromptTextView(
                text: $viewModel.inputText,
                placeholder: viewModel.isStreaming ? "Draft next message..." : "Message Ariadne...",
                minHeight: 62,
                maxHeight: 62,
                isFocused: $isInputFocused,
                isEnabled: true,
                submitOnReturn: !viewModel.isStreaming
            ) {
                if canSend {
                    Task {
                        await viewModel.sendMessage()
                    }
                }
            }
            .frame(height: 62)
            .modifier(ComposerTextFieldChrome(isFocused: isInputFocused))
            .onTapGesture {
                isInputFocused = true
            }

            Button {
                Task {
                    await viewModel.sendMessage()
                }
            } label: {
                Image(systemName: "arrow.up")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(canSend ? Color.white : .secondary)
                    .frame(width: 34, height: 34)
                    .background(canSend ? AriadneDesign.ColorToken.accent : Color.primary.opacity(0.08), in: Circle())
            }
            .buttonStyle(.plain)
            .disabled(!canSend)
            .padding(.bottom, 3)
        }
    }
}

struct ComposerTextFieldChrome: ViewModifier {
    let isFocused: Bool

    func body(content: Content) -> some View {
        content
            .background(AriadneDesign.ColorToken.elevated)
            .clipShape(RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: AriadneDesign.Radius.lg, style: .continuous)
                    .stroke(isFocused ? AriadneDesign.ColorToken.accent.opacity(0.36) : AriadneDesign.ColorToken.line, lineWidth: isFocused ? 1.3 : 1)
            )
    }
}

struct ReliablePromptTextView: NSViewRepresentable {
    @Binding var text: String
    let placeholder: String
    let minHeight: CGFloat
    let maxHeight: CGFloat
    @Binding var isFocused: Bool
    let isEnabled: Bool
    let submitOnReturn: Bool
    let onSubmit: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeNSView(context: Context) -> PromptTextContainer {
        let container = PromptTextContainer()
        container.textView.delegate = context.coordinator
        container.textView.font = .preferredFont(forTextStyle: .body)
        container.textView.textContainerInset = NSSize(width: 11, height: 9)
        container.textView.textColor = .labelColor
        container.textView.backgroundColor = .clear
        container.textView.drawsBackground = false
        container.textView.isRichText = false
        container.textView.importsGraphics = false
        container.textView.allowsUndo = true
        container.textView.isAutomaticQuoteSubstitutionEnabled = false
        container.textView.isAutomaticDashSubstitutionEnabled = false
        container.textView.isAutomaticTextReplacementEnabled = false
        container.textView.textContainer?.widthTracksTextView = true
        container.textView.textContainer?.lineFragmentPadding = 0
        container.textView.onReturn = {
            if submitOnReturn {
                onSubmit()
                return true
            }
            return false
        }
        container.placeholderLabel.stringValue = placeholder
        container.minHeight = minHeight
        container.maxHeight = maxHeight
        return container
    }

    func updateNSView(_ nsView: PromptTextContainer, context: Context) {
        context.coordinator.parent = self
        if nsView.textView.string != text {
            nsView.textView.string = text
        }
        nsView.placeholderLabel.stringValue = placeholder
        nsView.placeholderLabel.isHidden = !text.isEmpty
        nsView.textView.isEditable = isEnabled
        nsView.textView.textColor = isEnabled ? .labelColor : .secondaryLabelColor
        nsView.minHeight = minHeight
        nsView.maxHeight = maxHeight
        nsView.invalidateIntrinsicContentSize()

        if isFocused, nsView.window?.firstResponder !== nsView.textView {
            DispatchQueue.main.async {
                nsView.window?.makeFirstResponder(nsView.textView)
            }
        }
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: ReliablePromptTextView

        init(_ parent: ReliablePromptTextView) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
            if let container = textView.enclosingScrollView?.superview as? PromptTextContainer {
                container.placeholderLabel.isHidden = !textView.string.isEmpty
                container.invalidateIntrinsicContentSize()
            }
        }

        func textDidBeginEditing(_ notification: Notification) {
            parent.isFocused = true
        }

        func textDidEndEditing(_ notification: Notification) {
            parent.isFocused = false
        }
    }
}

final class PromptTextContainer: NSView {
    let scrollView = NSScrollView()
    let textView = PromptTextView()
    let placeholderLabel = ClickThroughLabel(labelWithString: "")
    var minHeight: CGFloat = 44
    var maxHeight: CGFloat = 132

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.cornerRadius = AriadneDesign.Radius.lg
        layer?.backgroundColor = NSColor.clear.cgColor

        scrollView.drawsBackground = false
        scrollView.hasVerticalScroller = true
        scrollView.autohidesScrollers = true
        scrollView.borderType = .noBorder
        scrollView.documentView = textView

        textView.minSize = NSSize(width: 0, height: 0)
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]

        placeholderLabel.textColor = .placeholderTextColor
        placeholderLabel.font = .preferredFont(forTextStyle: .body)
        placeholderLabel.backgroundColor = .clear
        placeholderLabel.isBezeled = false
        placeholderLabel.isEditable = false
        placeholderLabel.isSelectable = false

        addSubview(scrollView)
        addSubview(placeholderLabel)
    }

    required init?(coder: NSCoder) {
        nil
    }

    override func layout() {
        super.layout()
        scrollView.frame = bounds
        let textHeight = textView.layoutManager?.usedRect(for: textView.textContainer!).height ?? 0
        textView.frame = NSRect(
            x: 0,
            y: 0,
            width: bounds.width,
            height: max(bounds.height, textHeight + 22)
        )
        placeholderLabel.frame = NSRect(x: 11, y: bounds.height - 31, width: max(0, bounds.width - 22), height: 20)
    }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        true
    }

    override func mouseDown(with event: NSEvent) {
        window?.makeFirstResponder(textView)
        super.mouseDown(with: event)
    }

    override func hitTest(_ point: NSPoint) -> NSView? {
        let hit = super.hitTest(point)
        return hit === placeholderLabel ? textView : hit
    }

    override var intrinsicContentSize: NSSize {
        let textHeight = textView.layoutManager?.usedRect(for: textView.textContainer!).height ?? 0
        let height = min(max(textHeight + 22, minHeight), maxHeight)
        return NSSize(width: NSView.noIntrinsicMetric, height: height)
    }
}

final class ClickThroughLabel: NSTextField {
    override func hitTest(_ point: NSPoint) -> NSView? {
        nil
    }
}

final class PromptTextView: NSTextView {
    var onReturn: (() -> Bool)?

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        true
    }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 36, !event.modifierFlags.contains(.shift), onReturn?() == true {
            return
        }
        super.keyDown(with: event)
    }
}
