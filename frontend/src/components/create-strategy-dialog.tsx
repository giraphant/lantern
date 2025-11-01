'use client'

import { useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, type StrategyCreate } from '@/lib/api'
import { Plus } from 'lucide-react'

interface CreateStrategyDialogProps {
  onSuccess?: () => void
}

export function CreateStrategyDialog({ onSuccess }: CreateStrategyDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState<StrategyCreate>({
    name: '',
    exchange_a: 'LIGHTER',
    exchange_b: 'BINANCE',
    symbol: 'BTC-USDC',
    size: 0.001,
    max_position: 0.01,
    build_threshold_apr: 0.15,
    close_threshold_apr: 0.05,
    check_interval: 30,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    try {
      setLoading(true)
      await api.strategies.create(formData)
      setOpen(false)
      // Reset form
      setFormData({
        name: '',
        exchange_a: 'LIGHTER',
        exchange_b: 'BINANCE',
        symbol: 'BTC-USDC',
        size: 0.001,
        max_position: 0.01,
        build_threshold_apr: 0.15,
        close_threshold_apr: 0.05,
        check_interval: 30,
      })
      if (onSuccess) onSuccess()
    } catch (err) {
      alert('Failed to create strategy: ' + (err instanceof Error ? err.message : 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="w-4 h-4 mr-2" />
          Create Strategy
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create New Funding Rate Arbitrage Strategy</DialogTitle>
          <DialogDescription>
            Configure a new strategy to arbitrage funding rates between two exchanges.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Strategy Name</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., BTC Lighter-Binance Arb"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="exchange_a">Exchange A (Pay Funding)</Label>
              <Select
                value={formData.exchange_a}
                onValueChange={(value) => setFormData({ ...formData, exchange_a: value })}
              >
                <SelectTrigger id="exchange_a">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LIGHTER">Lighter</SelectItem>
                  <SelectItem value="BINANCE">Binance</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="exchange_b">Exchange B (Receive Funding)</Label>
              <Select
                value={formData.exchange_b}
                onValueChange={(value) => setFormData({ ...formData, exchange_b: value })}
              >
                <SelectTrigger id="exchange_b">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LIGHTER">Lighter</SelectItem>
                  <SelectItem value="BINANCE">Binance</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="symbol">Symbol</Label>
            <Input
              id="symbol"
              value={formData.symbol}
              onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
              placeholder="e.g., BTC-USDC"
              required
            />
            <p className="text-xs text-gray-500">
              Format: BASE-QUOTE (e.g., BTC-USDC, ETH-USDC)
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="size">Position Size</Label>
              <Input
                id="size"
                type="number"
                step="0.001"
                value={formData.size}
                onChange={(e) => setFormData({ ...formData, size: parseFloat(e.target.value) })}
                required
              />
              <p className="text-xs text-gray-500">
                Amount to trade per order (in base currency)
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="max_position">Max Position</Label>
              <Input
                id="max_position"
                type="number"
                step="0.001"
                value={formData.max_position}
                onChange={(e) => setFormData({ ...formData, max_position: parseFloat(e.target.value) })}
                required
              />
              <p className="text-xs text-gray-500">
                Maximum total position size
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="build_threshold">Build Threshold APR</Label>
              <Input
                id="build_threshold"
                type="number"
                step="0.01"
                value={formData.build_threshold_apr}
                onChange={(e) => setFormData({ ...formData, build_threshold_apr: parseFloat(e.target.value) })}
                required
              />
              <p className="text-xs text-gray-500">
                Minimum funding rate spread to enter position (decimal, e.g., 0.15 = 15% APR)
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="close_threshold">Close Threshold APR</Label>
              <Input
                id="close_threshold"
                type="number"
                step="0.01"
                value={formData.close_threshold_apr}
                onChange={(e) => setFormData({ ...formData, close_threshold_apr: parseFloat(e.target.value) })}
                required
              />
              <p className="text-xs text-gray-500">
                Funding rate spread below which to close position (decimal, e.g., 0.05 = 5% APR)
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="check_interval">Check Interval (seconds)</Label>
            <Input
              id="check_interval"
              type="number"
              value={formData.check_interval}
              onChange={(e) => setFormData({ ...formData, check_interval: parseInt(e.target.value) })}
              required
            />
            <p className="text-xs text-gray-500">
              How often to check funding rates and execute strategy logic
            </p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create Strategy'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
