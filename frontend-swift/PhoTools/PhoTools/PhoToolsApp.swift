import SwiftUI

@main
struct PhoToolsApp: App {
    // Create our main data store - like a global Redux store
    @StateObject private var libraryStore = LibraryStore()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(libraryStore) // Makes store available to all child views
                .frame(minWidth: 1200, minHeight: 800) // Minimum window size
                .onAppear {
                    // Load initial data when app starts
                    libraryStore.loadPhotos()
                }
        }
        .windowStyle(.hiddenTitleBar) // Modern macOS window style
        .windowToolbarStyle(.unified)
    }
}
