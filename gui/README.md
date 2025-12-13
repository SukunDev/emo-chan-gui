# Electron Boilerplate

Sebuah aplikasi Electron modern yang dibangun dengan React, TypeScript, dan berbagai teknologi terdepan untuk pengembangan aplikasi desktop yang powerful dan scalable.

## Deskripsi

Proyek ini adalah boilerplate Electron yang lengkap dengan fitur-fitur modern seperti:
- **React 19** dengan TypeScript untuk UI yang type-safe
- **TanStack Router** untuk routing yang powerful
- **TanStack Query** untuk state management dan data fetching
- **shadcn/ui** components dengan Tailwind CSS untuk UI yang modern
- **Authentication System** dengan JWT token management
- **Electron Store** untuk penyimpanan data lokal
- **Custom Window Controls** (minimize, maximize, close)
- **Dark Theme** sebagai default

## Fitur Utama

- ✅ **Modern Tech Stack**: React 19, TypeScript, Electron 38
- ✅ **Type-Safe Routing**: TanStack Router dengan file-based routing
- ✅ **State Management**: TanStack Query untuk server state
- ✅ **UI Components**: shadcn/ui dengan Tailwind CSS
- ✅ **Authentication**: Sistem autentikasi dengan JWT dan protected routes
- ✅ **Local Storage**: Electron Store untuk penyimpanan data lokal
- ✅ **Custom Window**: Frame-less window dengan custom controls
- ✅ **Dark Theme**: Tema gelap sebagai default
- ✅ **Developer Tools**: React Query DevTools dan Router DevTools
- ✅ **Backend Integration**: Terintegrasi dengan REST API backend

## Teknologi yang Digunakan

### Frontend
- **React 19.1.1** - Library UI modern
- **TypeScript 5.9.2** - Type safety
- **TanStack Router 1.135.0** - File-based routing
- **TanStack Query 5.90.7** - Server state management
- **Tailwind CSS 4.1.17** - Utility-first CSS framework
- **shadcn/ui** - Komponen UI yang dapat dikustomisasi
- **Axios 1.13.2** - HTTP client
- **Lucide React** - Icon library

### Electron
- **Electron 38.1.2** - Framework untuk aplikasi desktop
- **electron-vite 4.0.1** - Build tool untuk Electron
- **electron-builder 25.1.8** - Packaging dan distribution
- **electron-store 11.0.2** - Local storage

### Development Tools
- **Vite 7.1.6** - Build tool yang cepat
- **ESLint** - Code linting
- **Prettier** - Code formatting
- **TypeScript** - Type checking

## Instalasi

### Prerequisites

Pastikan Anda telah menginstall:
- **Node.js** (versi 18 atau lebih tinggi)
- **npm** atau **bun** (package manager)

### Langkah Instalasi

1. Clone repository ini:
```bash
git clone <repository-url>
cd electron-boilerplate
```

2. Install dependencies:
```bash
npm install
# atau
bun install
```

3. Setup environment variables (jika diperlukan):
Buat file `.env.local` di root project dengan konfigurasi:
```env
REST_API_URL=http://localhost:3000
```

## Penggunaan

### Development Mode

Jalankan aplikasi dalam mode development dengan hot reload:

```bash
npm run dev
```

Aplikasi akan terbuka dengan DevTools yang dapat diakses dengan `F12`.

### Build untuk Production

#### Windows
```bash
npm run build:win
```

#### macOS
```bash
npm run build:mac
```

#### Linux
```bash
npm run build:linux
```

#### Build tanpa packaging (unpacked)
```bash
npm run build:unpack
```

File hasil build akan tersimpan di folder `dist/`.

### Scripts Lainnya

```bash
# Type checking
npm run typecheck

# Linting
npm run lint

# Format code
npm run format

# Build saja (tanpa packaging)
npm run build
```

## Struktur Project

```
electron-boilerplate/
├── src/
│   ├── main/              # Electron main process
│   │   ├── index.ts       # Entry point main process
│   │   └── lib/           # Utilities untuk main process
│   ├── preload/           # Preload scripts
│   │   └── index.ts       # Preload script
│   └── renderer/          # React application
│       └── src/
│           ├── components/    # React components
│           ├── routes/         # File-based routes
│           ├── contexts/       # React contexts
│           ├── lib/           # Utilities
│           ├── hooks/         # Custom hooks
│           └── types/        # TypeScript types
├── resources/             # Resources (icons, etc.)
├── dist/                  # Build output
├── out/                   # Development build output
├── electron-builder.yml    # Electron Builder config
├── electron.vite.config.ts # Electron Vite config
└── package.json
```

## Authentication

Aplikasi ini dilengkapi dengan sistem autentikasi yang lengkap:

- **Login**: Menggunakan username/password
- **JWT Token**: Token-based authentication
- **Token Storage**: Token disimpan menggunakan Electron Store
- **Protected Routes**: Route yang memerlukan autentikasi
- **Auto Logout**: Logout otomatis saat token expired

### Menggunakan Auth Service

```typescript
import authService from '@renderer/lib/authService'

// Login
const response = await authService.login(email, password)
authService.handleAuthSuccess(response)

// Check authentication
const isAuthenticated = await authService.isAuthenticated()

// Get user
const user = await authService.getUser()

// Logout
authService.logout()
```

## UI Components

Proyek ini menggunakan **shadcn/ui** components yang dapat dikustomisasi. Komponen tersedia di `src/renderer/src/components/ui/`.

Beberapa komponen yang tersedia:
- Button
- Card
- Input
- Checkbox
- Dropdown Menu
- Avatar
- Sidebar
- Sheet
- Tooltip
- dan lainnya...

## IPC Communication

Aplikasi menggunakan IPC (Inter-Process Communication) untuk komunikasi antara main process dan renderer process.

### Available IPC Handlers

- `window:minimize` - Minimize window
- `window:maximize` - Maximize/Restore window
- `window:close` - Close window
- `auth:login` - Handle login
- `store:set` - Set value in store
- `store:get` - Get value from store
- `store:clear` - Clear all store values
- `todos:fetch` - Fetch todos (example)

### Menggunakan IPC dari Renderer

```typescript
// Minimize window
window.api.window.minimize()

// Maximize window
window.api.window.maximize()

// Close window
window.api.window.close()

// Store operations
await window.api.store.set('key', 'value')
const value = await window.api.store.get('key')
await window.api.store.clear()
```

## Backend Integration

Aplikasi terintegrasi dengan REST API backend. Konfigurasi API URL dapat diubah di `src/main/lib/config.ts`.

Default API URL: `http://localhost:3000`

## Development

### Recommended IDE Setup

- **VSCode** dengan ekstensi:
  - ESLint
  - Prettier
  - TypeScript

### Code Style

Proyek menggunakan:
- **ESLint** untuk linting
- **Prettier** untuk formatting
- **TypeScript** untuk type checking

Jalankan sebelum commit:
```bash
npm run lint
npm run format
npm run typecheck
```

## Environment Variables

Buat file `.env.local` di root project:

```env
REST_API_URL=http://localhost:3000
ELECTRON_RENDERER_URL=http://localhost:5173
```