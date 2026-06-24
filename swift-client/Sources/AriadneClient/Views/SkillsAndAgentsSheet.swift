import SwiftUI

struct SkillsAndAgentsSheet: View {
    @EnvironmentObject var viewModel: SessionViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var activeTab = 0
    
    // Create Agent Form State
    @State private var newAgentName = ""
    @State private var newAgentDescription = ""
    @State private var newAgentSystemPrompt = ""
    @State private var selectedTools: Set<String> = []
    @State private var showingCreateForm = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Plugins & Custom Agents")
                    .font(.title2)
                    .fontWeight(.bold)
                Spacer()
                Button("Close") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)
            }
            .padding()
            .background(Color(NSColor.windowBackgroundColor))
            
            Divider()
            
            // Tab View
            TabView(selection: $activeTab) {
                skillsTab()
                    .tabItem {
                        Label("Skills (Plugins)", systemImage: "puzzlepiece.fill")
                    }
                    .tag(0)
                
                agentsTab()
                    .tabItem {
                        Label("Custom Agents", systemImage: "person.2.badge.gearshape.fill")
                    }
                    .tag(1)
            }
            .padding()
        }
        .frame(width: 680, height: 500)
    }
    
    // MARK: - Skills Tab
    @ViewBuilder
    private func skillsTab() -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Python Skills & Extensions")
                .font(.headline)
                .foregroundColor(.secondary)
            
            Text("Skills allow the agent to execute complex task workflows. Toggle to enable or disable them.")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .padding(.bottom, 5)
            
            List {
                if viewModel.skills.isEmpty {
                    Text("No registered skills found.")
                        .foregroundColor(.secondary)
                        .italic()
                        .padding()
                } else {
                    ForEach(viewModel.skills) { skill in
                        HStack(alignment: .top, spacing: 15) {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(skill.name)
                                        .font(.body)
                                        .fontWeight(.semibold)
                                    
                                    if let err = skill.error, !err.isEmpty {
                                        Text("Error")
                                            .font(.caption2)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2)
                                            .background(Color.red.opacity(0.15))
                                            .foregroundColor(.red)
                                            .cornerRadius(4)
                                            .help(err)
                                    }
                                }
                                
                                if let desc = skill.description {
                                    Text(desc)
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                                
                                Text(skill.path)
                                    .font(.system(.caption, design: .monospaced))
                                    .foregroundColor(.secondary.opacity(0.7))
                            }
                            
                            Spacer()
                            
                            Toggle("", isOn: Binding(
                                get: { skill.enabled },
                                set: { _ in
                                    Task {
                                        await viewModel.toggleSkill(skill)
                                    }
                                }
                            ))
                            .toggleStyle(.switch)
                            .labelsHidden()
                        }
                        .padding(.vertical, 6)
                    }
                }
            }
            .listStyle(.inset(alternatesRowBackgrounds: true))
        }
    }
    
    // MARK: - Agents Tab
    @ViewBuilder
    private func agentsTab() -> some View {
        VStack(spacing: 12) {
            if showingCreateForm {
                createAgentForm()
            } else {
                HStack {
                    Text("Agent Templates")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Button(action: {
                        showingCreateForm = true
                    }) {
                        Label("New Agent", systemImage: "plus")
                    }
                }
                
                List {
                    ForEach(viewModel.agents) { agent in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(agent.name)
                                    .font(.body)
                                    .fontWeight(.bold)
                                
                                if agent.isBuiltin {
                                    Text("Built-in")
                                        .font(.caption2)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(Color.accentColor.opacity(0.15))
                                        .foregroundColor(.accentColor)
                                        .cornerRadius(4)
                                }
                                
                                Spacer()
                                
                                if !agent.isBuiltin {
                                    Button(action: {
                                        Task {
                                            await viewModel.removeAgent(agentId: agent.id)
                                        }
                                    }) {
                                        Image(systemName: "trash")
                                            .foregroundColor(.red)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            
                            if let desc = agent.description {
                                Text(desc)
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            
                            if let prompt = agent.systemPrompt {
                                Text("Prompt: \(prompt)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .lineLimit(2)
                                    .padding(.leading, 8)
                                    .border(Color.secondary.opacity(0.2), width: 1)
                                    .background(Color(NSColor.controlBackgroundColor))
                            }
                            
                            if let tools = agent.toolNames, !tools.isEmpty {
                                FlowLayout(spacing: 6) {
                                    ForEach(tools, id: \.self) { tool in
                                        Text(tool)
                                            .font(.caption2)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2)
                                            .background(Color.secondary.opacity(0.15))
                                            .cornerRadius(4)
                                    }
                                }
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
        }
    }
    
    // MARK: - Create Custom Agent Form
    @ViewBuilder
    private func createAgentForm() -> some View {
        VStack(spacing: 0) {
            HStack {
                Text("Create Custom Agent")
                    .font(.headline)
                Spacer()
                Button("Cancel") {
                    showingCreateForm = false
                    clearForm()
                }
                .buttonStyle(.borderless)
            }
            .padding(.bottom, 12)
            
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Group {
                        Text("Name").fontWeight(.semibold)
                        TextField("e.g. Code Reviewer", text: $newAgentName)
                            .textFieldStyle(.roundedBorder)
                        
                        Text("Description").fontWeight(.semibold)
                        TextField("e.g. Reviews swift changes", text: $newAgentDescription)
                            .textFieldStyle(.roundedBorder)
                        
                        Text("System Prompt").fontWeight(.semibold)
                        TextEditor(text: $newAgentSystemPrompt)
                            .frame(height: 80)
                            .border(Color.secondary.opacity(0.2))
                            .cornerRadius(4)
                    }
                    
                    Text("Select Superpowers (Tools)")
                        .fontWeight(.semibold)
                        .padding(.top, 4)
                    
                    if viewModel.tools.isEmpty {
                        Text("No tools registered on backend.")
                            .italic()
                            .foregroundColor(.secondary)
                    } else {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 180))], alignment: .leading, spacing: 10) {
                            ForEach(viewModel.tools, id: \.self) { tool in
                                Toggle(tool, isOn: Binding(
                                    get: { selectedTools.contains(tool) },
                                    set: { isSelected in
                                        if isSelected {
                                            selectedTools.insert(tool)
                                        } else {
                                            selectedTools.remove(tool)
                                        }
                                    }
                                ))
                                .toggleStyle(.checkbox)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
                .padding(.horizontal, 4)
            }
            
            Divider().padding(.vertical, 12)
            
            HStack {
                Spacer()
                Button("Save Agent") {
                    let agent = AgentDefinition(
                        name: newAgentName,
                        systemPrompt: newAgentSystemPrompt,
                        description: newAgentDescription.isEmpty ? nil : newAgentDescription,
                        toolNames: Array(selectedTools),
                        isBuiltin: false
                    )
                    Task {
                        await viewModel.saveAgent(definition: agent)
                        showingCreateForm = false
                        clearForm()
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(newAgentName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }
    
    private func clearForm() {
        newAgentName = ""
        newAgentDescription = ""
        newAgentSystemPrompt = ""
        selectedTools.removeAll()
    }
}

// Simple FlowLayout helper for badges
struct FlowLayout: Layout {
    var spacing: CGFloat
    
    init(spacing: CGFloat = 6) {
        self.spacing = spacing
    }
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var height: CGFloat = 0
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var maxRowHeight: CGFloat = 0
        
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if currentX + size.width > width {
                // new line
                currentX = 0
                currentY += maxRowHeight + spacing
                maxRowHeight = 0
            }
            currentX += size.width + spacing
            maxRowHeight = max(maxRowHeight, size.height)
        }
        height = currentY + maxRowHeight
        return CGSize(width: width, height: height)
    }
    
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var currentX: CGFloat = bounds.minX
        var currentY: CGFloat = bounds.minY
        var maxRowHeight: CGFloat = 0
        
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if currentX + size.width > bounds.maxX {
                currentX = bounds.minX
                currentY += maxRowHeight + spacing
                maxRowHeight = 0
            }
            view.place(at: CGPoint(x: currentX, y: currentY), proposal: .unspecified)
            currentX += size.width + spacing
            maxRowHeight = max(maxRowHeight, size.height)
        }
    }
}
