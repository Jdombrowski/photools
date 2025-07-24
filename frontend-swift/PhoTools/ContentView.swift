import SwiftUI

struct ContentView: View {
    @EnvironmentObject var libraryStore: LibraryStore
    @State private var selectedSidebarItem: SidebarItem = .library
    
    var body: some View {
        NavigationSplitView {
            // Left sidebar - like your typical macOS app
            SidebarView(selectedItem: $selectedSidebarItem)
                .frame(minWidth: 200, maxWidth: 300)
        } detail: {
            // Main content area
            switch selectedSidebarItem {
            case .library:
                LibraryView()
            case .imports:
                ImportView()
            case .collections:
                CollectionsView()
            case .search:
                SearchView()
            }
        }
        .navigationSplitViewStyle(.balanced) // macOS-style split view
    }
}

// Sidebar navigation items
enum SidebarItem: String, CaseIterable {
    case library = "Library"
    case imports = "Imports"
    case collections = "Collections"
    case search = "Search"
    
    var icon: String {
        switch self {
        case .library: return "photo.on.rectangle"
        case .imports: return "square.and.arrow.down"
        case .collections: return "folder"
        case .search: return "magnifyingglass"
        }
    }
}

// Preview for development - like Storybook
#Preview {
    ContentView()
        .environmentObject(LibraryStore())
}
