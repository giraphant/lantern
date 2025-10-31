# Funding Rate Arbitrage - Frontend Dashboard

Next.js dashboard for monitoring and managing funding rate arbitrage strategies.

## Features

- Strategy overview cards
- Real-time funding rate monitoring
- Position tracking
- Historical data visualization
- Strategy creation and management

## Technology Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **shadcn/ui** - Component library
- **TanStack Query** - Data fetching
- **Recharts** - Charts and graphs

## Development

### Setup

```bash
cd frontend
npm install
```

### Run locally

```bash
npm run dev
```

Dashboard will be available at http://localhost:3000

### Build for production

```bash
npm run build
npm start
```

### Run with Docker

```bash
docker build -t funding-bot-frontend .
docker run -p 3000:3000 funding-bot-frontend
```

## Project Structure

```
src/
├── app/              # Next.js App Router pages
│   ├── layout.tsx    # Root layout
│   ├── page.tsx      # Home page (strategy list)
│   └── globals.css   # Global styles
├── components/       # React components
│   ├── ui/          # shadcn/ui components
│   └── ...          # Custom components
└── lib/             # Utility functions
    ├── api.ts       # API client
    └── utils.ts     # Helper functions
```

## Configuration

### Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### API Proxy

API requests are automatically proxied to the backend in `next.config.js`.

## TODO

- [ ] Add strategy creation form
- [ ] Implement strategy detail page
- [ ] Add real-time WebSocket updates
- [ ] Add funding rate charts
- [ ] Add position history charts
- [ ] Add trade history table
- [ ] Add dark mode toggle
- [ ] Add authentication
- [ ] Add mobile responsive design
- [ ] Add loading states
- [ ] Add error handling
