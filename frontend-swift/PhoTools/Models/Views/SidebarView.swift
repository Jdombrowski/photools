import SwiftUI

struct SidebarView: View {
    @Binding var selectedItem: SidebarItem
    @EnvironmentObject var libraryStore: LibraryStore
    
    var body: some View {
        List(selection: $selectedItem) {
            // App branding header
            VStack {
                HStack {
                    Image(systemName: "camera.viewfinder")
                        .font(.title)
                        .foregroundColor(PhoToolsTheme.primaryColor)
                    Text("PhoTools")
                        .font(PhoToolsTheme.titleFont)
                        .foregroundColor(PhoToolsTheme.primaryText)
                }
                .padding(.vertical, 8)
            }
            .listRowBackground(Color.clear)
            .listRowSeparator(.hidden)
            
            // Main sections
            Section("Library") {
                ForEach(SidebarItem.allCases, id: \.self) { item in
                    Label(item.rawValue, systemImage: item.icon)
                        .tag(item)
                        .foregroundColor(selectedItem == item ? PhoToolsTheme.primaryColor : PhoToolsTheme.primaryText)
                        .font(Font.custom("Comic Sans MS", size: 12 ))
                }
            }
            
            // Quick stats section
            Section("Stats") {
                HStack {
                    Image(systemName: "photo")
                        .foregroundColor(PhoToolsTheme.mutedText)
                    Text("\(libraryStore.photoCount) photos")
                        .foregroundColor(PhoToolsTheme.secondaryText)
                    Spacer()
                }
                .font(.caption)
                
                if libraryStore.selectedPhotoCount > 0 {
                    HStack {
                        Image(systemName: "checkmark.circle")
                            .foregroundColor(PhoToolsTheme.primaryColor)
                        Text("\(libraryStore.selectedPhotoCount) selected")
                            .foregroundColor(PhoToolsTheme.secondaryText)
                        Spacer()
                    }
                    .font(.caption)
                }
            }
            
            // Quick filters section
            Section("Quick Filters") {
                Button(action: { libraryStore.selectedRating = 5 }) {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(PhoToolsTheme.accentColor)
                        Text("Showcase (5★)")
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                .font(Font.custom("Comic Sans MS", size: 12 ))
                
                Button(action: { libraryStore.selectedRating = 4 }) {
                    HStack {
                        Image(systemName: "star.fill")
                            .foregroundColor(PhoToolsTheme.secondaryColor)
                        Text("Portfolio (4★)")
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                .font(Font.custom("Comic Sans MS", size: 12 ))
                
                Button(action: { libraryStore.selectedRating = 0 }) {
                    HStack {
                        Image(systemName: "questionmark.circle")
                            .foregroundColor(PhoToolsTheme.mutedText)
                        Text("Unrated")
                            .foregroundColor(PhoToolsTheme.primaryText)
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
                .font(Font.custom("Comic Sans MS", size: 12 ))
                
                if libraryStore.selectedRating != nil {
                    Button("Clear Filter") {
                        libraryStore.selectedRating = nil
                    }
                    .foregroundColor(PhoToolsTheme.primaryColor)
                }
            }
        }
        .listStyle(.sidebar)
        .background(PhoToolsTheme.sidebarBackground)
        .navigationTitle("")
    }
}

#Preview {
    NavigationSplitView {
        SidebarView(selectedItem: .constant(.library))
            .environmentObject(LibraryStore())
    } detail: {
        Text("Detail View")
            .font(Font.custom("Comic Sans MS", size: 12 ))
    }
}
