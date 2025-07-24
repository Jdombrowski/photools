import SwiftUI

struct LibraryView: View {
    @EnvironmentObject var libraryStore: LibraryStore
    @State private var selectedPhoto: Photo?
    @State private var gridSize: CGFloat = 200
    
    // Grid columns that adapt to window size
    private var columns: [GridItem] {
        [GridItem(.adaptive(minimum: gridSize, maximum: gridSize + 50), spacing: 8)]
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Toolbar
            HStack {
                // Search bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(PhoToolsTheme.mutedText)
                    TextField("Search photos...", text: $libraryStore.searchQuery)
                        .textFieldStyle(.plain)
                        .foregroundColor(PhoToolsTheme.primaryText)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(PhoToolsTheme.cardBackground)
                .cornerRadius(6)
                .frame(maxWidth: 300)
                
                Spacer()
                
                // Grid size slider
                HStack {
                    Image(systemName: "square.grid.3x3")
                        .font(.caption)
                    Slider(value: $gridSize, in: 120...300, step: 20)
                        .frame(width: 100)
                    Image(systemName: "square.grid.2x2")
                        .font(.caption)
                }
                .foregroundColor(PhoToolsTheme.mutedText)
                
                // View options
                Button(action: { libraryStore.selectAllPhotos() }) {
                    Label("Select All", systemImage: "checkmark.circle")
                }
                .disabled(libraryStore.filteredPhotos.isEmpty)
                
                if libraryStore.selectedPhotoCount > 0 {
                    Button(action: { libraryStore.deselectAllPhotos() }) {
                        Label("Deselect All", systemImage: "xmark.circle")
                    }
                    
                    Button(action: { libraryStore.deleteSelectedPhotos() }) {
                        Label("Delete", systemImage: "trash")
                    }
                    .foregroundColor(.red)
                }
            }
            .padding()
            .background(PhoToolsTheme.backgroundColor)
            
            Divider()
            
            // Photo grid
            if libraryStore.isLoading {
                VStack {
                    Spacer()
                    ProgressView("Loading photos...")
                        .foregroundColor(PhoToolsTheme.primaryText)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    Spacer()
                }
            } else if libraryStore.filteredPhotos.isEmpty {
                VStack {
                    Spacer()
                    Image(systemName: "photo.on.rectangle")
                        .font(.system(size: 48))
                        .foregroundColor(PhoToolsTheme.mutedText)
                    Text("No photos found")
                        .font(PhoToolsTheme.headlineFont)
                        .foregroundColor(PhoToolsTheme.secondaryText)
                    if !libraryStore.searchQuery.isEmpty {
                        Text("Try adjusting your search terms")
                            .font(PhoToolsTheme.captionFont)
                            .foregroundColor(PhoToolsTheme.mutedText)
                    }
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVGrid(columns: columns, spacing: 8) {
                        ForEach(libraryStore.filteredPhotos) { photo in
                            PhotoThumbnailView(
                                photo: photo,
                                size: gridSize,
                                isSelected: libraryStore.selectedPhotos.contains(photo.id)
                            )
                            .onTapGesture {
                                if NSEvent.modifierFlags.contains(.command) {
                                    // Cmd+click for multi-select
                                    libraryStore.selectPhoto(photo.id)
                                } else {
                                    // Regular click - show detail
                                    selectedPhoto = photo
                                }
                            }
                        }
                    }
                    .padding()
                }
            }
        }
        .navigationTitle("Library (\(libraryStore.filteredPhotos.count))")
        .sheet(item: $selectedPhoto) { photo in
            PhotoDetailView(photo: photo)
        }
    }
}

#Preview {
    LibraryView()
        .environmentObject(LibraryStore())
}