import SwiftUI

struct PhotoDetailView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var libraryStore: LibraryStore
    let photo: Photo
    
    var body: some View {
        NavigationStack {
            HStack(spacing: 0) {
                // Main photo view
                VStack {
                    // Mock photo display - in real app this would be the full-res image
                    RoundedRectangle(cornerRadius: 12)
                        .fill(
                            LinearGradient(
                                colors: [.blue.opacity(0.4), .purple.opacity(0.4)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .aspectRatio(4/3, contentMode: .fit)
                        .overlay {
                            VStack {
                                Image(systemName: "photo.fill")
                                    .font(.system(size: 48))
                                    .foregroundColor(.white.opacity(0.8))
                                Text(photo.filename)
                                    .font(.title2)
                                    .foregroundColor(.white)
                                    .fontWeight(.medium)
                            }
                        }
                        .background(Color.black.opacity(0.1))
                        .cornerRadius(12)
                        .padding()
                    
                    Spacer()
                }
                
                // Sidebar with metadata
                VStack(alignment: .leading, spacing: 20) {
                    // Photo info
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Photo Details")
                            .font(.headline)
                        
                        InfoRow(label: "Filename", value: photo.filename)
                        InfoRow(label: "Size", value: photo.displaySize)
                        InfoRow(label: "Dimensions", value: "\(photo.width ?? 0) × \(photo.height ?? 0)")
                        InfoRow(label: "Format", value: photo.mimeType.uppercased())
                        InfoRow(label: "Created", value: photo.createdAt.formatted(date: .abbreviated, time: .shortened))
                    }
                    
                    Divider()
                    
                    // Camera info
                    if let metadata = photo.metadata {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Camera Info")
                                .font(.headline)
                            
                            InfoRow(label: "Camera", value: metadata.cameraInfo)
                            if let lens = metadata.lensModel {
                                InfoRow(label: "Lens", value: lens)
                            }
                            if !metadata.exposureInfo.isEmpty {
                                InfoRow(label: "Settings", value: metadata.exposureInfo)
                            }
                            if let dateTaken = metadata.dateTaken {
                                InfoRow(label: "Date Taken", value: dateTaken.formatted(date: .abbreviated, time: .shortened))
                            }
                        }
                        
                        Divider()
                    }
                    
                    // Rating section
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Workflow Rating")
                            .font(.headline)
                        
                        HStack {
                            ForEach(0...5, id: \.self) { rating in
                                Button(action: {
                                    libraryStore.updatePhotoRating(photo.id, rating: rating)
                                }) {
                                    Image(systemName: rating == 0 ? "xmark.circle" : "star.fill")
                                        .foregroundColor(
                                            photo.userRating == rating ? .yellow : .gray.opacity(0.3)
                                        )
                                        .font(.title2)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        
                        Text("Current: \(photo.workflowStage)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                }
                .frame(width: 280)
                .padding()
                .background(Color(NSColor.controlBackgroundColor))
            }
            .navigationTitle(photo.filename)
//            .navigationBarTitleDisplayMode(.inline)
//            .toolbar {
//                ToolbarItem(placement: .navigationBarTrailing) {
//                    Button("Done") {
//                        dismiss()
//                    }
//                }
//            }
        }
        .frame(minWidth: 800, minHeight: 600)
    }
}

struct InfoRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
                .frame(width: 80, alignment: .leading)
            Text(value)
                .fontWeight(.medium)
            Spacer()
        }
        .font(.subheadline)
    }
}

#Preview {
    PhotoDetailView(photo: Photo.mockPhotos[0])
        .environmentObject(LibraryStore())
}
