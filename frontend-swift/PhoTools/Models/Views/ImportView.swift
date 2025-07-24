import SwiftUI

struct ImportView: View {
    @State private var selectedFolder: String?
    @State private var isShowingFolderPicker = false
    
    var body: some View {
        VStack(spacing: 30) {
            // Header
            VStack(spacing: 10) {
                Image(systemName: "square.and.arrow.down")
                    .font(.system(size: 48))
                    .foregroundColor(.accentColor)
                
                Text("Import Photos")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                
                Text("Select a folder to import photos from")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            // Import options
            VStack(spacing: 20) {
                // Folder selection
                VStack(alignment: .leading, spacing: 8) {
                    Text("Source Folder")
                        .font(.headline)
                    
                    HStack {
                        Text(selectedFolder ?? "No folder selected")
                            .foregroundColor(selectedFolder == nil ? .secondary : .primary)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(Color(NSColor.controlBackgroundColor))
                            .cornerRadius(6)
                        
                        Button("Choose Folder") {
                            isShowingFolderPicker = true
                        }
                        .buttonStyle(.bordered)
                    }
                }
                
                // Import settings (placeholder)
                VStack(alignment: .leading, spacing: 8) {
                    Text("Import Settings")
                        .font(.headline)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Toggle("Copy files to library", isOn: .constant(true))
                        Toggle("Extract metadata", isOn: .constant(true))
                        Toggle("Generate previews", isOn: .constant(true))
                    }
                    .padding()
                    .background(Color(NSColor.controlBackgroundColor))
                    .cornerRadius(8)
                }
            }
            .frame(maxWidth: 400)
            
            // Import button
            Button(action: {
                // TODO: Implement import functionality
            }) {
                Label("Start Import", systemImage: "play.fill")
                    .frame(maxWidth: 200)
            }
            .buttonStyle(.borderedProminent)
            .disabled(selectedFolder == nil)
            
            Spacer()
        }
        .padding()
        .navigationTitle("Import")
        .fileImporter(
            isPresented: $isShowingFolderPicker,
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    selectedFolder = url.path
                }
            case .failure(let error):
                print("Error selecting folder: \(error)")
            }
        }
    }
}

#Preview {
    ImportView()
}