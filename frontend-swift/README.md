# Photools SwiftUI Frontend

## Getting Started

1. **Open in Xcode**: Open `Photools.xcodeproj` in Xcode
2. **Run**: Press `Cmd+R` or click the Play button to run the app
3. **Target**: Make sure "Photools" is selected as the target

## Project Structure

```
Photools/
├── PhotoolsApp.swift          # Main app entry point
├── ContentView.swift          # Root view
├── Views/
│   ├── LibraryView.swift      # Main photo library grid
│   ├── PhotoGridView.swift    # Photo grid component
│   ├── PhotoThumbnailView.swift # Individual photo thumbnail
│   ├── SidebarView.swift      # Navigation sidebar
│   └── ImportView.swift       # Photo import interface
├── Models/
│   ├── Photo.swift            # Photo data model
│   ├── Collection.swift       # Collection data model
│   └── LibraryStore.swift     # Main data store
├── Services/
│   ├── APIService.swift       # Backend API client
│   └── FileService.swift      # File system operations
└── Utils/
    └── Extensions.swift       # Swift extensions
```

## Key SwiftUI Concepts for React Developers

- **@State**: Like `useState()` - local component state
- **@StateObject**: Like creating a store instance
- **@ObservedObject**: Like connecting to a store
- **@Published**: Like making a property observable
- **body: some View**: Like the render function
- **LazyVGrid**: Like a virtualized grid component

## Running the Backend

Make sure your Python backend is running:
```bash
cd ..
make dev  # Start the FastAPI backend on http://localhost:8000
```

## Development Tips

- **Hot Reload**: SwiftUI has automatic previews - look for `#Preview` at the bottom of files
- **Debugging**: Use `print()` statements or breakpoints in Xcode
- **UI Inspector**: Right-click on simulator and choose "Inspect Element"
- **Documentation**: Cmd+Click on any SwiftUI component to see docs