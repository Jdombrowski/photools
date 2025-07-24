import SwiftUI

struct SidebarView: View {
    @Binding var selectedItem: SidebarItem
    @EnvironmentObject var libraryStore: LibraryStore
    
    var body: some View {
        List(selection: $selectedItem) {
            // Main sections
            Section("Library") {
                ForEach(SidebarItem.allCases, id: \.self) { item in
                    Label(item.rawValue, systemImage: item.icon)
                        .tag(item)
                }
            }
            
            // Quick stats section
            Section("Stats") {
                HStack {
                    Image(systemName: "photo")
                        .foregroundColor(.secondary)
                    Text("\(libraryStore.photoCount) photos")
                    Spacer()
                }
                .font(.caption)
                .foregroundColor(.secondary)
                
                if libraryStore.selectedPhotoCount > 0 {
                    HStack {
                        Image(systemName: "checkmark.circle")
                            .foregroundColor(.blue)
                        Text("\(libraryStore.selectedPhotoCount) selected")
                        Spacer()
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
            }
            
            // Quick filters section
            Section("Quick Filters") {
                Button(action: { libraryStore.selectedRating = 5 }) {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(.yellow)
                        Text("Showcase (5★)")
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                
                Button(action: { libraryStore.selectedRating = 4 }) {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(.orange) 
                        Text("Portfolio (4★)")
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                
                Button(action: { libraryStore.selectedRating = 0 }) {
                    HStack {
                        Image(systemName: "questionmark.circle")
                            .foregroundColor(.gray)
                        Text("Unrated")
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                
                if libraryStore.selectedRating != nil {
                    Button("Clear Filter") {
                        libraryStore.selectedRating = nil
                    }
                    .foregroundColor(.blue)
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("Photools")
    }
}

#Preview {
    NavigationSplitView {
        SidebarView(selectedItem: .constant(.library))
            .environmentObject(LibraryStore())
    } detail: {
        Text("Detail View")
    }
}