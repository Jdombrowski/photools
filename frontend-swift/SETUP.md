# Xcode Project Setup Instructions

## Step 1: Create New Xcode Project

1. **Open Xcode**
2. **File → New → Project**
3. **Choose "macOS" tab → "App"**
4. **Project Details:**
   - Product Name: `Photools`
   - Interface: `SwiftUI`
   - Language: `Swift`
   - Bundle Identifier: `com.photools.desktop`
   - Team: (your developer account)
   - Use Core Data: `No`
   - Include Tests: `Yes` (optional)

5. **Choose save location** (this frontend-swift folder)
6. **Click Create**

## Step 2: Add Our Files

Xcode will create a basic project. Now replace/add our files:

### **Replace Default Files:**
1. **Delete** the default `ContentView.swift`
2. **Replace** `PhotoolsApp.swift` with our version

### **Add Our Files:**
Drag these files from Finder into Xcode's navigator:

**Models folder:**
- `Models/Photo.swift`
- `Models/LibraryStore.swift`

**Views folder:**
- `Views/ContentView.swift`
- `Views/SidebarView.swift`
- `Views/LibraryView.swift`
- `Views/PhotoThumbnailView.swift`
- `Views/PhotoDetailView.swift`
- `Views/ImportView.swift`
- `Views/CollectionsView.swift`

**When dragging:** Make sure "Copy items if needed" is checked.

## Step 3: Fix Any Import Issues

If you see red errors:
1. **Build the project** (Cmd+B) - many errors resolve automatically
2. **Check file paths** - make sure all files are in the Xcode navigator
3. **Missing functions** - some placeholder functions might need implementation

## Step 4: Run the App

1. **Select target:** Make sure "Photools" is selected in the scheme
2. **Run:** Press Cmd+R or click the Play button
3. **You should see:** A working photo grid with mock data!

## Expected Result

You'll have a functioning macOS app with:
- ✅ **Sidebar navigation** (Library, Import, Collections, Search)
- ✅ **Photo grid** with mock thumbnails  
- ✅ **Search functionality**
- ✅ **Photo detail view** with ratings
- ✅ **Workflow-based rating system** (0-5 stars)
- ✅ **Responsive layout** that adapts to window size

## Next Steps

Once the basic app is running:
1. **Connect to your Python backend API**
2. **Replace mock data with real photos**
3. **Implement file import functionality**
4. **Add photo thumbnail loading**

## Troubleshooting

**Common Issues:**
- **"Cannot find type 'Photo'"** → Make sure Photo.swift is added to project
- **"Cannot find 'LibraryStore'"** → Check LibraryStore.swift is included
- **Build errors** → Clean build folder (Shift+Cmd+K) then rebuild

**Need Help?**
The app should compile and run with all our existing files. If you hit issues, we can debug them step by step!