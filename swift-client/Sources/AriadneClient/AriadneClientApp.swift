import SwiftUI

@main
struct AriadneClientApp: App {
    @StateObject private var viewModel = SessionViewModel()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(viewModel)
                .frame(minWidth: 1000, minHeight: 650)
                .task {
                    await viewModel.loadAllData()
                }
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unifiedCompact)
    }
}
