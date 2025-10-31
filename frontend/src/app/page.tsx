'use client'

import { useEffect, useState } from 'react'

interface Strategy {
  id: string
  name: string
  exchange_a: string
  exchange_b: string
  symbol: string
  status: string
  size: number
  max_position: number
  build_threshold_apr: number
  close_threshold_apr: number
}

export default function Home() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/strategies')
      .then(res => res.json())
      .then(data => {
        setStrategies(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to fetch strategies:', err)
        setLoading(false)
      })
  }, [])

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold mb-8">Funding Rate Arbitrage Dashboard</h1>

        {loading ? (
          <p>Loading strategies...</p>
        ) : strategies.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">No strategies configured yet.</p>
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md">
              Create Strategy
            </button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {strategies.map(strategy => (
              <div
                key={strategy.id}
                className="p-6 border rounded-lg shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-xl font-semibold">{strategy.name}</h2>
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      strategy.status === 'running'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {strategy.status}
                  </span>
                </div>

                <div className="space-y-2 text-sm text-muted-foreground">
                  <div className="flex justify-between">
                    <span>Pair:</span>
                    <span className="font-medium text-foreground">
                      {strategy.exchange_a} vs {strategy.exchange_b}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Symbol:</span>
                    <span className="font-medium text-foreground">{strategy.symbol}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Size:</span>
                    <span className="font-medium text-foreground">{strategy.size}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Build Threshold:</span>
                    <span className="font-medium text-foreground">
                      {(strategy.build_threshold_apr * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t flex gap-2">
                  <button className="flex-1 px-3 py-2 text-sm border rounded-md hover:bg-accent">
                    View Details
                  </button>
                  <button
                    className={`flex-1 px-3 py-2 text-sm rounded-md ${
                      strategy.status === 'running'
                        ? 'bg-red-100 text-red-800 hover:bg-red-200'
                        : 'bg-green-100 text-green-800 hover:bg-green-200'
                    }`}
                  >
                    {strategy.status === 'running' ? 'Stop' : 'Start'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
